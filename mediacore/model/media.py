import os.path
from datetime import datetime
import logging

from mediacore.utils.db import Model

from filetools.media import files, get_file, get_mtime
from filetools.title import Title


TYPES_DEF = {
    'movies': 'video',
    'tv': 'video',
    'anime': 'video',
    'music': 'audio',
    }

logger = logging.getLogger(__name__)


class Media(Model):
    COL = 'media'

    @classmethod
    def add_file(cls, file):
        '''Add a file or path.
        '''
        types = list(set(TYPES_DEF.values()))
        for file_ in files(file, types=types):
            info = file_.get_file_info()
            name = info.get('display_name')
            if not name:
                continue

            doc = {
                'name': name,
                'type': file_.type,
                'info': info,
                }
            res = cls.update({'$or': [
                    {'files': file_.file},
                    {'name': name},
                    ]},
                    {
                    '$set': doc,
                    '$addToSet': {'files': file_.file},
                    }, safe=True)
            if not res['updatedExisting']:
                doc['files'] = [file_.file]
                doc['created'] = datetime.utcnow()
                doc['date'] = get_mtime(file_.file)
                cls.insert(doc, safe=True)

    @classmethod
    def add_url(cls, url, name, category, **kwargs):
        '''Add a URL.
        '''
        type = TYPES_DEF.get(category)
        if not type:
            logger.error('invalid category "%s"' % category)
            return

        info = {}

        title = Title(name)
        for key in ('full_name', 'display_name', 'name',
                'season', 'episode', 'date', 'rip', 'langs'):
            info[key] = getattr(title, key)
        info['subtype'] = category
        info.update(kwargs)
        name = info.get('display_name')
        if not name:
            return

        doc = {
            'name': name,
            'type': type,
            'info': info,
            }
        res = cls.update({'$or': [
                {'urls': url},
                {'name': name},
                ]},
                {
                '$set': doc,
                '$addToSet': {'urls': url},
                }, safe=True)
        if not res['updatedExisting']:
            doc['urls'] = [url]
            doc['created'] = datetime.utcnow()
            doc['date'] = datetime.utcnow()
            cls.insert(doc, safe=True)

    @classmethod
    def get_bases(cls, id, dirs_only=False):
        '''Get the Media base directories or files.
        '''
        media = cls.get(id) or {}
        files = media.get('files', [])
        res = list(set([get_file(f).get_base() for f in files]))
        if dirs_only:
            return [f for f in res if os.path.isdir(f)]
        return res

    @classmethod
    def search(cls, name, category, **kwargs):
        '''Get media matching the parameters.
        '''
        spec = {'info.subtype': category}
        name_ = Title(name)

        if category == 'movies':
            spec['info.full_name'] = {'$regex': name_.get_search_pattern(), '$options': 'i'}

        elif category in ('tv', 'anime'):
            spec['info.subtype'] = 'tv'
            spec['info.name'] = {'$regex': name_.get_search_pattern(category='tv'), '$options': 'i'}
            if kwargs.get('season'):
                spec['info.season'] = str(kwargs['season'])
            if kwargs.get('episode'):
                spec['info.episode'] = {'$regex': '^0*%s$' % kwargs['episode']}

        elif category == 'music':
            spec['info.artist'] = {'$regex': name_.get_search_pattern(), '$options': 'i'}
            if kwargs.get('album'):
                album_ = Title(kwargs['album'])
                spec['info.album'] = {'$regex': album_.get_search_pattern(), '$options': 'i'}

        return list(cls.find(spec))

    @classmethod
    def search_files(cls, *args, **kwargs):
        '''Get the media files and URLs matching the parameters.
        '''
        res = []
        for media in cls.search(*args, **kwargs):
            res.extend(media.get('files', []))
            res.extend(media.get('urls', []))
        return res

    @classmethod
    def get_search(cls, media):
        res = {
            'category': media['info']['subtype'],
            'media_id': media['_id'],
            }
        if res['category'] == 'tv':
            res['name'] = media['info']['name']
            if media['info']['season']:
                res['season'] = int(media['info']['season'])
            if media['info']['episode']:
                res['episode'] = int(media['info']['episode'])
        elif res['category'] == 'music':
            res['name'] = media['info']['artist']
            res['album'] = media['info']['album']
        else:
            res['name'] = media['info']['full_name']
        return res
