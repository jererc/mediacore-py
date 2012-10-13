import os
import re
import shutil
from stat import S_IMODE
import mimetypes
import filecmp
import logging

from lxml import html
import pexpect

from systools.system import popen

from mediacore.util.title import Title, clean, PATTERN_EXTRA
from mediacore.util.util import in_range, compare_words
from mediacore.util.mediainfo import get_info


RE_TVSHOW_CHECK = re.compile(r'[\W_]s\d{2}e\d{2}[\W_]', re.I)
RE_SPECIAL_CHAR = re.compile(r'[^\w_\-\(\)\[\]\{\}\.]')
RE_SUB_FILENAME = re.compile(r'\((.*)\)$')
RE_SUB_DIFF = re.compile(r'\b(cd[\W_]*\d+|(480|720|1080)[pi]|parodie)\b', re.I)
RE_EXTRACT_ERRORS = {
    '.zip': re.compile(r'\b(signature\snot\sfound|unsupported\scompression\smethod)\b', re.I),
    '.rar': re.compile(r'\bCorrupt\sfile\sor\swrong\spassword\b', re.I),
    }
SIZE_TVSHOW_MAX = 600   # for tvshow detection (MB)
ARCHIVE_DEF = {
    '.zip': ['unzip', '-o'],    # overwrite files
    '.rar': ['unrar', 'x', '-yo+', '-p-'],  # assume yes to all questions, overwrite files, do not query password
    # '.ace': ['unace', 'x', '-y'], # assume yes to all questions
    }
RE_RAR_PASSWORD = re.compile(r'\bEnter password.*for.*:\W*', re.I)
RE_ZIP_PASSWORD = re.compile(r'\bpassword:\W*', re.I)
PATTERNS_LANGS_WORDS = {
    'en': r"i'm|it's|you're|he|she|they|this|that|what|when|why|how|have|has|was|were|yours?|tells?|says?",
    'fr': r"je|il|elle|nous|vous|vais|allons|vont|suis|sommes|sont|j'ai|avons|avez|c'est|cette|mais|donc",
    'sp': r"el|ella|usted|nosotros|nosotras|vosotros|vosotras|ellos|ellas|ustedes|los|las",
    'ge': r"ich|du|das|ist|bin|bist|sind|eine?|keine?|nicht|nein|warum",
    'it': r"sono|sei|siamo|siete|sete|hai|abbiamo|avete|hanno|uno|una",
    'du': r"",
    'nl': r"",
    'sw': r"",
    'ar': r"",
    }

logger = logging.getLogger(__name__)


def iter_files(path_root, incl_files=True, incl_dirs=False, topdown=False, recursive=True):
    '''Iterate files in the root path.
    '''
    if not os.path.exists(path_root):
        logger.error('%s does not exist', path_root)
    elif os.path.isfile(path_root):
        if incl_files:
            yield path_root
    elif recursive:
        for path, dirs, files in os.walk(path_root, topdown=topdown):
            if incl_dirs:
                for dir in dirs:
                    yield os.path.join(path, dir)
            if incl_files:
                for file in files:
                    yield os.path.join(path, file)
    else:
        for file in os.listdir(path_root):
            file = os.path.join(path_root, file)
            if (incl_dirs and os.path.isdir(file)) \
                    or (incl_files and os.path.isfile(file)):
                yield file

def get_file(file, real_file=None):
    '''Get a File object.

    :param real_file: real file
    '''
    cl_default = File

    if real_file:
        file_type = get_file_type(real_file)
    else:
        file_type = get_file_type(file)

    if file_type:
        cl = globals().get(file_type.capitalize(), cl_default)
        return cl(file, real_file=real_file)
    return cl_default(file)

def files(path_root, re_file=None, re_path=None, re_filename=None, re_ext=None,
            size_min=None, size_max=None, incl_files=True, incl_dirs=False,
            types=None, topdown=False, recursive=True):
    '''Iterate files and yield File objects according to the file type.
    '''
    if not os.path.exists(path_root):
        logger.error('%s does not exist', path_root)
    else:
        for file in iter_files(path_root, incl_files=incl_files,
                incl_dirs=incl_dirs, topdown=topdown, recursive=recursive):
            if types:
                if not isinstance(types, (list, tuple)):
                    types = [types]
                if not get_type(file) in types:
                    continue

            res = get_file(file)
            if re_file and not re_file.search(res.file):
                continue
            elif re_path and not re_path.search(res.path):
                continue
            elif re_filename and not re_filename.search(res.filename):
                continue
            elif re_ext and not re_ext.search(res.ext):
                continue
            elif not check_size(res.file, size_min, size_max):
                continue
            yield res

