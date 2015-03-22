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

    def releases(self, pages_max=1):
        for page in range(1, pages_max + 1):
            if page > 1:
                if not self._next(page):
                    break
            else:
                if not self.browser.open(self._get_releases_url()):
                    return

            for el in self.browser.cssselect('.container div.rls'):
                log = html.tostring(el, pretty_print=True)[:1000]

                links = el[1][0][3].cssselect('a')
                if not links:
                    continue
                result = {'release': links[0].text}

                try:
                    result['date'] = datetime.strptime(clean(el[1][0][0][0][0].text), '%d/%m/%y')
                except Exception, e:
                    logger.error('failed to get date from %s: %s', log, str(e))
                    continue

                yield result
