from datetime import datetime

from mediacore.utils.db import Model


class Sync(Model):
    COL = 'syncs'

    @classmethod
    def add(cls, username, password, media_id, dst, parameters=None):
        doc = {
            'username': username,
            'password': password,
            'dst': dst,
            'parameters': parameters or {},
            }
        if media_id:
            doc['media_id'] = media_id
        if not cls.find_one(doc):
            doc['created'] = datetime.utcnow()
            return cls.insert(doc, safe=True)