def fsplit(file):
    '''Get the path, filename (without path and extension) and extension of a file.

    :return: tuple
    '''
    path, file_ = os.path.split(file)
    filename, ext = os.path.splitext(file_)
    if (os.path.exists(file) and os.path.isdir(file)) or (not os.path.exists(file) and len(ext)) > 4:
        filename, ext = file_, ''
    return path, filename, ext

def get_size(file):
    '''Get file size (KB).
    '''
    try:
        return os.stat(file).st_size / 1024.0
    except Exception:
        pass

def check_size(file, size_min=None, size_max=None):
    '''Check file size (MB).
    '''
    size = get_size(file)
    if size is not None:
        return in_range(size / 1024, size_min, size_max)

def get_file_type(file):
    # Custom types
    if not os.path.isdir(file):
        ext = os.path.splitext(file)[1].lower()
        if ext in ARCHIVE_DEF:
            return 'archive'
        elif ext in ('.srt', '.ass',):
            return 'subtitles'

    file_type = mimetypes.guess_type(file)[0]
    if file_type:
        file_type = file_type.split('/')[0]
    return file_type

def get_type(file):
    '''Get the file type or the main file type in the directory.
    '''
    if not os.path.isdir(file):
        return get_file_type(file)

    type_stat = {}
    for res in files(file):
        file_type = get_file_type(res.file)
        if file_type:
            type_stat.setdefault(file_type, [0, 0])
            type_stat[file_type][0] += 1
            type_stat[file_type][1] += os.stat(res.file).st_size / 1024
    # Main type has the greatest 'size' * 'number of files'
    stat = sorted([(v[0] * v[1], t) for t, v in type_stat.items()])
    if stat:
        return stat[-1][1]

def get_permissions(file):
    '''Get octal file permissions.
    '''
    return oct(S_IMODE(os.stat(file).st_mode))

def get_unique(file):
    '''Get a unique file or directory name.

    :param file: file or directory
    '''
    if os.path.exists(file):
        path, filename, ext = fsplit(file)
        i = 1
        while os.path.exists(file):
            file = '%s-%d%s' % (os.path.join(path, filename), i, ext)
            i += 1
    return file

def get_clean_filename(file):
    file = clean(file)
    file = RE_SPECIAL_CHAR.sub('_', file)
    return file

def clean_file(file, strip_extra=False):
    '''Clean and rename a file or directory.

    :param strip_extra: strip brackets with text inside, if at the beginning with text after

    :return: cleaned file or directory
    '''
    path, filename, ext = fsplit(file)
    if strip_extra:
        filename = re.compile(r'^%s[\W_]*(.+)$' % PATTERN_EXTRA).sub(r'\1', filename)

    filename = get_clean_filename(filename)
    file_dst = os.path.join(path, filename + ext)
    if file_dst != file:
        # Rename file
        if os.path.exists(file_dst):
            file_dst = get_unique(file_dst)
        file_dst = rename_file(file, file_dst)
    return file_dst

def rename_file(file, file_dst):
    if file_dst != file:
        file_dst = get_unique(file_dst)
        try:
            os.renames(file, file_dst)
        except OSError:
            logger.exception('exception')
            return file
    return file_dst

def is_duplicate(src, dst):
    '''Check if source is identical to destination.
    '''
    if not os.path.exists(dst):
        return
    if os.path.isfile(src):
        return filecmp.cmp(src, dst)

    to_compare = []
    re_filename = re.compile(r'^%s/(.*)$' % re.escape(src))
    for file in iter_files(src):
        filename = re_filename.search(file).group(1)
        to_compare.append(filename)

    match, mismatch, errors = filecmp.cmpfiles(src, dst, to_compare)
    if not mismatch and not errors:
        return True

def move_file(src, path_dst):
    '''Move the file or directory into the destination path.

    :param src: file or directory
    :param path_dst: directory
    '''
    if not os.path.exists(path_dst):
        try:
            os.makedirs(path_dst)
        except Exception:
            logger.exception('failed to create %s', path_dst)
            return

    dst = os.path.join(path_dst, os.path.basename(src))
    if is_duplicate(src, dst):
        remove_file(src)
    else:
        dst = get_unique(dst)
        try:
            shutil.move(src, dst)
        except Exception:
            logger.exception('exception')
            return
    return dst

