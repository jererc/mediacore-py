from datetime import datetime

from mediacore.model import Base


class Similar(Base):
    COL = 'similar'

    def add(self, paths, category, recurrence, **kwargs):
        doc = {
            'paths': paths,
            'category': category,
            'recurrence': recurrence,
            }
        doc.update(kwargs)
        if not self.find_one(doc):
            doc['created'] = datetime.utcnow()
            return self.insert(doc, safe=True)
