import re
from datetime import datetime, timedelta
import logging

from lxml import html

from filetools.title import clean, is_url

from mediacore.web import Base
from mediacore.web.search import Result, SearchError


PRIORITY = 2
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
    'date': re.compile(r'^\s*Uploaded\s*$', re.I),
    'popularity': re.compile(r'^\s*SE\s*$', re.I),
    }
RE_OVERLOAD = re.compile(r'please\s+try\s+again\s+in\s+a\s+few\s+seconds', re.I)
RE_DETAILS = re.compile(r'uploaded\s+(.*?)\s*,\s*size\s+(.*?)\s*,', re.I)
RE_DATE = re.compile(r'^(y-day|today|\d\d-\d\d|\d+)\s+(\d\d:\d\d|\d{4}|mins?\s+ago)$', re.I)

logger = logging.getLogger(__name__)


class Thepiratebay(Base):
    URL = [
        'http://thepiratebay.sx',
        'http://pirateproxy.net',
        ]

    def _get_date(self, val):
        d, t = RE_DATE.search(val).group(1, 2)
        now = datetime.now()
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

    def _next(self, page):
        return self.browser.follow_link(
                text_regex=re.compile(r'^\D*%s\D*$' % page),
                url_regex=re.compile(r'/%s/' % (page - 1), re.I))

    def _sort(self, sort):
        return self.browser.follow_link(text_regex=RE_URL_SORT[sort])

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
                            fields[val] = ['on']
                    if not self.browser.submit_form(self.url, fields=fields):
                        raise SearchError('no data')
                    self._sort(sort)

            trs = self.browser.cssselect('#searchResult tr:not([class="header"])')
            if not trs:
                if trs is None:
                    raise SearchError('no data')
                elif RE_OVERLOAD.search(self.browser.tree.text_content()):
                    raise SearchError('overload')

            for tr in trs:
                if len(tr) < 4:
                    continue

                log = html.tostring(tr, pretty_print=True)[:1000]

                result = Result()
                result.safe = False
                try:
                    result.category = tr[0].cssselect('a')[0].text.lower()
                except Exception:
                    logger.error('failed to get category from %s' % log)

                res = tr.cssselect('div.detName a')
                if not res:
                    logger.error('failed to get title from %s' % log)
                    continue
                result.title = res[0].text

                result.type = 'torrent'
                result.url = self._get_magnet_url(tr)
                if not result.url:
                    logger.error('failed to get magnet url from %s' % log)
                    continue
                if not result.get_hash():
                    continue

                res = tr.cssselect('.detDesc')
                if not res:
                    logger.error('failed to get details from %s' % log)
                    continue
                details = clean(html.tostring(res[0]))
                res_ = RE_DETAILS.search(details)
                if not res_:
                    logger.error('failed to parse details: %s' % details)
                    continue
                date, size = res_.groups()
                if not result.get_size(size):
                    continue

                if not result.validate(**kwargs):
                    continue

                try:
                    result.date = self._get_date(date)
                except Exception, e:
                    logger.error('failed to get date from "%s": %s' % (date, str(e)))
                    continue

                try:
                    result.seeds = int(tr[2].text)
                except Exception:
                    pass
                yield result
