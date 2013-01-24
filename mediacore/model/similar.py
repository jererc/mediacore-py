from datetime import datetime

from mediacore.utils.db import Model


class SimilarSearch(Model):
    COL = 'similar.searches'

    @classmethod
    def add(cls, name, category, **kwargs):
        doc = {
            'name': name.lower(),
            'category': category.lower(),
            }
        if not cls.find_one(doc):
            doc.update(kwargs)
            doc['created'] = datetime.utcnow()
            return cls.insert(doc, safe=True)


class SimilarResult(Model):
    COL = 'similar.results'
