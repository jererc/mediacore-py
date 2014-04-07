import re
from datetime import datetime
from urlparse import urlparse, parse_qs
from urllib import urlencode
from base64 import b64encode
import logging

from lxml import html

import requests

from filetools.title import clean

from mediacore.model.settings import Settings

from mediacore.web import Base, throttle
from mediacore.web.search import Result, LoginError, SearchError


PRIORITY = 4
QUERY_URL = 'http://rutracker.org/forum/tracker.php'
RE_OVERLOAD = re.compile(r'please\s+try\s+again\s+in\s+a\s+few\s+seconds', re.I)

logger = logging.getLogger(__name__)


class DownloadError(Exception): pass


class Rutracker(Base):
    URL = [
        'http://rutracker.org/forum/index.php',
        ]

    def __init__(self, username, password):
        super(Rutracker, self).__init__()
        self._login(username, password)

    def _login(self, username, password):
        fields = {
            'login_username': username,
            'login_password': password,
            }
        if not self.browser.submit_form(self.url, index=2, fields=fields):
            raise LoginError('failed to login to rutracker')
        for form in self.browser.forms():
            if set(fields.keys()) <= set([c.name for c in form.controls]):
                raise LoginError('failed to login to rutracker')

    def _next(self, page):
        for link in self.browser.cssselect('.pg', []):
            if link.text == str(page):
                return self.browser.open(link.get('href'))

    @throttle(300)
    def results(self, query, category=None, pages_max=1, **kwargs):
        if not self.url:
            raise SearchError('no data')

        url = '%s?%s' % (QUERY_URL, urlencode({'nm': query}))
        for page in range(1, pages_max + 1):
            if page > 1:
                if not self._next(page):
                    break
            else:
                if not self.browser.open(url):
                    raise SearchError('no data')

            trs = self.browser.cssselect('#tor-tbl tbody tr')
            if not trs:
                if trs is None:
                    raise SearchError('no data')
                elif RE_OVERLOAD.search(self.browser.tree.text_content()):
                    raise SearchError('overload')

            for el in trs:
                if len(el) == 1:
                    continue
                log = html.tostring(el, pretty_print=True)[:1000]

                result = Result()
                result.type = 'rutracker'
                result.safe = False
                result.category = None

                links = el[3].cssselect('a')
                if not links:
                    logger.error('failed to get title from %s', log)
                    continue
                result.title = clean(html.tostring(links[0]))

                links = el[5].cssselect('a')
                if not links:
                    logger.debug('failed to get torrent url from %s', html.tostring(el[5]))
                    continue
                result.url = links[0].get('href')

                size = clean(links[0].text or '').replace('_', ' ').strip()
                if not result.get_size(size):
                    continue

                seeds = el[6].cssselect('.seedmed')
                if seeds:
                    try:
                        result.seeds = int(seeds[0].text)
                    except ValueError:
                        pass

                els = el[9].cssselect('u')
                if not els:
                    logger.error('failed to get date from %s', log)
                    continue
                try:
                    result.date = datetime.utcfromtimestamp(int(els[0].text))
                except ValueError:
                    logger.error('failed to get date from %s', els[0].text)
                    continue

                if not result.validate(**kwargs):
                    continue

                yield result


def download_torrent(url):
    res = parse_qs(urlparse(url).query).get('t')
    if not res:
        raise DownloadError('failed to get torrent id from %s' % url)
    id_ = res[0]

    settings = Settings.get_settings('rutracker')
    if not settings.get('username') or not settings.get('password'):
        raise DownloadError('missing username and password')
    try:
        rutracker = Rutracker(settings['username'], settings['password'])
    except LoginError, e:
        raise DownloadError('failed to get torrent from %s: %s' % (url, str(e)))

    cookie_str = ';'.join(['%s=%s' % (c.name, c.value)
            for c in rutracker.browser._ua_handlers['_cookies'].cookiejar])
    headers = {
        'Content-Type': 'application/x-bittorrent; name="%s.torrent"' % id_,
        'Cookie': '%s; bb_dl=%s' % (cookie_str, id_),
        }
    res = requests.post(url, headers=headers)
    if not 200 <= res.status_code < 300:
        raise DownloadError('failed to get torrent from %s: %s' % (url, res.status_code))
    return str(b64encode(res.content))
