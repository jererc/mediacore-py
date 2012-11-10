from pymongo.objectid import ObjectId

from mediacore.utils.db import Model


class Worker(Model):
    COL = 'workers'

    @classmethod
    def get(cls, worker):
        '''Get the worker document.
        Create one if it does not exist.

        :param worker: worker name
        '''
        doc = cls.find_one({'worker': worker})
        if not doc:
            doc = {
                '_id': ObjectId(),
                'worker': worker,
                }
            cls.save(doc, safe=True)
        return doc

    @classmethod
    def get_attr(cls, worker, attr, default=None):
        '''Get an attribute.
        '''
        config = cls.get(worker)
        return config.get(attr, default)

    @classmethod
    def set_attr(cls, worker, attr, value):
        '''Set an attribute.
        '''
        config = cls.get(worker)
        cls.update({'_id': config['_id']}, {'$set': {attr: value}}, safe=True)
