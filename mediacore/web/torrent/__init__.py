import os
import re
from urlparse import parse_qs
from datetime import datetime
import logging

from systools.system import dotdict

from mediacore.util.title import Title, clean
from mediacore.util.util import in_range, list_in


PLUGINS_DIR = 'plugins'
RE_SIZE = re.compile(r'^([\d\.]+)\W*\s*([gmk])?i?b\s*$', re.I)
RE_URL_MAGNET = re.compile(r'^magnet:\?(.*)', re.I)


logger = logging.getLogger(__name__)


class TorrentError(Exception): pass


class Result(dotdict):
    def __init__(self):
        init = {
            'hash': None,
            'title': None,
            'category': '',
            'url_magnet': None,
            'url_torrent': None,
            'size': None,
            'date': None,
            'seeds': None,
            'page': 1,
            'created': datetime.utcnow(),
            'processed': False,
            }
        super(Result, self).__init__(init)

    def _validate_title(self, re_incl=None, re_excl=None):
        if re_incl:
            if not isinstance(re_incl, (tuple, list)):
                re_incl = [re_incl]
            for re_ in re_incl:
                if re_ and not re_.search(self.title):
                    return False

        if re_excl:
            if not isinstance(re_excl, (tuple, list)):
                re_excl = [re_excl]
            for re_ in re_excl:
                if re_ and re_.search(self.title):
                    return False

        return True

    def _validate_lang(self, langs):
        if not langs or list_in(langs, Title(self.title).langs, all=False):
            return True

    def _validate_size(self, size_min=None, size_max=None):
        if self.size is None or in_range(self.size, size_min, size_max):
            return True

    def validate(self, **kwargs):
        '''Validate the result attributes.

        :param kwargs: filters
            - re_incl: regex the title must match
            - re_excl: regex the title must not match
            - langs: langs the title must match
            - size_min: minimum result size
            - size_max: maximum result size
        '''
        if not self._validate_title(kwargs.get('re_incl'), kwargs.get('re_excl')):
            return
        if not self._validate_lang(kwargs.get('langs')):
            return
        if not self._validate_size(kwargs.get('size_min'), kwargs.get('size_max')):
            return
        return True

    def get_size(self, val):
        '''Get the result size in MB.
        '''
        res = RE_SIZE.search(val)
        if not res:
            logger.error('failed to get result size from "%s"', val)
            return

        size, unit = res.groups()
        self.size = float(size)
        if not unit:
            self.size /= (1024 * 1024)
        elif unit.lower() == 'k':
            self.size /= 1024
        elif unit.lower() == 'g':
            self.size *= 1024
        return True

    def get_hash(self):
        if self.url_magnet:
            res = parse_magnet_url(self.url_magnet)
            if res and 'xt' in res:
                hash = res['xt'][0].split(':')[-1].lower()
                if hash:
                    self.hash = hash
                    return True

            logger.error('failed to get hash from magnet url "%s"', self.url_magnet)
        else:
            logger.error('failed to get hash from result %s', self)


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
        return __import__('%s.%s' % (PLUGINS_DIR, net), globals(), locals(), [net], -1)
    except ImportError:
        logger.error('failed to import %s module', net)

def _get_net_priority(net):
    module_ = _get_module(net)
    if module_:
        return getattr(module_, 'PRIORITY', None)

def _get_net_object(net):
    '''Get a torrent plugin object.
    '''
    module_ = _get_module(net)
    if module_:
        try:
            object_ = getattr(module_, net.capitalize())()
        except Exception:
            logger.error('failed to create %s object', net.capitalize())
            return

        if object_.url:
            return object_

def get_query(query, category=None):
    '''Get a clean query.
    '''
    query = clean(query, 1)
    if category == 'tv':
        query = Title(query).name
    elif category == 'anime':
        query = Title(query).display_name

    query = re.sub(r'[\W_]+|\s+s\s+|\sand\s|\sor\s|\snot\s', ' ', query)
    query = re.sub(r'^the\s+|^[\W_]+|[\W_]+$', '', query)
    return query

def results(query, **kwargs):
    '''Get torrent results.
    '''
    nets = kwargs.get('nets', _get_nets())
    for net in nets:
        obj = _get_net_object(net)
        if not obj:
            continue

        query_ = get_query(query, kwargs.get('category'))
        if not query_:
            logger.error('failed to process query "%s"', query)
            continue

        try:
            for result in obj.results(query_, **kwargs):
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
