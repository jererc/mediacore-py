import os
import re
import logging

from systools.system import is_file_open

from mediacore.util.media import (File, files, iter_files, clean_file, fsplit, rename_file,
        remove_file, get_file, get_type, get_size, check_size)


RE_BAD_CODEC = re.compile(r'\bunknown\b', re.I)
RE_DOWNLOAD_JUNK = re.compile(r'/(\.DS_Store|Thumbs\.db)$', re.I)
UNPACK_PASSES = 3
SIZE_TVSHOW_MAX = 600   # for tvshow detection (MB)
SIZE_ALBUM_IMAGE_MIN = 50     # KB


logger = logging.getLogger(__name__)


def downloads(path):
    '''Iterate finished downloads.
    '''
    if not os.path.exists(path):
        logger.error('%s does not exist', path)
        return

    for file in iter_files(path, incl_dirs=True, recursive=False):
        if is_file_open(file):
            continue

        file = unpack_download(file)
        for res in get_downloads(file):
            res = clean_download_dir(res)
            if res:
                yield File(res)

def unpack_download(download):
    '''Move download file into a directory and unpack the archives.

    :return: directory
    '''
    download = clean_file(download, strip_extra=True)
    if os.path.isfile(download):
        # Move file into a directory
        path_dst = os.path.splitext(download)[0]
        path, filename, ext = fsplit(download)
        file_dst = rename_file(download, os.path.join(path_dst, filename + ext))
        download = os.path.dirname(file_dst)

    # Unpack archives
    to_skip = []
    for i in range(UNPACK_PASSES):
        for file in sorted(list(iter_files(download))):  # sort for multipart archives
            if file in to_skip:
                continue

            res = get_file(file)
            if res.type == 'archive':
                processed = res.unpack(remove_src=True)
                to_skip += processed
            else:
                to_skip.append(file)

    return download

def clean_download_dir(path):
    '''Clean the download directories and files.
    '''
    for file in list(iter_files(path, incl_dirs=True)) + [path]:
        if os.path.isdir(file) and not os.listdir(file):
            remove_file(file)
        elif RE_DOWNLOAD_JUNK.search(file):
            remove_file(file)
        else:
            clean_file(file)

    if os.path.exists(path):
        return path

def get_downloads(path_root):
    '''Clean and get download sub directories.

    :return: directories list
    '''
    paths = []
    for path in list(iter_files(path_root, incl_files=False, incl_dirs=True)) + [path_root]:

        if get_type(path) == 'audio':
            album = {}
            extra = []
            for file in files(path, recursive=False):
                # Get album files
                if file.type == 'audio' and file.ext.lower() not in ('.m3u',):
                    album[file.file] = file.get_file_info()
                # Get extra files
                elif file.type == 'video' or (file.type == 'image' and get_size(file.file) > SIZE_ALBUM_IMAGE_MIN):
                    extra.append(file.file)
                else:
                    remove_file(file.file)

            path_dst = path
            if album:
                # Get album stat
                stat = {
                    'artist': [],
                    'album': [],
                    'date': [],
                    'titles': [],
                    'track_numbers': [],
                    }
                for info in album.values():
                    # Get album attributes
                    if info['artist'] and info['artist'] not in stat['artist']:
                        stat['artist'].append(info['artist'])
                    if info['album'] and info['album'] not in stat['album']:
                        stat['album'].append(info['album'])
                    if info['date'] and info['date'] not in stat['date']:
                        stat['date'].append(info['date'])

                    # Get track attributes
                    if info['track_number'] and info['track_number'] not in stat['track_numbers']:
                        stat['track_numbers'].append(info['track_number'])
                    if info['title']:
                        stat['titles'].append(info['title'])

                if len(stat['titles']) == len(album) and len(stat['track_numbers']) == len(album):
                    # Rename tracks files
                    for file, info in album.items():
                        track_name = '%02d-%s-%s' % (int(info['track_number']), info['artist'], info['title'])
                        track_name = re.sub(r'\s+', '_', track_name).lower()
                        file_dst = os.path.join(path, track_name + os.path.splitext(file)[1])
                        rename_file(file, file_dst)

                # Get album directory name
                if len(stat['artist']) == len(stat['album']) == 1:
                    album_name = '%s-%s%s' % (stat['artist'][0].capitalize(), stat['album'][0].capitalize(), '-%s' % stat['date'][0] if len(stat['date']) == 1 else '')
                    album_name = re.sub(r'\s+', '_', album_name)

                    # Rename extra files using the album name
                    for file in extra:
                        filename_extra = os.path.basename(file)
                        if not filename_extra.startswith('00-'):
                            file_dst = os.path.join(path, '00-%s-%s' % (album_name.lower(), filename_extra.lower()))
                            rename_file(file, file_dst)

                    # Rename album directory
                    path_dst = rename_file(path, os.path.join(os.path.dirname(path_root), album_name))
                    paths.append(path_dst)

    if os.path.exists(path_root) and path_root not in paths:
        paths.append(path_root)
    return paths

