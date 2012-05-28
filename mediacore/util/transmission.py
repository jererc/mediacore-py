import os
import re
from datetime import datetime
import logging

import transmissionrpc

from mediacore.util import media as mmedia
from mediacore.util.title import clean
from mediacore.util.download import check_download_file


RE_DUPLICATE = re.compile(r'\bduplicate\storrent\b', re.I)


logger = logging.getLogger(__name__)


class TransmissionError(Exception): pass
class TorrentExists(Exception): pass


class Transmission(object):
    def __init__(self, host='localhost', port=9091, username=None, password=None):
        try:
            self.client = transmissionrpc.Client(host, port=port, user=username, password=password)
            self.logged = True
            self.download_dir = self.client.get_session().download_dir
        except Exception, e:
            self.logged = False
            logger.error('failed to connect to the transmission rpc server: %s', e)

    def torrents(self):
        '''Iterate torrents.
        '''
        for id in self.client.list():
            res = self.get(id)
            if res:
                yield res

    def get(self, id):
        '''Get a torrent.

        :param id: transmission id or torrent hash
        '''
        try:
            res = self.client.info(id).items()[0][1]
        except Exception:
            return
        if not res:
            return

        info = {
            'hash': res.hashString.lower(),
            'id': res.id,
            'name': res.name,
            'error_string': res.errorString,
            'status': res.status,
            'torrent_file': res.torrentFile,
            'files': [f['name'] for f in res.files().values()],
            'date_added': res.date_added,
            'progress': res.progress,
            'size': res.totalSize,
            }
        return info

    def add(self, url, delete_torrent=True):
        '''Add a torrent.

        :return: torrent hash
        '''
        try:
            res = self.client.add_uri(url)
        except Exception, e:
            if RE_DUPLICATE.search(e.message):
                raise TorrentExists('url %s is already queued' % url)
            raise TransmissionError('failed to add url %s: %s' % (url, e))

        if os.path.isfile(url) and delete_torrent:
            mmedia.remove_file(url)

        try:
            id = res.items()[0][0]
            return self.get(id)['hash'].lower()
        except Exception, e:
            logger.error('failed to get torrent hash for url %s', url)

    def remove(self, id, delete_data=False):
        '''Remove a torrent.

        :param id: transmission id or torrent hash

        :return: True if successful
        '''
        res = self.get(id)
        if not res:
            return
        if delete_data and not res['files']:    # remove requests fail for magnet links without metadata yet
            delete_data = False

        try:
            self.client.remove(id, delete_data=delete_data)
        except Exception:
            logger.exception('exception')
            return
        return True

    def watch(self, dst, dst_invalid=None, age_max=None, callable=None):
        '''Watch torrents and move finished downloads to the destination.

        :param dst: destination root directory
        :param dst_invalid: destination directory for invalid files
        :param age_max: timedelta
        :param callable: callable
        '''
        for torrent in self.torrents():

            if not self._check_torrent_files(torrent):
                if torrent['progress'] == 100 and dst_invalid \
                        and not self._move_torrent_files(torrent, dst_invalid):
                    continue
                if not self.remove(torrent['id'], delete_data=True):
                    continue
                logger.info('removed invalid torrent "%s" (%s%% done)', torrent['name'], int(torrent['progress']))

            elif torrent['progress'] == 100:
                if callable and not callable(torrent):
                    continue

                destination = self._get_destination_dir(torrent, dst)
                if not self._move_torrent_files(torrent, destination):
                    continue
                if not self.remove(torrent['id']):
                    continue
                logger.info('removed finished torrent "%s"', torrent['name'])

            elif age_max and torrent['date_added'] < datetime.utcnow() - age_max:
                if self.remove(torrent['id'], delete_data=True):
                    logger.info('removed obsolete torrent "%s" (added %s)', torrent['name'], torrent['date_added'])

    def clean_download_directory(self):
        '''Clean download directory.
        '''
        files_queued = []
        for torrent in self.torrents():
            for file in torrent['files']:
                files_queued.append(os.path.join(self.download_dir, file))

        # Remove files not queued
        for file in mmedia.iter_files(self.download_dir):
            file_source, ext = os.path.splitext(file)
            if ext == '.part' and file_source in files_queued:
                continue
            elif os.path.isfile(file) and file not in files_queued:
                if mmedia.remove_file(file):
                    logger.info('removed file %s: not queued', file.encode('utf-8'))

        # Remove empty directories not queued
        for path in mmedia.iter_files(self.download_dir, incl_files=False, incl_dirs=True):
            if not os.listdir(path) and not self._is_dir_queued(path, files_queued):
                if mmedia.remove_file(path):
                    logger.info('removed empty directory %s: not queued', path.encode('utf-8'))

    def _check_torrent_files(self, torrent):
        finished = torrent['progress'] == 100
        for file in torrent['files']:
            file = os.path.join(self.download_dir, file)
            if not check_download_file(file + '.part', finished_file=file, finished=finished):
                return
            elif not check_download_file(file, finished=finished):
                return
        return True

    def _get_destination_dir(self, torrent, dst):
        '''Get the base directory where to move the torrent files.
        '''
        root_files = [f for f in torrent['files'] if '/' not in f]
        if not root_files:
            base_dirs = set([r.split('/')[0] for r in torrent['files']])
            if len(base_dirs) == 1:
                return dst
        return os.path.join(dst, clean(torrent['name']))

    def _move_torrent_files(self, torrent, dst):
        '''Move files to the destination directory.

        :param torrent: torrent
        :param dst: destination root directory

        :return: True if successful
        '''
        res = True
        for file in torrent['files']:
            src = os.path.join(self.download_dir, file)
            if os.path.isfile(src):
                dst_dir = os.path.dirname(os.path.join(dst, file))
                if not mmedia.move_file(src, dst_dir):
                    res = False
        return res

    def _is_dir_queued(self, directory, files):
        for file in files:
            if file.startswith('%s/' % directory):
                return True

    def import_torrents(self, src, recursive=False):
        '''Import torrents files from a directory.

        :param src: source directory
        '''
        for file in mmedia.files(src, recursive=recursive):
            filename = file.file.encode('utf-8')

            # Remove automatically imported torrents
            if file.ext.lower() == '.added':
                mmedia.remove_file(file.file)
                logger.info('removed already imported torrent file %s', filename)

            # Add new torrents
            if file.ext.lower() == '.torrent':
                try:
                    self.add(file.file)
                    logger.info('imported torrent file %s', filename)
                except TorrentExists, e:
                    mmedia.remove_file(file.file)
                    logger.info('removed torrent file %s: %s', filename, e)
                except TransmissionError, e:
                    logger.error('failed to import torrent file %s: %s', filename, e)
