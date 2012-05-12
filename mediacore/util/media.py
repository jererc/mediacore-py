import os
import re
from datetime import datetime
import shutil
import stat
import mimetypes
import logging

from lxml import html

# Avoid metadata module debug messages flood
logging.getLogger('metadata').setLevel(logging.CRITICAL)
from kaa import metadata

import pexpect

from systools.system import popen

from mediacore.util.title import Title, clean, get_year, PATTERN_EXTRA
from mediacore.util.util import in_range, compare_words


RE_TVSHOW_CHECK = re.compile(r'[\W_]s\d{2}e\d{2}[\W_]', re.I)
RE_SPECIAL_CHAR = re.compile(r'[^\w_\-\(\)\[\]\{\}\.]')
RE_SUB_FILENAME = re.compile(r'\((.*)\)$')
RE_SUB_DIFF = re.compile(r'\b(cd[\W_]*\d+|(720|1080)[pi]|parodie)\b', re.I)
RE_EXTRACT_SET = re.compile(r'^\.r?\d+$', re.I)
RE_EXTRACT_ERRORS = {
    '.rar': re.compile(r'\bCorrupt\sfile\sor\swrong\spassword\b', re.I),
    '.zip': re.compile(r'\b(signature\snot\sfound|unsupported\scompression\smethod)\b', re.I),
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

def get_modified_date(file):
    '''Get the file modified date.
    '''
    return datetime.utcfromtimestamp(os.stat(file).st_mtime)

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
    return oct(stat.S_IMODE(os.stat(file).st_mode))

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

    dst = get_unique(os.path.join(path_dst, os.path.basename(src)))
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

    def get_base(self, path_root=None):
        '''Get the base directory or filename.
        '''
        return self.file


class Video(File):

    def _get_media_info(self):
        info = {
            'length': '',
            'video_codec': '',
            'audio_codec': '',
            'video_fourcc': '',
            'audio_fourcc': '',
            }
        try:
            meta = metadata.parse(self.file)
        except Exception:
            meta = None
        if meta:
            try:
                info['length'] = meta.length
            except Exception:
                pass
            try:
                info['video_codec'] = str(meta.video[0].codec)
            except Exception:
                pass
            try:
                info['video_fourcc'] = str(meta.video[0].fourcc)
            except Exception:
                pass
            try:
                info['audio_codec'] = str(meta.audio[0].codec)
            except Exception:
                pass
            try:
                info['audio_fourcc'] = str(meta.audio[0].fourcc)
            except Exception:
                pass
        return info

    def get_file_info(self):
        '''Get the file info.
        '''
        info = self._get_media_info()

        # Get title info using parent directory name and its parent's name
        title = Title(self.filename, [self.dir, os.path.basename(os.path.dirname(self.path))])
        for attr in ('full_name', 'display_name', 'name', 'season', 'episode', 'date', 'rip', 'langs'):
            info[attr] = getattr(title, attr)

        if info['episode'] and (RE_TVSHOW_CHECK.search(self.filename) or check_size(self.file, size_max=SIZE_TVSHOW_MAX)):
            info['subtype'] = 'tv'
        else:
            info['subtype'] = 'movies'
        return info

    def get_base(self, path_root=None):
        '''Get the base directory or filename.
        '''
        base = self.file
        size_min = get_size(self.file) / 1024 / 10
        info = self.get_file_info()
        re_name = Title(info['display_name']).get_search_re()
        dir = base
        for i in range(2):
            dir = os.path.dirname(dir)
            if path_root and dir == path_root:
                break

            # Check if directory files are related
            for file in files(dir, size_min=size_min, types=self.type):
                if not re_name.search(file.get_file_info()['display_name']):
                    return base
            base = dir
        return base

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


class Audio(File):

    def _get_media_info(self):
        info = {
            'artist': '',
            'album': '',
            'date': None,
            'track_number': '',
            'title': '',
            }
        try:
            meta = metadata.parse(self.file)
        except Exception:
            meta = None
        if meta:
            try:
                info['artist'] = clean(meta.artist, 1)
            except Exception:
                pass
            try:
                info['album'] = clean(meta.album, 1)
            except Exception:
                pass
            try:
                info['date'] = get_year(meta.userdate)
            except Exception:
                pass
            try:
                track_number = meta.trackno.split('/')[0]
                if track_number.isdigit():
                    info['track_number'] = track_number
            except Exception:
                pass
            try:
                info['title'] = clean(meta.title, 1)
            except Exception:
                pass
        return info

    def get_file_info(self):
        '''Get the file info.
        '''
        info = self._get_media_info()
        info['full_name'] = '%s%s%s' % (info['artist'], ' ' if info['artist'] and info['album'] else '', info['album'])
        info['display_name'] = '%s%s%s' % (info['artist'], ' - ' if info['artist'] and info['album'] else '', info['album'])
        if info['date']:
            info['display_name'] = '%s%s%s' % (info['display_name'], ' - ' if info['display_name'] else '', info['date'])
        return info

    def get_base(self, path_root=None):
        '''Get the base directory or filename.
        '''
        base = self.file
        info = self.get_file_info()
        if info['album']:
            dir = base
            for i in range(2):
                dir = os.path.dirname(dir)
                if path_root and dir == path_root:
                    break

                # Check if directory files are related
                for file in files(dir, types=self.type):
                    info_ = file.get_file_info()
                    if info_['album'] and info_['album'] != info['album']:
                        return base
                base = dir
        return base


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

        video_file = self.get_video()
        if video_file:
            # Get video info
            info_video = get_file(video_file).get_file_info()
            for attr in ('full_name', 'display_name', 'name', 'season', 'episode', 'date', 'subtype'):
                info[attr] = info_video[attr]
        else:
            title = Title(self.filename, self.dir)
            for attr in ('full_name', 'display_name', 'name', 'season', 'episode', 'date'):
                info[attr] = getattr(title, attr)

            if info['episode'] and (RE_TVSHOW_CHECK.search(self.filename) or check_size(self.file, size_max=SIZE_TVSHOW_MAX)):
                info['subtype'] = 'tv'
            else:
                info['subtype'] = 'movies'

        return info

    def get_base(self, path_root=None):
        '''Get the base directory or filename.
        '''
        return self.file

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

    def get_base(self, path_root=None):
        '''Get the base directory or filename.
        '''
        return self.file

    def is_main_file(self):
        multipart_archives = []
        for file in self.get_multipart_files():
            if get_type(file) == self.type:
                multipart_archives.append(file)

        if not multipart_archives or multipart_archives[0] == self.file:
            return True

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
            logger.exception('exception')
        finally:
            session.terminate(force=True)   # clean open process

    def get_multipart_files(self):
        '''Get multipart archive files
        '''
        res = []
        filename_, ext_ = os.path.splitext(self.filename)
        if ext_.lower().startswith('.part') and filename_:
            res = [f.file for f in files(self.path,
                    re_filename=re.compile(r'^%s\.part\d+$' % re.escape(filename_)),
                    re_ext=re.compile(r'^%s$' % re.escape(self.ext), re.I),
                    recursive=False)]
        else:
            res = [self.file] + [f.file for f in files(self.path,
                    re_filename=re.compile(r'^%s$' % re.escape(self.filename)),
                    re_ext=RE_EXTRACT_SET,
                    recursive=False)]

        return sorted(res)

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