def check_download_file(file, finished_file=None, finished=False):
    '''Check the file and its meta data.

    :param file: download file finished or incomplete
        (if incomplete, also pass the finished_file param)
    :param finished_file: finished file if the incomplete file
        has a different name (e.g.: '.part' extension)
    :param finished: True if the download is finished

    :return: True if the file is valid
    '''
    if not os.path.exists(file):
        return True

    file = get_file(file, real_file=finished_file)
    ext = getattr(file, 'real_ext', file.ext).lower()

    if file.type == 'archive':
        if file.is_main_file() and file.is_protected():
            logger.info('invalid archive %s: password protected', file.file)
            return False

    elif file.type == 'video':
        if not check_size(file.file, size_min=50):
            return True

        info = file.get_file_info()

        # Check extension
        if ext in ('.wmv', '.asf'):
            if info['season'] and info['episode']:
                logger.info('invalid extension "%s" for tvshow %s', ext, file.file)
                return False

        # Check length and bitrate
        if isinstance(info['length'], (int, float)):
            size = get_size(file.file)
            if info['length'] == 0:
                logger.info('invalid length "%s" in %s', info['length'], file.file)
                return False
            else:
                bitrate = size * 8 / info['length']
                if not 300 < bitrate < 10000:
                    logger.info('invalid bitrate "%s" in %s', bitrate, file.file)
                    return False
        elif finished:
            logger.info('failed to get length from %s', file.file)
            return False

        # Check codec
        if info['video_codec']:
            if RE_BAD_CODEC.search(info['video_codec']):
                logger.info('invalid video codec "%s" in %s', info['video_codec'], file.file)
                return False
        elif finished:
            logger.info('failed to get video codec from %s', file.file)
            return False

        if info['audio_codec']:
            if RE_BAD_CODEC.search(info['audio_codec']):
                logger.info('invalid audio codec "%s" in %s', info['audio_codec'], file.file)
                return False
        elif finished:
            logger.info('failed to get audio codec from %s', file.file)
            return False

        # Check fourcc
        if info['video_fourcc']:
            if RE_BAD_CODEC.search(info['video_fourcc']):
                logger.info('invalid video fourcc "%s" in %s', info['video_fourcc'], file.file)
                return False
        elif finished:
            logger.info('failed to get video fourcc from %s', file.file)
            return False

        if info['audio_fourcc']:
            if RE_BAD_CODEC.search(info['audio_fourcc']):
                logger.info('invalid audio fourcc "%s" in %s', info['audio_fourcc'], file.file)
                return False
        elif finished:
            logger.info('failed to get audio fourcc from %s', file.file)
            return False

    return True

def check_download(file):
    '''Check a download file or directory.
    '''
    for file in iter_files(file):
        if not check_download_file(file):
            return False
    return True
