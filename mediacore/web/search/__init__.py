import os
import re
from datetime import datetime
import logging

from mediacore.util.title import Title, clean, get_size
from mediacore.util.util import in_range, list_in, parse_magnet_url

from systools.system import dotdict


PLUGINS_DIR = 'plugins'

logger = logging.getLogger(__name__)


class SearchError(Exception): pass


class Result(dotdict):

    def __init__(self):
        init = {
            'created': datetime.utcnow(),
            'processed': False,
            }
        super(Result, self).__init__(init)

    def _validate_title(self, re_incl=None, re_excl=None, clean=True):
        title = Title(self.title).full_name if clean else self.title

        if re_incl:
            if not isinstance(re_incl, (tuple, list)):
                re_incl = [re_incl]
            for re_ in re_incl:
                if re_ and not re_.search(title):
                    return False

        if re_excl:
            if not isinstance(re_excl, (tuple, list)):
                re_excl = [re_excl]
            for re_ in re_excl:
                if re_ and re_.search(title):
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
            - re_incl_raw: regex the raw title must match
            - re_excl_raw: regex the raw title must not match
            - langs: langs the title must match
            - size_min: minimum result size
            - size_max: maximum result size
        '''
        if not self._validate_title(kwargs.get('re_incl_raw'), kwargs.get('re_excl_raw'), clean=False):
            return
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
        self.size = get_size(val)
        if self.size is not None:
            return True
        logger.error('failed to get result size from "%s"', val)

    def get_hash(self):
        if not self.url:
            logger.error('failed to get hash from result %s', self)
        else:
            res = parse_magnet_url(self.url)
            if res and 'xt' in res:
                hash = res['xt'][0].split(':')[-1].lower()
                if hash:
                    self.hash = hash
                    return True
            logger.error('failed to get hash from magnet url "%s"', self.url)

def _get_plugins():
    '''Find modules filenames sorted by priority.

    :return: modules list
    '''
    res = []

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), PLUGINS_DIR)
    for filename in os.listdir(path):
        module, ext = os.path.splitext(filename)
        if ext == '.py' and module != '__init__':
            priority = _get_plugin_priority(module)
            if priority is not None:
                res.append((priority, module))

    return [name for i, name in sorted(res)]

def _get_module(plugin):
    try:
        return __import__('%s.%s' % (PLUGINS_DIR, plugin), globals(), locals(), [plugin], -1)
    except ImportError:
        logger.error('failed to import %s module', plugin)

def _get_plugin_priority(plugin):
    module_ = _get_module(plugin)
    if module_:
        return getattr(module_, 'PRIORITY', 0)

def _get_plugin_object(plugin):
    '''Get a search plugin object.
    '''
    module_ = _get_module(plugin)
    if module_:
        try:
            object_ = getattr(module_, plugin.capitalize())()
        except Exception:
            logger.error('failed to get %s object', plugin.capitalize())
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
    '''Get search results.
    '''
    plugins = kwargs.get('plugins', _get_plugins())
    for plugin in plugins:
        obj = _get_plugin_object(plugin)
        if not obj:
            yield None
            continue

        query_ = get_query(query, kwargs.get('category'))
        if query and not query_:
            logger.error('failed to process query "%s"', query)
            continue

        try:
            for result in obj.results(query_, **kwargs):
                result.plugin = plugin
                yield result
        except SearchError, e:
            logger.error('error with %s: %s', plugin, str(e))
            yield None
