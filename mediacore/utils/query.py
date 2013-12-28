import re
import logging

from filetools.title import clean

from mediacore.model.settings import Settings
from mediacore.web.info import get_movies_titles, get_music_albums, InfoError


CAT_DEF = {
    'anime': re.compile(r'\banime\b', re.I),
    'apps': re.compile(r'\bapplications?\b', re.I),
    'books': re.compile(r'\be?books?\b', re.I),
    'games': re.compile(r'\bgames?\b', re.I),
    'movies': re.compile(r'\b(movies?|video)\b', re.I),
    'music': re.compile(r'\b(audio|music)\b', re.I),
    'tv': re.compile(r'\b(tv|tv\s*shows?)\b', re.I),
    }
RE_ARTIST = {
    'movies': re.compile(r'\b(artist|director|actor)\b', re.I),
    'music': re.compile(r'\b(artist|band)\b', re.I),
    }

logger = logging.getLogger(__name__)


class QueryError(Exception): pass


def get_category_info(val):
    for category, re_cat in CAT_DEF.items():
        if re_cat.search(val):
            re_ = RE_ARTIST.get(category)
            return category, re_ and re_.search(val)
    return None, False

def get_movies_searches(artist, langs):
    res = []
    titles = get_movies_titles(artist)
    if not titles:
        logger.info('failed to find movies from "%s"', artist)
    else:
        for title in titles:
            res.append({
                    'name': title,
                    'category': 'movies',
                    'langs': langs,
                    })
    return res

def get_music_searches(artist):
    res = []
    albums = get_music_albums(artist)
    if not albums:
        logger.info('failed to find albums from "%s"', artist)
    else:
        for album in albums:
            res.append({
                    'name': artist,
                    'album': album,
                    'category': 'music',
                    })
    return res

def get_searches(query):
    parts = [v.strip() for v in query.split(',')]
    if len(parts) < 2:
        return []
    category, is_artist = get_category_info(clean(parts.pop(0)))
    if category is None:
        return []
    name = clean(parts.pop(0), 1)
    if not name:
        return []
    artist = name if is_artist else None

    langs = Settings.get_settings('media_langs').get(category, [])
    search = {
        'name': name,
        'category': category,
        'mode': 'once',
        'langs': langs,
        }

    if category == 'music':
        if not parts:
            artist = name
        if artist:
            try:
                return get_music_searches(artist)
            except InfoError, e:
                raise QueryError('failed to find albums from "%s": %s', artist, str(e))

        search['album'] = clean(parts.pop(0), 1)
        if not search['album']:
            raise QueryError('failed to parse query "%s": album name is missing', query)

    elif category == 'movies':
        if artist:
            try:
                return get_movies_searches(artist, langs=langs)
            except InfoError, e:
                raise QueryError('failed to find movies from "%s": %s', artist, str(e))

    elif category in ('tv', 'anime'):
        search['mode'] = 'inc'
        search['season'] = 1
        search['episode'] = 1

    return [search]
