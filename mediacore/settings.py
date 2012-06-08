OPENSUBTITLES_USERNAME = ''
OPENSUBTITLES_PASSWORD = ''


TRANSMISSION_HOST = 'localhost'
TRANSMISSION_PORT = 9091
TRANSMISSION_USERNAME = None
TRANSMISSION_PASSWORD = None


# Import local settings
try:
    from local_settings import *
except ImportError:
    pass
