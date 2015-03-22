import re
from datetime import datetime, timedelta
from urlparse import urljoin
import logging

from lxml import html

from filetools.title import is_url

from mediacore.web import Base, Browser, throttle
from mediacore.web.search import Result, SearchError


PRIORITY = 5
RE_OVERLOAD = re.compile(r'please\s+try\s+again\s+in\s+a\s+few\s+seconds', re.I)
RE_DATE = re.compile(r'^(\d+)\s+(seconds?|minutes?|hours?|days?|months?|years?)$', re.I)

logger = logging.getLogger(__name__)


class Isohunt(Base):
    URL = [
        'http://isohunt.to',
        ]

    def _get_date(self, val):
        d, t = RE_DATE.search(val).group(1, 2)
        if not t.endswith('s'):
            t += 's'
        unit = t.lower()

        if unit in ('seconds', 'minutes', 'hours', 'days'):
            key = unit
            d = int(d)
        elif unit == 'months':
            key = 'days'
            d = int(int(d) * 365.25 / 12.)
        elif unit == 'years':
            key = 'days'
            d = int(int(d) * 365.25)
        else:
            key = None

        now = datetime.now()
        if key:
            return now - timedelta(**{key: d})
        return now

    def _get_torrent_url(self, url):
        browser = Browser()
        if browser.open(url):
            links = browser.cssselect('a.btn-magnet')
            if links:
                return links[0].get('href')

    def _next(self, page):
        return self.browser.follow_link(
                text_regex=re.compile(r'^\b%s\b$' % page),
                url_regex=re.compile(r'page='))

    def _sort(self, sort):
        if sort == 'date':
            sort_value = 'created_at.desc'
        elif sort == 'popularity':
            sort_value = 'seeders.desc'
        else:
            return
        url = self.browser.geturl()
        sep = '&' if '?' in url else '?'
        self.browser.open(url + sep + 'Torrent_sort=%s' % sort_value)

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
                    fields = {'ihq': query}
                    if not self.browser.submit_form(self.url,
                            fields=fields):
                        raise SearchError('no data')
                    self._sort(sort)

            trs = self.browser.cssselect('.table-torrents tr[data-key]')
            if not trs:
                if trs is None:
                    raise SearchError('no data')
                elif RE_OVERLOAD.search(self.browser.tree.text_content()):
                    raise SearchError('overload')

            for tr in trs:
                log = html.tostring(tr, pretty_print=True)[:1000]

                result = Result()
                result.type = 'torrent'
                result.safe = False

                category_ = tr.cssselect('.category-row span')
                if not category_:
                    category = None
                else:
                    try:
                        category = category_[0].get('title').lower()
                    except Exception:
                        category = None
                if not category:
                    logger.error('failed to get category from %s', log)
                else:
                    result.category = category

                links_ = tr.cssselect('.title-row a')
                if not links_:
                    logger.error('failed to get title link from %s', log)
                    continue
                try:
                    result.title = links_[0].cssselect('span')[0].text
                except Exception:
                    logger.error('failed to get title from %s', log)
                    continue

                url_info = urljoin(self.url, links_[0].get('href'))

                size_ = tr.cssselect('.size-row')
                if not size_:
                    logger.error('failed to get size from %s', log)
                    continue
                size = size_[0].text
                if not result.get_size(size):
                    logger.error('failed to get size from "%s"', size)
                    continue

                date_ = tr.cssselect('.date-row')
                if not date_:
                    logger.error('failed to get size from %s', log)
                    continue
                date = date_[0].text
                try:
                    result.date = self._get_date(date)
                except Exception, e:
                    logger.error('failed to get date from "%s": %s', date, str(e))
                    continue

                if not result.validate(**kwargs):
                    continue

                result.url = self._get_torrent_url(url_info)
                if not result.url:
                    logger.error('failed to get magnet url from %s', url_info)
                    continue
                if not result.get_hash():
                    continue

                try:
                    result.seeds = int(tr[-2].text)
                except Exception:
                    logger.error('failed to get seeds from %s', log)

                yield result
