import re
from datetime import datetime, timedelta
import logging

from lxml import html

from mediacore.web import WEB_EXCEPTIONS
from mediacore.web.torrent import BaseTorrent, get_hash, Result, TorrentError
from mediacore.util.title import clean, is_url


PRIORITY = 0
CAT_DEF = {
    'anime': 'video',
    'apps': 'apps',
    'books': None,
    'games': 'games',
    'movies': 'video',
    'music': 'audio',
    'tv': 'video',
    }
RE_URL_SORT = {
    'age': re.compile(r'^\s*Uploaded\s*$', re.I),
    'seeds': re.compile(r'^\s*SE\s*$', re.I),
    }
RE_OVERLOAD = re.compile(r'%s' % re.escape('please try again in a few seconds'), re.I)
RE_DETAILS = re.compile(r'uploaded\s+(.*?)\s*,\s*size\s+(.*?)\s*,', re.I)
RE_DATE = re.compile(r'^(y-day|today|\d\d-\d\d|\d+)\s+(\d\d:\d\d|\d{4}|mins?\s+ago)$', re.I)


logger = logging.getLogger(__name__)


class Thepiratebay(BaseTorrent):
    URL = 'http://thepiratebay.se'

    def _sort(self, sort):
        try:
            return self.browser.follow_link(text_regex=RE_URL_SORT[sort])
        except Exception:
            return self.browser.response()

    def _next(self, page):
        try:
            return self.browser.follow_link(
                    text_regex=re.compile(r'^\D*%s\D*$' % page),
                    url_regex=re.compile(r'/%s/' % (page - 1), re.I))
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
                        fields = {'q': query}
                        if category:
                            val = CAT_DEF.get(category.lower())
                            if val:
                                fields[val] = ['on']
                        res = self.submit_form(self.URL, fields=fields)
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
            elif RE_OVERLOAD.search(data):
                raise TorrentError('overload')

            yield page, data

    def _get_date(self, val):
        d, t = RE_DATE.search(val).group(1, 2)
        now = datetime.utcnow()
        if 'ago' in t:
            date = now - timedelta(minutes=int(d))
        elif d.lower() == 'y-day':
            day = now - timedelta(days=1)
            hour = datetime.strptime(t, '%H:%M')
            date = datetime(day.year, day.month, day.day, hour.hour, hour.minute)
        elif d.lower() == 'today':
            hour = datetime.strptime(t, '%H:%M')
            date = datetime(now.year, now.month, now.day, hour.hour, hour.minute)
        elif ':' not in t:
            date = datetime.strptime('%s-%s' % (t, d), '%Y-%m-%d') # add year to avoid exceptions like 29/02
        else:
            date = datetime.strptime('%s-%s %s' % (now.year, d, t), '%Y-%m-%d %H:%M') # add year to avoid exceptions like 29/02
        return date + (datetime.utcnow() - now)

    def _get_magnet_url(self, tr):
        for link in tr.cssselect('a'):
            url = link.get('href')
            if url.startswith('magnet:?'):
                return url

    def results(self, query, category=None, sort='age', pages_max=1):
        for page, data in self._pages(query, category, sort, pages_max):
            tree = html.fromstring(data)
            for tr in tree.cssselect('#searchResult tr:not([class="header"])'):
                log = html.tostring(tr, pretty_print=True)

                result = Result()
                try:
                    result.category = tr[0].cssselect('a')[0].text.lower()
                except Exception:
                    logger.error('failed to get category from %s', log)

                res = tr.cssselect('div.detName a')
                if not res:
                    logger.error('failed to get title from %s', log)
                    continue
                result.title = res[0].text

                result.url_magnet = self._get_magnet_url(tr)
                if not result.url_magnet:
                    logger.error('failed to get magnet url from %s', log)
                    continue

                result.hash = get_hash(result.url_magnet)
                if not result.hash:
                    logger.error('failed to get hash from %s', result.url_magnet)
                    continue

                res = tr.find_class('detDesc')
                if not res:
                    logger.error('failed to get details from %s', log)
                    continue

                details = clean(html.tostring(res[0]))
                res_ = RE_DETAILS.search(details)
                if not res_:
                    logger.error('failed to parse details: %s', details)
                    continue
                date, size = res_.groups()
                try:
                    result.size = self._get_size(size)
                except Exception, e:
                    logger.error('failed to get size from "%s": %s', size, e)
                    continue
                try:
                    result.date = self._get_date(date)
                except Exception, e:
                    logger.error('failed to get date from "%s": %s', date, e)
                    continue

                try:
                    result.seeds = int(tr[2].text)
                except Exception:
                    pass

                result.page = page
                yield result
