import re
from datetime import datetime
from urlparse import urljoin
import logging

from lxml import html

from mediacore.web import Browser, WEB_EXCEPTIONS
from mediacore.web.torrent import BaseTorrent, parse_magnet_url, Result, TorrentError, RE_URL_MAGNET
from mediacore.util.title import Title, clean, is_url


PRIORITY = 2
CAT_DEF = {
    'anime': re.compile(r'\banime\b', re.I),
    'apps': re.compile(r'\bapplications?\b', re.I),
    'books': re.compile(r'\be?books?\b', re.I),
    'games': re.compile(r'\bgames?\b', re.I),
    'movies': re.compile(r'\bmovies?\b', re.I),
    'music': re.compile(r'\b(audio|music)\b', re.I),
    'tv': re.compile(r'\b(tv|television|shows?)\b', re.I),
    }
RE_URL_SORT = {
    'age': re.compile(r'^date$', re.I),
    'seeds': re.compile(r'^peers$', re.I),
    }
RE_URL_TORRENT = re.compile(r'\.torrent$', re.I)
RE_OVERLOAD = re.compile(r'%s' % re.escape('please try again in a few seconds'), re.I)
RE_DESC = re.compile(r'uploaded\s+(.*?)\s*,\s*size\s+(.*?)\s*,', re.I)
RE_DATE = re.compile(r'^(y-day|today|\d\d-\d\d|\d+)\s+(\d\d:\d\d|\d{4}|mins?\s+ago)$', re.I)
RE_CATEGORIES = re.compile(r'&#187;\W*(.*)$')


logger = logging.getLogger(__name__)


class Torrentz(BaseTorrent):
    URL = 'http://torrentz.eu'

    def _sort(self, sort):
        try:
            return self.browser.follow_link(text_regex=RE_URL_SORT[sort])
        except Exception:
            return self.browser.response()

    def _next(self, page):
        try:
            return self.browser.follow_link(
                    text_regex=re.compile(r'^%s$' % page),
                    url_regex=re.compile(r'\bp=%s\b' % (page - 1), re.I))
        except Exception:
            pass

    def _pages(self, query, sort='age', pages_max=1):
        for page in range(1, pages_max + 1):
            data = None
            try:
                if page > 1:
                    res = self._next(page)
                else:
                    self.browser.clear_history()
                    if is_url(query):
                        res = self.browser.open(query)
                    else:
                        res = self.submit_form(self.URL, index=0, fields={'f': query})
                        if res and sort != 'seeds':     # default is 'peers'
                            res = self._sort(sort)

                if res:
                    data = res.get_data()
            except WEB_EXCEPTIONS:
                pass
            except Exception:
                logger.exception('exception')

            if not data:
                if page > 1:
                    return
                raise TorrentError('no data')
            elif RE_OVERLOAD.search(data):
                raise TorrentError('overload')

            yield page, data

    def _mirror_urls(self, url):
        '''Iterate over mirror urls.
        '''
        browser = Browser()
        try:
            data = browser.open(url).get_data()
            if not data:
                return
        except WEB_EXCEPTIONS:
            return
        except Exception:
            logger.exception('exception')
            return

        tree = html.fromstring(data)
        links = tree.cssselect('div.download dl a')
        if not links:
            logger.exception('failed to get mirror urls from %s', url)
            return

        for link in links:
            mirror_url = link.get('href')
            if not mirror_url.startswith('/'):
                yield mirror_url

    def _torrent_urls(self, url):
        '''Iterate over torrent urls fetched from the raw html data.
        '''
        browser = Browser()
        try:
            browser.open(url)
            for link in browser.links(url_regex=RE_URL_MAGNET):
                yield link.absolute_url
        except WEB_EXCEPTIONS:
            pass
        except Exception:
            logger.debug('failed to get torrent url from %s', url)

    def _get_torrent_url(self, query, url):
        re_q = Title(query).get_search_re(mode='all')

        for mirror_url in self._mirror_urls(url):
            for torrent_url in self._torrent_urls(mirror_url):
                res = parse_magnet_url(torrent_url)
                if not res or not 'dn' in res:
                    logger.debug('failed to get title from magnet url %s at %s', torrent_url, mirror_url)
                    continue

                title = clean(res['dn'][0])
                if re_q.match(title):
                    return torrent_url

    def _get_date(self, val):
        return datetime.strptime(val, '%a, %d %b %Y %H:%M:%S')

    def _get_category(self, val):
        for key, re_cat in CAT_DEF.items():
            if re_cat.search(val):
                return key
        return 'other'

    def results(self, query, category=None, sort='age', pages_max=1):
        for page, data in self._pages(query, sort, pages_max):
            tree = html.fromstring(data)
            for dl in tree.cssselect('div.results dl'):
                links = dl.cssselect('a')
                if not links:
                    continue

                log = html.tostring(dl, pretty_print=True)

                result = Result()
                title = self.get_link_text(html.tostring(links[0]))
                if not title:
                    continue
                result.title = clean(title)

                try:
                    res = RE_CATEGORIES.search(html.tostring(links[0]))
                    result.category = self._get_category(res.group(1))
                except Exception:
                    logger.error('failed to get category info from %s', log)

                if category and category != result.category:
                    continue

                try:
                    date = dl.find_class('a')[0][0].get('title')
                    result.date = self._get_date(date)
                except Exception:
                    logger.debug('failed to get date from %s', log)
                    continue
                try:
                    size = dl.find_class('s')[0].text
                    result.size = self._get_size(size)
                except Exception:
                    logger.debug('failed to get size from %s', log)
                    continue
                try:
                    seeds = dl.find_class('d')[0].text
                    result.seeds = int(seeds.replace(',', ''))
                except Exception:
                    logger.debug('failed to get seeds from %s', log)

                url_info = urljoin(self.URL, links[0].get('href'))
                result.url_magnet = self._get_torrent_url(query, url_info)
                if not result.url_magnet:
                    continue

                result.page = page
                yield result
