from mediacore.model import Base


class Worker(Base):
    COL = 'workers'

    def get(self, worker):
        '''Get the worker document.
        Create one if it does not exist.

        :param worker: worker name
        '''
        res = self.find_one({'worker': worker})
        if not res:
            id = self.insert({'worker': worker}, safe=True)
            res = self.find_one({'_id': id})

        return res

    def get_attr(self, worker, attr, default=None):
        '''Get an attribute.
        '''
        config = self.get(worker)
        return config.get(attr, default)

    def set_attr(self, worker, attr, value):
        '''Set an attribute.
        '''
        config = self.get(worker)
        self.update({'_id': config['_id']}, {'$set': {attr: value}}, safe=True)