def remove_file(file):
    if os.path.exists(file):
        try:
            if os.path.isfile(file):
                os.remove(file)
            else:
                shutil.rmtree(file)
        except OSError:
            logger.exception('exception')
            return
    return True

def get_text_lang(val, chunk_size=1024):
    if val:
        stat = {}
        for lp in PATTERNS_LANGS_WORDS:
            stat[lp] = 0
        index = 0
        while index < len(val):
            for lang, pattern in PATTERNS_LANGS_WORDS.items():
                if pattern:
                    stat[lang] += len(re.compile(r'\b(%s)\b' % pattern, re.I).findall(val[index:index + chunk_size]))
            data = sorted([[v, k] for k, v in stat.items()], reverse=True)
            if data[0][0] >= 4 * (data[1][0] + 1):
                return data[0][1]
            index += chunk_size
        if data[0][0] > 0:
            return data[0][1]

def is_html(data):
    try:
        tree = html.fromstring(data)
    except Exception:
        return None
    if tree.cssselect('html'):
        return True


#
# File types
#

class File(object):
    def __init__(self, file, real_file=None):
        self.file = file
        self.type = get_type(file)
        self.path, self.filename, self.ext = fsplit(file)
        self.dir = os.path.basename(self.path)

        if real_file:
            self.real_file = real_file
            self.real_type = get_type(real_file)
            self.real_path, self.real_filename, self.real_ext = fsplit(real_file)
            self.real_dir = os.path.basename(self.real_path)
            self.type = self.real_type

    def get_file_info(self):
        '''Get the file info.
        '''
        return {}

    def get_base(self):
        '''Get the base directory or filename.
        '''
        return self.file


class Media(File):

    TYPES = ['video', 'audio']

    def _has_unrelated(self, name, path):
        '''Check unrelated media in the given directory.
        '''
        size_limit = get_size(self.file) / 10.0
        for file in files(path, types=self.TYPES):
            if file.file == self.file:
                continue

            name_ = file.get_file_info().get('display_name')
            if not name_ or name_ != name:
                if file.type == self.type == 'video' and get_size(file.file) < size_limit:
                    continue
                return True

    def get_base(self):
        path = self.file
        name = self.get_file_info().get('display_name')
        for i in range(3):
            if self._has_unrelated(name, os.path.dirname(path)):
                break
            path = os.path.dirname(path)
        return path


class Video(Media):

    def get_file_info(self):
        '''Get the file info.
        '''
        info = get_info(self.file)
        if info:
            # Get title info using parent directory name and its parent's name
            title = Title(self.filename, [self.dir, os.path.basename(os.path.dirname(self.path))])
            for attr in ('full_name', 'display_name', 'name', 'season', 'episode', 'date', 'rip', 'langs'):
                info[attr] = getattr(title, attr)

            if info['episode'] and (RE_TVSHOW_CHECK.search(self.filename) or check_size(self.file, size_max=SIZE_TVSHOW_MAX)):
                info['subtype'] = 'tv'
            else:
                info['subtype'] = 'movies'
        return info

    def get_subtitles(self, lang):
        '''Get the subtitles file.
        '''
        stat = {}
        info = self.get_file_info()

        re_video = re.compile(r'^%s(.*)' % re.escape(self.filename))
        for sub in files(self.path, re_filename=re_video, types='subtitles'):
            # Get subtitles filename
            sub_post = re_video.search(sub.filename).group(1)
            if sub_post:
                res = RE_SUB_FILENAME.search(sub_post)
                if res:
                    sub_post = res.group(1)
            else:
                sub_post = sub.filename

            # Check sub filename differences
            if RE_SUB_DIFF.search(sub_post) and not RE_SUB_DIFF.search(self.filename):
                continue

            # Check sub filename common words
            if sub.get_file_info()['lang'] == lang:
                r1 = compare_words(self.filename, sub_post)
                r2 = compare_words(info['rip'], sub_post)
                stat[sub.file] = r1 + r2

        if stat:
            return sorted([[v, k] for k, v in stat.items()])[-1][1]


