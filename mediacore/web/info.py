from mediacore.web.imdb import Imdb
from mediacore.web.tvrage import Tvrage
from mediacore.web.sputnikmusic import Sputnikmusic
from mediacore.web.lastfm import Lastfm
from mediacore.web.youtube import Youtube

from mediacore.util.title import Title
from mediacore.util.filter import validate_info
from mediacore.util.util import randomize


class InfoException(Exception): pass


def get_movies_titles(name):
    '''Get movies titles from a director or actor.
    '''
    imdb = Imdb()
    if not imdb.url:
        raise InfoException('failed to connect to imdb')

    info = imdb.get_info(name, type='name') or {}
    movies_info = info.get('titles_known_for', [])

    return list(set([a['title'] for a in movies_info]))

def get_music_albums(band):
    '''Get albums from a music band.
    '''
    sputnikmusic = Sputnikmusic()
    if not sputnikmusic.url:
        raise InfoException('failed to connect to sputnikmusic')
    lastfm = Lastfm()
    if not lastfm.url:
        raise InfoException('failed to connect to lastfm')

    info_sputnikmusic = sputnikmusic.get_info(band) or {}
    info_lastfm = lastfm.get_info(band) or {}
    albums_info = info_lastfm.get('albums', []) + info_sputnikmusic.get('albums', [])

    return list(set([a['name'] for a in albums_info]))

def similar_movies(query, type='title', year=None, randomized=True,
            filters=None):
    '''Iterate over similar movies from a director, actor or movie title.
    '''
    imdb = Imdb()
    similar_movies = imdb.get_similar(query, type=type, year=year)
    if randomized:
        similar_movies = randomize(similar_movies)

    for movie_info in similar_movies:
        info = imdb.get_info(url=movie_info['url']) or {}
        if filters and not validate_info(info, filters['imdb']):
            continue
        yield movie_info['title']

def similar_music(band, randomized=True, filters=None):
    '''Iterate over similar artists albums from a music band.
    '''
    objects = (Sputnikmusic(), Lastfm())
    similar_bands = []
    for obj in objects:
        res = obj.get_similar(band)
        if res:
            similar_bands.extend(res)

    similar_bands = list(set(similar_bands))
    if randomized:
        similar_bands = randomize(similar_bands)

    for similar_band in similar_bands:
        albums_names = []

        for obj in objects:
            info = obj.get_info(similar_band) or {}
            albums = info.get('albums')
            if not albums:
                continue
            if randomized:
                albums = randomize(albums)

            type = obj.__class__.__name__.lower()
            for album_info in albums:
                if album_info['name'] in albums_names:
                    continue
                albums_names.append(album_info['name'])

                if filters and not validate_info(album_info, filters[type]):
                    continue
                yield (similar_band, album_info['name'])

def search_extra(obj):
    '''Get an object extra info.
    '''
    extra = {}

    info = obj.get('info', {})
    category = info.get('subtype') or obj.get('category')

    if category in ('movies', 'tv', 'anime'):

        if category in ('tv', 'anime'):
            name = info.get('name') or obj.get('name')
            extra['tvrage'] = Tvrage().get_info(name) or {}
        else:
            name = info.get('full_name') or obj.get('name')

        # Get date
        if obj.get('release'):
            date = Title(obj['release']).date
        elif obj.get('date'):
            date = obj['date'].year
        else:
            date = info.get('date')

        extra['imdb'] = Imdb().get_info(name, year=date) or {}

        date = extra.get('tvrage', {}).get('date') or extra['imdb'].get('date') or date
        extra['youtube'] = Youtube().get_trailer(name, date=date) or {}

    elif category == 'music':
        artist = info.get('artist') or obj.get('artist') or obj.get('name')
        album = info.get('album') or obj.get('album')

        extra['sputnikmusic'] = Sputnikmusic().get_info(artist, album) or {}
        extra['lastfm'] = Lastfm().get_info(artist, album) or {}
        extra['youtube'] = Youtube().get_track(artist, album) or {}

    return extra

def _get_rating_str(extra):
    if 'imdb' in extra:
        rating = extra['imdb'].get('rating')
        if rating is not None:
            return '%s/10' % rating

    elif 'sputnikmusic' in extra:
        rating = extra['sputnikmusic'].get('rating')
        if rating is not None:
            return '%s/5' % rating

def _get_clean_extra(extra):
    res = {}

    for type, info in extra.items():
        res.setdefault(type, {})

        for key in ('date', 'rating', 'classification', 'genre', 'country',
                'network', 'next_episode', 'director', 'stars', 'airs',
                'runtime', 'title'):
            val = info.get(key)
            if isinstance(val, (tuple, list)):
                val = ', '.join(val)
            res[type][key] = val

    return res

def get_info(obj):
    '''Get an object info.
    '''
    extra = obj.get('extra', {})
    category = obj.get('info', {}).get('subtype') or obj.get('category')
    info = {
        'category': category,
        'url_thumbnail': extra.get('youtube', {}).get('urls_thumbnails', [None])[0],
        'url_watch': extra.get('youtube', {}).get('url_watch'),
        'rating': _get_rating_str(extra),
        'extra': _get_clean_extra(extra),
        }

    if category == 'movies':
        info['url_info'] = extra.get('imdb', {}).get('url')

    elif category == 'tv':
        info['url_info'] = extra.get('tvrage', {}).get('url') or extra.get('imdb', {}).get('url')

    elif category == 'music':
        info['url_info'] = extra.get('sputnikmusic', {}).get('url') or extra.get('lastfm', {}).get('url')
        info['url_thumbnail'] = extra.get('sputnikmusic', {}).get('url_cover') or info['url_thumbnail']

    return info
