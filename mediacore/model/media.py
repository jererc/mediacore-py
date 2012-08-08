import os.path
from datetime import datetime

from mediacore.model import Base
from mediacore.util.media import files, get_file
from mediacore.util.title import clean


TYPES = ['video', 'audio']


class Media(Base):
    COL = 'media'

    def add(self, file):
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
            res = self.update({'$or': [
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
                self.insert(doc, safe=True)

    def get_bases(self, id, dirs_only=False):
        '''Get the Media base directories or files.
        '''
        media = Media().get(id)
        if media:
            files = dict([(os.path.dirname(f), f) for f in media['files'] if os.path.exists(f)]).values()
            res = [get_file(f).get_base() for f in files]
            if dirs_only:
                res = [f for f in res if os.path.isdir(f)]
            if res:
                return list(set(res))

    def search(self, name, category, **kwargs):
        '''Get media matching the parameters.
        '''
        spec = {'info.subtype': category}

        if category == 'movies':
            spec['info.full_name'] = clean(name, 1)

        elif category in ('tv', 'anime'):
            spec['info.subtype'] = 'tv'
            spec['info.name'] = clean(name, 1)
            if kwargs.get('season'):
                spec['info.season'] = str(kwargs['season'])
            if kwargs.get('episode'):
                spec['info.episode'] = {'$regex': '^0*%s$' % kwargs['episode']}

        elif category == 'music':
            spec['info.artist'] = clean(name, 1)
            if kwargs.get('album'):
                spec['info.album'] = clean(kwargs['album'], 1)

        return list(self.find(spec))

    def search_files(self, *args, **kwargs):
        files = []
        for res in self.search(*args, **kwargs):
            files.extend(res['files'])
        return files
