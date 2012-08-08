from datetime import datetime

from mediacore.model import Base


class Sync(Base):
    COL = 'syncs'

    def add(self, username, password, src, dst, parameters=None):
        doc = {
            'username': username,
            'password': password,
            'src': src,
            'dst': dst,
            'parameters': parameters or {},
            }
        if not self.find_one(doc):
            doc['created'] = datetime.utcnow()
            return self.insert(doc, safe=True)
