from datetime import datetime

from mediacore.utils.db import Model


class Sync(Model):
    COL = 'syncs'

    @classmethod
    def add(cls, user, dst, media_id=None, parameters=None):
        doc = {
            'user': user,
            'dst': dst,
            'parameters': parameters or {},
            }
        if media_id:
            doc['media_id'] = media_id
        if not cls.find_one(doc):
            doc['created'] = datetime.utcnow()
            return cls.insert(doc, safe=True)
