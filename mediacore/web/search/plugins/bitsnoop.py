import re
from datetime import datetime, timedelta
from urlparse import urljoin
import logging

from lxml import html

from filetools.title import clean, is_url

from mediacore.web import Base, Browser, throttle
from mediacore.web.search import Result, SearchError


PRIORITY = 4
CAT_DEF = {
    'anime': 'video',
    'apps': 'software',
    'books': None,
    'games': 'games',
    'movies': 'video',
    'music': 'audio',
    'tv': 'video',
    }
RE_URL_SORT = {
    'date': re.compile(r'^\s*Age\s*$', re.I),
    'popularity': re.compile(r'^\s*Seeds\s*$', re.I),
    }
RE_OVERLOAD = re.compile(r'please\s+try\s+again\s+in\s+a\s+few\s+seconds', re.I)
RE_DETAILS = re.compile(r'&#8212;\s*([^&]+)&#187;\s*([^&]+)&#8212;\s*([^<]*)', re.I)
RE_DATE = re.compile(r'^(\d+)\s+(\w+)', re.I)

logger = logging.getLogger(__name__)


class Bitsnoop(Base):
    URL = [
        'http://bitsnoop.com',
        ]

    def _get_date(self, val):
        res = RE_DATE.search(val.lower())
        if res:
            n, val = res.groups()
            n = int(n)
        if val == 'yesterday':
            delta = timedelta(days=1)
        elif val.startswith('year'):
            delta = timedelta(days=n*365)
        elif val.startswith('month'):
            delta = timedelta(days=n*365/12)
        elif val.startswith('week'):
            delta = timedelta(weeks=n)
        elif val.startswith('day'):
            delta = timedelta(days=n)
        elif val.startswith('hour'):
            delta = timedelta(hours=n)
        elif val.startswith('minute'):
            delta = timedelta(minutes=n)
        else:
            return None
        return datetime.now() - delta

    def _get_magnet_url(self, tr):
        for link in tr.cssselect('a'):
            url = link.get('href')
            if url.startswith('magnet:?'):
                return url

    def _get_torrent_url(self, url):
        browser = Browser()
        if browser.open(url):
            links = browser.cssselect('a[title="Magnet Link"]')
            if links:
                return links[0].get('href')

    def _next(self, page):
        return self.browser.follow_link(
                text_regex=re.compile(r'^\D*%s\D*$' % page),
                url_regex=re.compile(r'/%s/' % page))

    def _sort(self, sort):
        return self.browser.follow_link(text_regex=RE_URL_SORT[sort])

    @throttle(300)
    def results(self, query, category=None, sort='date', pages_max=1,
            **kwargs):
        if not self.url:
            raise SearchError('no data')

        for page in range(1, pages_max + 1):
            if page > 1:
                if not self._next(page):
                    break
            else:
                if is_url(query):
                    if not self.browser.open(query):
                        raise SearchError('no data')
                else:
                    fields = {'q': query}
                    if category:
                        val = CAT_DEF.get(category.lower())
                        if val:
                            fields['t'] = [val]
                    if not self.browser.submit_form(self.url, fields=fields):
                        raise SearchError('no data')
                    self._sort(sort)

            lis = self.browser.cssselect('#torrents li')
            if not lis:
                if lis is None:
                    raise SearchError('no data')
                elif RE_OVERLOAD.search(self.browser.tree.text_content()):
                    raise SearchError('overload')

            for el in lis:
                log = html.tostring(el, pretty_print=True)[:1000]

                result = Result()
                result.type = 'torrent'
                result.safe = False

                links = el.cssselect('a')
                if not links:
                    logger.error('failed to get title from %s' % log)
                    continue
                result.title = clean(html.tostring(links[0]))

                details = el.cssselect('.torInfo')
                if not details:
                    logger.error('failed to get details from %s' % log)
                    continue
                res = RE_DETAILS.search(html.tostring(details[0]))
                if not res:
                    continue
                result.category = res.group(1).strip(' ').lower()

                date = res.group(3)
                result.date = self._get_date(date)
                if not result.date:
                    logger.error('failed to get date from "%s"' % date)
                    continue

                seeds = details[0].cssselect('span.seeders')
                if seeds:
                    try:
                        result.seeds = int(seeds[0].text.replace(',', ''))
                    except ValueError:
                        pass

                tds = el.cssselect('tr td')
                if not tds:
                    logger.error('failed to get size from %s' % log)
                    continue
                if not result.get_size(tds[0].text):
                    continue

                url_info = urljoin(self.url, links[0].get('href')).encode('utf-8')
                result.url = self._get_torrent_url(url_info)
                if not result.url:
                    logger.error('failed to get magnet url from %s' % url_info)
                    continue
                if not result.get_hash():
                    continue

                if not result.validate(**kwargs):
                    continue

                yield result
