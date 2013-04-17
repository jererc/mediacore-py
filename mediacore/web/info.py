from mediacore.web.imdb import Imdb
from mediacore.web.tvrage import Tvrage
from mediacore.web.sputnikmusic import Sputnikmusic
from mediacore.web.lastfm import Lastfm
from mediacore.web.youtube import Youtube

from filetools.title import Title

from mediacore.utils.filter import validate_info
from mediacore.utils.utils import randomize


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
    albums_info = info_sputnikmusic.get('albums', []) + info_lastfm.get('albums', [])

    return list(set([a['name'] for a in albums_info]))

def similar_movies(query, type='title', year=None, filters=None,
        randomize_titles=True):
    '''Iterate over similar movies from a director, actor or movie title.
    '''
    imdb = Imdb()
    similar_movies = imdb.get_similar(query, type=type, year=year)
    if not similar_movies:
        return
    if randomize_titles:
        similar_movies = randomize(similar_movies)

    for movie_info in similar_movies:
        info = imdb.get_info(url=movie_info['url']) or {}
        if filters and not validate_info(info, filters['imdb']):
            continue
        yield movie_info['title']

def similar_tv(query, years_delta=None, filters=None,
        randomize_titles=True):
    '''Iterate over similar tv shows from a tv show name.
    '''
    tvrage = Tvrage()
    similar_tv = tvrage.get_similar(query, years_delta=years_delta)
    if not similar_tv:
        return
    if randomize_titles:
        similar_tv = randomize(similar_tv)

    for tv_info in similar_tv:
        info = tvrage.get_info(tv_info['url']) or {}
        if filters and not validate_info(info, filters['tvrage']):
            continue
        yield tv_info['title']

def similar_music(band, filters=None,
        randomize_bands=True, randomize_albums=False):
    '''Iterate over similar artists albums from a music band.
    '''
    objects = (Sputnikmusic(), Lastfm())
    similar_bands = []
    for obj in objects:
        res = obj.get_similar(band)
        if res:
            similar_bands.extend([r['title'] for r in res])

    similar_bands = list(set(similar_bands))
    if randomize_bands:
        similar_bands = randomize(similar_bands)

    for similar_band in similar_bands:
        albums_names = []

        for obj in objects:
            info = obj.get_info(similar_band) or {}
            albums = info.get('albums')
            if not albums:
                continue
            if randomize_albums:
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

    def set_extra(key, val):
        extra[key] = val or obj.get('extra', {}).get(key, {})

    info = obj.get('info', {})
    category = info.get('subtype') or obj.get('category')

    if category in ('movies', 'tv', 'anime'):
        if category in ('tv', 'anime'):
            name = info.get('name') or obj.get('name')
            set_extra('tvrage', Tvrage().get_info(name))
        else:
            name = info.get('full_name') or obj.get('name')

        date = None
        if obj.get('release'):
            date = Title(obj['release']).date
        if not date:
            if info.get('date'):
                date = info['date']
            elif obj.get('date'):
                date = obj['date'].year

        set_extra('imdb', Imdb().get_info(name, year=date))
        date = extra.get('tvrage', {}).get('date') or extra['imdb'].get('date') or date
        set_extra('youtube', Youtube().get_trailer(name, date=date))

    elif category == 'music':
        artist = info.get('artist') or obj.get('artist') or obj.get('name')
        album = info.get('album') or obj.get('album')

        set_extra('sputnikmusic', Sputnikmusic().get_info(artist, album))
        set_extra('lastfm', Lastfm().get_info(artist, album))
        set_extra('youtube', Youtube().get_track(artist, album))

    return extra
