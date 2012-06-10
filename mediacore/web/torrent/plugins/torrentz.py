import re
from datetime import datetime
from urlparse import urljoin
import logging

from lxml import html

from mediacore.web import Base, Browser
from mediacore.web.torrent import (parse_magnet_url, Result, TorrentError,
        RE_URL_MAGNET)
from mediacore.util.title import Title, clean, is_url


PRIORITY = 1
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
RE_CATEGORIES = re.compile(r'&#187;\W*(.*)$')
RE_APPROXIMATE_MATCH = re.compile(r'\bapproximate\s+match\b', re.I)


logger = logging.getLogger(__name__)


class Torrentz(Base):
    URL = [
        'http://torrentz.eu',
        'http://torrentz.piratereverse.info',
        ]

    def _sort(self, sort):
        res = self.browser.follow_link(text_regex=RE_URL_SORT[sort])
        return res or self.browser.response()

    def _next(self, page):
        return self.browser.follow_link(
                text_regex=re.compile(r'^%s$' % page),
                url_regex=re.compile(r'\bp=%s\b' % (page - 1), re.I))

    def _pages(self, query, sort='age', pages_max=1):
        for page in range(1, pages_max + 1):
            if page > 1:
                res = self._next(page)
            else:
                self.browser.clear_history()
                if is_url(query):
                    res = self.browser.open(query)
                else:
                    res = self.submit_form(self.url, index=0, fields={'f': query})
                    if res and sort != 'seeds':     # default is 'peers'
                        res = self._sort(sort)

            if res:
                data = res.get_data()
                if not data:
                    if page > 1:
                        return
                    raise TorrentError('no data')

                yield page, data

    def _mirror_urls(self, url):
        '''Iterate over mirror urls.
        '''
        browser = Browser()
        res = browser.open(url)
        if not res:
            return
        data = res.get_data()
        if not data:
            return

        tree = html.fromstring(data)
        links = tree.cssselect('div.download dl a')
        if not links:
            logger.error('failed to get mirror urls from %s', url)
            return

        for link in links:
            mirror_url = link.get('href')
            if not mirror_url.startswith('/'):
                yield mirror_url

    def _torrent_urls(self, url):
        '''Iterate over torrent urls fetched from the raw html data.
        '''
        browser = Browser()
        if not browser.open(url):
            logger.debug('failed to get torrent url from %s', url)
            return

        for link in browser.links(url_regex=RE_URL_MAGNET):
            yield link.absolute_url

    def _get_torrent_url(self, query, url):
        re_q = Title(query).get_search_re(mode='all')

        for mirror_url in self._mirror_urls(url):
            for torrent_url in self._torrent_urls(mirror_url):
                res = parse_magnet_url(torrent_url)
                if not res or not 'dn' in res:
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

    def results(self, query, category=None, sort='age', pages_max=1, **kwargs):
        for page, data in self._pages(query, sort, pages_max):
            tree = html.fromstring(data)

            # Skip approximate matches
            res = tree.cssselect('div.results h3')
            if not res:
                logger.error('failed to check approximate matches at %s', self.browser.geturl())
            elif RE_APPROXIMATE_MATCH.search(html.tostring(res[0])):
                break

            for div in tree.cssselect('div.results'):

                # Skip sponsored links
                try:
                    if div.cssselect('h2')[0].text.lower() == 'sponsored links':
                        continue
                except Exception:
                    pass

                for dl in div.cssselect('dl'):
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

                    if dl.cssselect('span.pe'):     # skip 'pending' results (missing date and size)
                        continue

                    try:
                        date = dl.find_class('a')[0][0].get('title')
                        result.date = self._get_date(date)
                    except Exception:
                        logger.debug('failed to get date from %s', log)
                        continue
                    try:
                        size = dl.find_class('s')[0].text
                    except Exception:
                        logger.debug('failed to get size from %s', log)
                        continue
                    if not result.get_size(size):
                        continue

                    if not result.validate(**kwargs):
                        continue

                    try:
                        seeds = dl.find_class('d')[0].text
                        result.seeds = int(seeds.replace(',', ''))
                    except Exception:
                        logger.debug('failed to get seeds from %s', log)

                    # Find torrent url
                    url_info = urljoin(self.url, links[0].get('href'))
                    result.url_magnet = self._get_torrent_url(query, url_info)
                    if not result.url_magnet:
                        continue
                    if not result.get_hash():
                        continue

                    result.page = page
                    yield result
