import os.path
from datetime import datetime

from mediacore.utils.db import Model

from filetools.media import files, get_file, get_mtime
from filetools.title import Title, clean


TYPES = ['video', 'audio']


class Media(Model):
    COL = 'media'

    @classmethod
    def add(cls, file):
        '''Add a file or path.
        '''
        for file_ in files(file, types=TYPES):
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
    def get_bases(cls, id, dirs_only=False):
        '''Get the Media base directories or files.
        '''
        media = cls.get(id)
        if media:
            files = dict([(os.path.dirname(f), f) for f in media['files'] if os.path.exists(f)]).values()
            res = [get_file(f).get_base() for f in files]
            if dirs_only:
                res = [f for f in res if os.path.isdir(f)]
            if res:
                return list(set(res))

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
            spec['info.name'] = {'$regex': name_.get_search_pattern('__all__'), '$options': 'i'}
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
        files = []
        for res in cls.search(*args, **kwargs):
            files.extend(res['files'])
        return files

    @classmethod
    def get_search(cls, media):
        category = media['info']['subtype']
        if category == 'tv':
            name = media['info']['name']
        elif category == 'music':
            name = media['info']['artist']
        else:
            name = media['info']['full_name']
        res = {
            'name': name,
            'category': category,
            'media_id': media['_id'],
            }
        return res
