import os
import re
from urlparse import parse_qs
import logging

from mediacore.web import Base
from mediacore.util.title import Title, clean


PLUGINS_DIR = 'plugins'

RE_INCL_MOVIES = re.compile(r'\b(br|bd|dvd)rip\b', re.I)
RE_INCL_TV = re.compile(r'\b([hp]dtv|dsr(ip)?)\b', re.I)
RE_EXCL_VIDEO = re.compile(r'\([^\)]*ipod[^\)]*\)|\b(720|1080)p\b|\[micro\]', re.I)
RE_EXCL_ANIME = re.compile(r'\([^\)]*ipod[^\)]*\)|\b(720|1080)p\b|\[micro\]', re.I)

CAT_DEF = {     # category: (inclusion regex, exclusion regex)
    'anime': (None, RE_EXCL_ANIME),
    'apps': (None, None),
    'books': (None, None),
    'games': (None, None),
    'movies': (RE_INCL_MOVIES, RE_EXCL_VIDEO),
    'music': (None, None),
    'tv': (RE_INCL_TV, RE_EXCL_VIDEO),
    }
RE_SIZE = re.compile(r'^([\d\.]+)\W*\s*([gmk])?i?b\s*$', re.I)
RE_URL_MAGNET = re.compile(r'^magnet:\?(.*)', re.I)


logger = logging.getLogger(__name__)


class TorrentError(Exception): pass


class BaseTorrent(Base):
    '''Base torrent website.
    '''
    def _get_query(self, query, category=None):
        query = clean(query, 1)
        if category == 'tv':
            query = Title(query).name
        elif category == 'anime':
            query = Title(query).display_name
        query = re.sub(r'[\W_]+|\s+s\s+|\sand\s|\sor\s|\snot\s', ' ', query)
        query = re.sub(r'^the\s+|^[\W_]+|[\W_]+$', '', query)
        return query

    def _get_size(self, val):
        '''Get the size in MB.
        '''
        n, unit = RE_SIZE.search(val).group(1, 2)
        n = float(n)
        if not unit:
            n /= (1024 / 1024)
        elif unit.lower() == 'k':
            n /= 1024
        elif unit.lower() == 'g':
            n *= 1024
        return n


class Result(dict):
    def __init__(self):
        init = {
            'hash': None,
            'title': None,
            'net_name': None,
            'url_magnet': None,
            'url_torrent': None,
            'category': '',
            'size': None,
            'date': None,
            'seeds': None,
            'private': False,
            'page': 1,
            }
        super(Result, self).__init__(init)

    __getattr__ = dict.__getitem__

    def __setattr__(self, attr_name, value):
        if hasattr(getattr(self.__class__, attr_name, None), '__set__'):
            return object.__setattr__(self, attr_name, value)
        else:
            return self.__setitem__(attr_name, value)

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__, dict(self))

    def __repr__(self):
        return self.__str__()

    def __delattr__(self, attr_name):
        if attr_name.startswith('_'):
            return object.__delattr__(self, attr_name)
        else:
            return self.__delitem__(attr_name)


def _get_nets():
    '''Find torrent modules filenames.

    :return: modules list
    '''
    res = []
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), PLUGINS_DIR)
    for filename in os.listdir(path):
        module, ext = os.path.splitext(filename)
        if ext == '.py' and module != '__init__':
            priority = _get_net_priority(module)
            if priority is not None:
                res.append((priority, module))

    return [net for i, net in sorted(res)]

def _get_module(net):
    try:
        module_ = __import__('%s.%s' % (PLUGINS_DIR, net), globals(), locals(), [net], -1)
    except ImportError:
        logger.error('failed to import %s module', net)
        return
    return module_

def _get_net_priority(net):
    module_ = _get_module(net)
    if module_:
        return getattr(module_, 'PRIORITY', None)

def _get_net_object(net):
    '''Get a torrent plugin object.
    '''
    module_ = _get_module(net)
    if not module_:
        return
    try:
        object_ = getattr(module_, net.capitalize())()
    except Exception:
        logger.error('failed to create %s object', net)
        return
    if not object_.accessible:
        logger.info('%s is inaccessible', object_.URL)
        return
    return object_

def results(query, category=None, sort='age', pages_max=1, re_incl=None, re_excl=None, nets=None):
    if not nets:
        nets = _get_nets()
    if category:
        category = category.lower()
        if category not in CAT_DEF:
            logger.error('invalid category %s for query "%s"' % (category, query))
            category = None

    re_incl_cat, re_excl_cat = CAT_DEF.get(category, (None, None))

    for net in nets:
        obj = _get_net_object(net)
        if not obj:
            continue
        query_ = obj._get_query(query, category)
        if not query_:
            continue

        try:
            for result in obj.results(query_, category, sort=sort, pages_max=pages_max):
                if re_incl_cat and not re_incl_cat.search(result.title):
                    continue
                if re_excl_cat and re_excl_cat.search(result.title):
                    continue
                if re_incl and not re_incl.search(result.title):
                    continue
                if re_excl and re_excl.search(result.title):
                    continue

                result.net_name = net
                yield result

        except TorrentError, e:
            logger.error('error with %s: %s', net, e)
            yield None

def parse_magnet_url(url):
    try:
        qs = RE_URL_MAGNET.search(url).group(1)
        return parse_qs(qs)
    except Exception:
        logger.error('failed to parse magnet url %s', url)

def get_hash(url):
    '''Get the torrent hash.
    '''
    res = parse_magnet_url(url)
    if res and 'xt' in res:
        hash = res['xt'][0].split(':')[-1].lower()
        return hash
