from datetime import datetime

from mediacore.model import Base


class Similar(Base):
    COL = 'similar'

    def add(self, **doc):
        if not self.find_one(doc):
            doc['created'] = datetime.utcnow()
            return self.insert(doc, safe=True)
