import re
from datetime import datetime, timedelta
from urlparse import urljoin
import logging

from lxml import html

from mediacore.web import Browser, WEB_EXCEPTIONS
from mediacore.web.torrent import BaseTorrent, Result, TorrentError
from mediacore.util.title import clean, is_url

#
# TODO: handle torrent hash
#

PRIORITY = None
CAT_DEF = {
    'anime': 'anime',
    'apps': 'applications',
    'books': 'books',
    'games': 'games',
    'movies': 'video/movies',
    'music': 'audio',
    'tv': 'tv',
    }
SORT_DEF = {
    'age': 'nameTH_5',
    'seeds': 'nameTH_1',
    }
RE_SORT = re.compile(r"='([^']+)'")
RE_URL_TORRENT = re.compile(r'/download/.*\.torrent$', re.I)
RE_DATE = re.compile(r'([\d\.]+)([hdw])', re.I)


logger = logging.getLogger(__name__)


class Isohunt(BaseTorrent):
    URL = 'http://isohunt.com'

    def _sort(self, sort):
        response = self.browser.response()

        if getattr(self, 'sorted', None) == sort:   # sorting order is valid for a session
            return response

        tree = html.fromstring(response.get_data())
        try:
            th = tree.get_element_by_id(SORT_DEF[sort])
        except Exception:
            return response

        res = RE_SORT.search(th.get('onclick'))
        if not res:
            logger.error('failed to sort results by %s', sort)
        else:
            url = urljoin(self.URL, res.group(1))
            try:
                response = self.browser.open(url)
            except Exception, e:
                logger.error('failed to sort results by %s: %s', sort, e)
            self.sorted = sort
        return response

    def _next(self, page):
        try:
            return self.browser.follow_link(url_regex=re.compile(r'\bihp=%s\b' % page, re.I))
        except Exception:
            pass

    def _pages(self, query, category=None, sort='age', pages_max=1):
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
                        res = self.submit_form(self.URL, name='ihSearch', fields={'ihq': query})
                        if res:
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

            yield page, data

    def _get_torrent_url(self, url):
        browser = Browser()
        try:
            browser.open(url)
            for link in browser.links(url_regex=RE_URL_TORRENT):
                return link.absolute_url
        except WEB_EXCEPTIONS:
            pass
        except Exception, e:
            logger.exception('failed to get torrent url from %s: %s', url, e)

    def _get_date(self, val):
        n, u = RE_DATE.search(val).groups()
        n = float(n)
        now = datetime.utcnow()
        if u == 'h':
            date = now - timedelta(hours=n)
        elif u == 'd':
            date = now - timedelta(days=n)
        elif u == 'w':
            date = now - timedelta(weeks=n)
        else:
            raise Exception('unknown date format: %s' % val)
        return date + (datetime.utcnow() - now)

    def results(self, query, category=None, sort='age', pages_max=1):
        for page, data in self._pages(query, category, sort, pages_max):
            tree = html.fromstring(data)
            for tr in tree.cssselect('tr.hlRow'):
                log = html.tostring(tr, pretty_print=True)

                # Skip "isohunt releases"
                res = tr.cssselect('i')
                if res:
                    val = res[0].text
                    if val and val.lower() == 'isohunt release':
                        continue

                result = Result()
                try:
                    result.category = tr[0].text
                except Exception:
                    logger.error('failed to get category for query "%s" from %s', query, log)
                    continue
                if result.category.lower() == 'category':   # header
                    continue

                if category and result.category.lower() != CAT_DEF[category.lower()]:
                    continue

                links = tr[2].cssselect('a')
                if not links:
                    logger.error('failed to get title from %s', log)
                    continue
                title = self.get_link_text(html.tostring(links[-1]))
                result.title = clean(title.split('<br>')[-1])

                url_info = urljoin(self.URL, links[-1].get('href'))
                result.url_torrent = self._get_torrent_url(url_info)
                if not result.url_torrent:
                    logger.error('failed to get torrent url from %s', url_info)
                    continue

                try:
                    result.size = self._get_size(tr[3].text)
                except Exception, e:
                    logger.error('failed to get size from %s: %s', log, e)
                    continue
                try:
                    result.date = self._get_date(clean(html.tostring(tr[1])))
                except Exception, e:
                    logger.error('failed to get date from %s: %s', log, e)
                    continue
                try:
                    result.seeds = int(tr[4].text)
                except Exception:
                    pass

                result.page = page
                yield result
