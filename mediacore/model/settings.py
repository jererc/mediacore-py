from mediacore.utils.db import Model


DEFAULTS = {
    'paths': {
        'media_root': '/home/user',
        'media_root_exclude': [],
        'media': {
            'video': '/home/user/video/new',
            'audio': '/home/user/audio/new',
            'image': '/home/user/image/new',
            'misc': '/home/user/misc/new',
            },
        'finished_download': '/home/user/finished',
        'tmp': '/tmp',
        },
    'search_filters': {
        'anime': {'size_min': 100, 'size_max': 2000, 'exclude_raw': '\\b1080p\\b'},
        'apps': {},
        'books': {},
        'games': {},
        'movies': {'size_min': 500, 'size_max': 3000, 'include_raw': '\\b(br|bd|dvd|hd)rip\\b', 'exclude_raw': '\\b1080p\\b'},
        'music': {'size_min': 20, 'size_max': 500},
        'tv': {'size_min': 100, 'size_max': 2000, 'include_raw': '\\b([hp]dtv|dsr(ip)?)\\b', 'exclude_raw': '\\b1080p\\b'},
        },
    'media_filters': {
        'metacritic': {'rating': {'min': 65}},
        'imdb': {'genre': {'exclude': ['horror']}, 'rating': {'min': 6.5}},
        'tvrage': {'genre': {'exclude': ['teens', 'soaps']}, 'classification': {'include': ['scripted']}},
        'sputnikmusic': {'genre': {'exclude': ['hip hop', 'rap']}, 'rating': {'min': 3.5}},
        'lastfm': {'genre': {'exclude': ['hip hop', 'rap']}},
        },
    'media_langs': {'movies': ['en'], 'tv': ['en']},
    'subtitles_langs': ['en'],
    'opensubtitles': {'username': '', 'password': ''},
    'netflix': {'username': '', 'password': ''},
    'filestube': {'api_key': ''},
    'rutracker': {'username': '', 'password': ''},
    'sync': {'recurrence': 240, 'retry_delta': 30},
    }


class Settings(Model):
    COL = 'settings'

    @classmethod
    def get_settings(cls, section, key=None, default=None):
        res = cls.find_one({'section': section}) or {}
        settings = res.get('settings', DEFAULTS.get(section, {}))
        return settings.get(key, default) if key else settings

    @classmethod
    def set_setting(cls, section, key, value):
        cls.update({'section': section},
                {'$set': {'section': section, 'settings.%s' % key: value}},
                upsert=True, safe=True)

    @classmethod
    def set_settings(cls, section, settings, overwrite=False):
        doc = {
            'section': section,
            'settings': settings,
            }
        cls.update({'section': section},
                doc if overwrite else {'$set': doc}, upsert=True, safe=True)
