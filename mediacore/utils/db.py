from pymongo import Connection
from pymongo.objectid import ObjectId


_connection_uri = 'mongodb://localhost'
_connection = None

_db_name = None
_db = None


class ConnectionError(Exception): pass


class Model(object):

    def __init__(self):
        col_name = getattr(self, 'COL', None) or self.__class__.__name__.lower()
        self.col = get_db()[col_name]

    @classmethod
    def save(cls, *args, **kwargs):
        return cls().col.save(*args, **kwargs)

    @classmethod
    def insert(cls, *args, **kwargs):
        return cls().col.insert(*args, **kwargs)

    @classmethod
    def find_one(cls, *args, **kwargs):
        return cls().col.find_one(*args, **kwargs)

    @classmethod
    def find(cls, *args, **kwargs):
        return cls().col.find(*args, **kwargs)

    @classmethod
    def find_and_modify(cls, *args, **kwargs):
        return cls().col.find_and_modify(*args, **kwargs)

    @classmethod
    def update(cls, *args, **kwargs):
        return cls().col.update(*args, **kwargs)

    @classmethod
    def remove(cls, *args, **kwargs):
        return cls().col.remove(*args, **kwargs)

    @classmethod
    def drop(cls, *args, **kwargs):
        return cls().col.drop(*args, **kwargs)

    @classmethod
    def get(cls, id=None, **kwargs):
        spec = {}
        if id:
            spec['_id'] = ObjectId(id)
        spec.update(kwargs)
        return cls().col.find_one(spec)


def _get_connection():
    global _connection, _connection_uri
    # Connect to the database if not already connected
    if _connection is None:
        _connection = Connection(host=_connection_uri)
    return _connection

def get_db():
    global _db, _connection
    # Connect if not already connected
    if _connection is None:
        _connection = _get_connection()

    if _db is None:
        if _db_name is None:
            raise ConnectionError('Not connected to the database')
        _db = _connection[_db_name]

    return _db

def connect(db=None, uri='mongodb://localhost'):
    global _connection_uri, _db_name, _connection

    _connection_uri = uri
    if not db:
        raise ConnectionError('No database chosen')
    _db_name = db
    return _get_connection()
