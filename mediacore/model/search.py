from datetime import datetime

from mediacore.model import Base


EXTRA_KEYS = ['album', 'season', 'episode']


class Search(Base):
    COL = 'searches'

    def add(self, name, category, mode='once', langs=None, **kwargs):
        doc = {
            'name': name.lower(),
            'category': category.lower(),
            'mode': mode.lower(),
            'langs': langs or [],
            }
        for key in EXTRA_KEYS:
            if key in kwargs:
                doc[key] = kwargs[key]

        if not self.find_one(doc):
            doc.update(kwargs)
            doc['created'] = datetime.utcnow()
            return self.insert(doc, safe=True)

    def get_query(self, search):
        query = search['name']

        if search.get('episode'):
            extra = '%02d' % search['episode']
            if search.get('season'):
                extra = '%sx%s' % (search['season'], extra)
            query = '%s %s' % (query, extra)

        elif search.get('album'):
            query = '%s %s' % (query, search['album'])

        return query

    def get_next(self, search, mode='episode'):
        res = {
            'name': search['name'],
            'category': search['category'],
            'mode': search['mode'],
            'langs': search.get('langs') or [],
            }
        for key in EXTRA_KEYS:
            if key in search:
                res[key] = search[key]

        if mode == 'episode' and res.get('episode'):
            res['episode'] += 1
            return res
        elif mode == 'season' and res.get('season'):
            res['season'] += 1
            res['episode'] = 1
            return res
