from pymongo import Connection


_connection_uri = 'mongodb://localhost'
_connection = None

_db_name = None
_db = None


class ConnectionError(Exception): pass


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
