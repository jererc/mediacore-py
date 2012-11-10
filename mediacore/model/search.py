from datetime import datetime

from mediacore.utils.db import Model


EXTRA_KEYS = ['album', 'season', 'episode']


class Search(Model):
    COL = 'searches'

    @classmethod
    def add(cls, name, category, mode='once', langs=None, **kwargs):
        doc = {
            'name': name.lower(),
            'category': category.lower(),
            'mode': mode.lower(),
            'langs': langs or [],
            }
        for key in EXTRA_KEYS:
            if key in kwargs:
                doc[key] = kwargs[key]

        if not cls.find_one(doc):
            doc.update(kwargs)
            doc['created'] = datetime.utcnow()
            return cls.insert(doc, safe=True)

    @classmethod
    def get_query(cls, search):
        query = search['name']

        if search.get('episode'):
            extra = '%02d' % search['episode']
            if search.get('season'):
                extra = '%sx%s' % (search['season'], extra)
            query = '%s %s' % (query, extra)

        elif search.get('album'):
            query = '%s %s' % (query, search['album'])

        return query

    @classmethod
    def get_next(cls, search, mode='episode'):
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
