from datetime import datetime

from mediacore.utils.db import Model


class Notification(Model):
    COL = 'notifications'

    @classmethod
    def add(cls, message, **kwargs):
        doc = {
            'message': message,
            'created': datetime.utcnow(),
            }
        if kwargs:
            doc.update(kwargs)
        return cls.insert(doc, safe=True)
