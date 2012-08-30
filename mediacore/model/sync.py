from datetime import datetime

from mediacore.model import Base


class Sync(Base):
    COL = 'syncs'

    def add(self, username, password, media_id, dst, parameters=None):
        doc = {
            'username': username,
            'password': password,
            'dst': dst,
            'parameters': parameters or {},
            }
        if media_id:
            doc['media_id'] = media_id
        if not self.find_one(doc):
            doc['created'] = datetime.utcnow()
            return self.insert(doc, safe=True)
