import re
from datetime import datetime
from urlparse import urljoin
import logging

from lxml import html

from filetools.title import clean

from mediacore.web import Base


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

    def results(self, pages_max=1):
        self.browser.clear_history()

        for page in range(1, pages_max + 1):
            if page > 1:
                if not self._next(page):
                    break
            else:
                self.browser.open(self._get_releases_url())

            tbodys = self.browser.cssselect('#searchResult tbody')
            if not tbodys:
                logger.error('failed to get results from %s' % self.browser.geturl())
                continue

            for tr in tbodys[-1].cssselect('tr'):
                log = html.tostring(tr, pretty_print=True)[:1000]

                links = tr.cssselect('.titleField a')
                if not links:
                    continue
                result = {'release': links[0].text}

                dates = tr.cssselect('.dateField')
                if not dates:
                    logger.error('failed to get date from %s', log)
                    continue
                date_ = clean(dates[0].text)
                result['date'] = datetime.strptime('%s %s' % (date_, datetime.utcnow().year), '%d %b %Y')

                yield result