class Audio(Media):

    def get_file_info(self):
        '''Get the file info.
        '''
        info = get_info(self.file)
        if info:
            info['full_name'] = '%s%s%s' % (info['artist'], ' ' if info['artist'] and info['album'] else '', info['album'])
            info['display_name'] = '%s%s%s' % (info['artist'], ' - ' if info['artist'] and info['album'] else '', info['album'])
            if info.get('date'):
                info['display_name'] = '%s%s%s' % (info['display_name'], ' - ' if info['display_name'] else '', info['date'])
            info['subtype'] = 'music'
            if not info.get('display_name'):
                info['display_name'] = clean(self.dir, 1)
        return info


class Subtitles(File):

    def get_file_info(self):
        '''Get the file info.
        '''
        info = {'lang': None}

        # Get lang
        try:
            with open(self.file) as fd:
                data = fd.read()
            info['lang'] = get_text_lang(data)
        except Exception:
            pass

        title = Title(self.filename, self.dir)
        for attr in ('full_name', 'display_name', 'name', 'season', 'episode', 'date'):
            info[attr] = getattr(title, attr)

        return info

    def get_video(self):
        '''Get the related video file.
        '''
        for file in files(self.path, types='video', topdown=True):
            if self.filename.startswith(file.filename):
                return file.file


class Archive(File):

    def get_file_info(self):
        '''Get the file info.
        '''
        info = {}
        info['multipart_files'] = self.get_multipart_files()
        info['protected'] = self.is_protected()
        return info

    def is_main_file(self):
        return self.file == self.get_multipart_files()[0]

    def is_protected(self):
        '''Return True if the archive is password protected.
        '''
        ext = getattr(self, 'real_ext', self.ext).lower()
        if ext == '.rar':
            cmd = 'unrar t "%s"' % self.file
            re_password = RE_RAR_PASSWORD
        elif ext == '.zip':
            cmd = 'unzip -t "%s"' % self.file
            re_password = RE_ZIP_PASSWORD
        else:
            return

        try:
            session = pexpect.spawn(cmd, env={'PATH': os.environ['PATH'], 'TERM': 'dumb'})
            res = session.expect_list([re_password, pexpect.TIMEOUT, pexpect.EOF])
            if res == 0:
                return True
            elif res == 1:
                logger.error('command "%s" timed out', cmd)
        except pexpect.ExceptionPexpect:
            pass
        finally:
            try:
                session.terminate(force=True)   # clean open process
            except pexpect.ExceptionPexpect:
                pass

    def get_multipart_files(self):
        '''Get multipart archive files
        '''
        real_file = getattr(self, 'real_file', self.file)
        path_, filename_, ext_ = fsplit(real_file)

        pattern = re.sub(r'part\d+', r'part\\d+', re.escape(filename_))

        # Get files with an archive extension
        pattern_ext = r'(%s)' % '|'.join([re.escape(k) for k in ARCHIVE_DEF])
        re_files = re.compile(r'/%s%s(\..*)?$' % (pattern, pattern_ext), re.I)
        files_ = sorted([f.file for f in files(self.path,
                re_file=re_files, recursive=False)])

        # Get files with a part extension (e.g.: .rXX)
        pattern_ext = r'(\.r?\d+)'
        re_files = re.compile(r'/%s%s(\..*)?$' % (pattern, pattern_ext), re.I)
        files_more = sorted([f.file for f in files(self.path,
                re_file=re_files, recursive=False)])

        for file in files_more:
            if file not in files_:
                files_.append(file)

        return files_

    def unpack(self, remove_src=True, remove_failed=True):
        '''Unpack the archive in its directory.

        :return: processed files list (including multipart files)
        '''
        ext = self.ext.lower()
        stdout, stderr, returncode = popen(ARCHIVE_DEF[ext] + [self.file], cwd=self.path)
        if returncode != 0:
            if remove_failed and ext in RE_EXTRACT_ERRORS:
                if [l for l in stderr if RE_EXTRACT_ERRORS[ext].search(l)]:
                    remove_src = True
                    logger.info('failed to extract %s: bad archive', self.file)
                else:
                    remove_src = False
                    logger.error('failed to extract %s: %s, %s', self.file, stdout, stderr)

        processed = self.get_multipart_files()

        # Remove files
        if remove_src:
            for processed_file in processed:
                remove_file(processed_file)

        return processed
