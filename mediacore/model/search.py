from pymongo.objectid import ObjectId

from mediacore.model import Base
from mediacore.util.title import Title


class Search(Base):
    COL = 'searches'

    def add(self, q, category, mode='once', langs=None, pages_max=1):
        q = q.lower()
        category = category.lower()
        if not langs:
            langs = []

        search = {
            'q': q,
            'category': category,
            'mode': mode,
            'langs': langs,
            'pages_max': pages_max,
            }
        res = self.get(q=q, category=category)
        if res:
            self.update(res['_id'], info=search)
        else:
            self.col.insert(search, safe=True)

    def get(self, id=None, q=None, category=None):
        spec = {}
        if id:
            spec['_id'] = ObjectId(id)
        if q:
            spec['q'] = q
        if category:
            spec['category'] = category
        return self.col.find_one(spec)

    def update(self, id=None, q=None, category=None, spec=None, info=None):
        if not info:
            return

        if not spec:
            spec = {}
        if id:
            spec['_id'] = ObjectId(id)
        if q:
            spec['q'] = q
        if category:
            spec['category'] = category
        self.col.update(spec, {'$set': info}, safe=True, multi=True)

    def remove(self, id=None, q=None, category=None, spec=None):
        if not spec:
            spec = {}
        if id:
            spec['_id'] = ObjectId(id)
        if q:
            spec['q'] = q
        if category:
            spec['category'] = category
        return self.col.remove(spec, safe=True)

    def remove_all(self, name, category):
        '''Remove all searches matching the name and category.

        :param name: search name (e.g.: tv show or anime title)
        '''
        ids = []
        for search in self.col.find({'category': category}):
            if search['category'] in ('tv', 'anime'):
                search_name = Title(search['q']).name
            else:
                search_name = search['q'].lower()

            if search_name == name:
                ids.append(search['_id'])

        if ids:
            self.col.remove({'_id': {'$in': ids}}, safe=True)

    def list_names(self):
        '''Get searches names by category.
        '''
        res = {}
        for search in self.col.find():
            res.setdefault(search['category'], [])

            if search['category'] in ('tv', 'anime'):
                name = Title(search['q']).name
            else:
                name = search['q'].lower()
            res[search['category']].append(name)

        return res

    def get_next_episode(self, query):
        '''Get the query for the next episode.
        '''
        title = Title(query)
        if title.episode_alt:   # we do not consider the season (e.g.: anime episodes)
            episode_new = str(int(title.episode_alt) + 1).zfill(len(title.episode_alt))
            return '%s %s' % (title.name, episode_new)
        elif title.episode:
            episode_new = str(int(title.episode) + 1).zfill(len(title.episode))
            season_str = '%sx' % title.season if title.season else ''
            return '%s %s%s' % (title.name, season_str, episode_new)

    def get_next_season(self, query):
        '''Get the query for the next season (first episode).
        '''
        title = Title(query)
        if title.season and title.episode and not title.episode_alt:
            return '%s %sx01' % (title.name, str(int(title.season) + 1))
