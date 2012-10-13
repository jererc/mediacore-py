import re
from datetime import datetime
from urlparse import urljoin
import logging

from lxml import html

from mediacore.web import Base


RE_DATE = re.compile(r'\d{2}-\d{2} \d{4}')

logger = logging.getLogger(__name__)


class Vcdquality(Base):
    URL = 'http://www.vcdq.com'

    def _get_releases_url(self):
        year = datetime.utcnow().year
        date_str = '%s_%s' % (year - 1, year)
        return urljoin(self.url, 'browse/1/0/3_2/91282_19_2_2_4_9_8_3/0/%s/0/0/0/0' % date_str)

    def _next(self, page):
        return self.browser.follow_link(
                text_regex=re.compile(r'^%s$' % page),
                url_regex=re.compile(r'browse'))

    def _pages(self, pages_max=1):
        for page in range(1, pages_max + 1):
            if page > 1:
                res = self._next(page)
            else:
                self.browser.clear_history()
                res = self.browser.open(self._get_releases_url())

            if res:
                data = res.get_data()
                if data:
                    yield page, data

    def results(self, pages_max=1):
        for page, data in self._pages(pages_max):
            tree = html.fromstring(data)

            tbodys = tree.cssselect('#searchResult tbody')
            if not tbodys:
                logger.error('failed to get results')
                continue

            for tr in tbodys[-1].cssselect('tr'):
                log = html.tostring(tr, pretty_print=True)

                tags = tr.cssselect('.titleField a')
                if not tags:
                    continue
                result = {'release': tags[0].text}

                res = RE_DATE.findall(html.tostring(tr))
                if not res:
                    logger.error('failed to get date from %s', log)
                    continue
                result['date'] = datetime.strptime(res[0], '%m-%d %Y')

                result['page'] = page
                yield result
