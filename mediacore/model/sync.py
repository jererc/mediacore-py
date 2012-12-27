from datetime import datetime

from mediacore.utils.db import Model


class Sync(Model):
    COL = 'syncs'

    @classmethod
    def add(cls, user, category, dst='', parameters=None):
        doc = {
            'user': user,
            'category': category,
            'dst': dst,
            'parameters': parameters or {},
            }
        if not cls.find_one(doc):
            doc['created'] = datetime.utcnow()
            return cls.insert(doc, safe=True)
