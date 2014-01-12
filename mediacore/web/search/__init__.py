import os
import re
import logging

from filetools.title import Title, clean, get_size
from filetools.utils import in_range

from systools.system import dotdict

from mediacore.model.settings import Settings
from mediacore.web import update_rate, RateLimitReached
from mediacore.utils.utils import list_in, parse_magnet_url


PLUGINS_DIR = 'plugins'

logger = logging.getLogger(__name__)


class SearchError(Exception): pass


class Result(dotdict):

    def __init__(self):
        init = {'safe': True, 'auto': True}
        super(Result, self).__init__(init)

    def _get_regex(self, val):
        if isinstance(val, (str, unicode)):
            return re.compile(val, re.I)
        return val

    def _validate_title(self, include=None, exclude=None, clean=True):
        title = Title(self.title).full_name if clean else self.title

        if include:
            if not isinstance(include, (tuple, list)):
                include = [include]
            for include_ in include:
                if include_ and not self._get_regex(include_).search(title):
                    return False

        if exclude:
            if not isinstance(exclude, (tuple, list)):
                exclude = [exclude]
            for exclude_ in exclude:
                if exclude_ and self._get_regex(exclude_).search(title):
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
            - include_raw: regex the raw title must match
            - exclude_raw: regex the raw title must not match
            - include: regex the title must match
            - exclude: regex the title must not match
            - langs: langs the title must match
            - size_min: minimum size in MB
            - size_max: maximum size in MB
        '''
        if not self._validate_title(kwargs.get('include_raw'), kwargs.get('exclude_raw'), clean=False):
            return
        if not self._validate_title(kwargs.get('include'), kwargs.get('exclude')):
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


def _get_module(plugin):
    try:
        return __import__('%s.%s' % (PLUGINS_DIR, plugin), globals(), locals(), [plugin], -1)
    except ImportError:
        logger.error('failed to import %s module', plugin)

def _get_plugin_priority(plugin):
    module_ = _get_module(plugin)
    if module_:
        return getattr(module_, 'PRIORITY', 0)

def _get_plugins():
    res = []
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), PLUGINS_DIR)
    for filename in os.listdir(path):
        module, ext = os.path.splitext(filename)
        if ext != '.py' or module == '__init__':
            continue
        priority = _get_plugin_priority(module)
        if priority is not None:
            res.append((priority, module))

    return [name for i, name in sorted(res)]

def _get_plugin_object(plugin):
    module_ = _get_module(plugin)
    if not module_:
        return None
    args = Settings.get_settings(plugin)
    try:
        object_ = getattr(module_, plugin.capitalize())(**args)
    except Exception:
        logger.error('failed to get %s object', plugin.capitalize())
        return None
    if hasattr(object_, 'URL') and not object_.url:
        return None
    return object_

def get_query(query, category=None):
    query = clean(query, 1)
    if category == 'tv':
        query = Title(query).name
    elif category == 'anime':
        query = Title(query).display_name

    query = re.sub(r'[\W_]+|\s+s\s+|\sand\s|\sor\s|\snot\s', ' ', query)
    query = re.sub(r'^the\s+|^[\W_]+|[\W_]+$', '', query)
    return query

def results(query, plugins=None, **kwargs):
    if not plugins:
        plugins = _get_plugins()

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
        except SearchError:
            if plugin == 'torrentz' and obj.browser.url_error:
                if obj.browser.url_error.reason.lower() == 'too many requests':
                    update_rate(plugin, count=-1)
            yield None
        except RateLimitReached:
            yield None
