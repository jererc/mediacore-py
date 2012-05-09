from mediacore.util.db import get_db


class Base(object):
    COL = None

    def __init__(self):
        self.col = get_db()[self.COL]

    def insert(self, *args, **kwargs):
        return self.col.insert(*args, **kwargs)

    def find_one(self, *args, **kwargs):
        return self.col.find_one(*args, **kwargs)

    def find(self, *args, **kwargs):
        return self.col.find(*args, **kwargs)

    def update(self, *args, **kwargs):
        return self.col.update(*args, **kwargs)

    def remove(self, *args, **kwargs):
        return self.col.remove(*args, **kwargs)

    def drop(self, *args, **kwargs):
        return self.col.drop(*args, **kwargs)
