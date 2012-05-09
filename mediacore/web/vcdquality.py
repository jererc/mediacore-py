import re
from datetime import datetime
from urlparse import urljoin
import logging

from lxml import html

from mediacore.web import Base, WEB_EXCEPTIONS
from mediacore.util.title import clean


logger = logging.getLogger(__name__)


class Vcdquality(Base):
    URL = 'http://www.vcdq.com'

    def _get_url(self):
        year = datetime.utcnow().year
        date_str = '%s_%s' % (year - 1, year)
        return urljoin(self.URL, 'browse/1/0/3_2/91282_19_2_2_4_9_8_3/0/%s/0/0/0/0' % date_str)

    def _next(self, page):
        try:
            return self.browser.follow_link(
                    text_regex=re.compile(r'^%s$' % page),
                    url_regex=re.compile(r'browse'))
        except Exception:
            pass

    def _get_data(self, page):
        try:
            if page > 1:
                res = self._next(page)
            else:
                self.browser.clear_history()
                res = self.browser.open(self._get_url())

            if res:
                return res.get_data()

        except WEB_EXCEPTIONS:
            pass
        except Exception:
            logger.exception('exception')

    def results(self, pages_max=1):
        for page in range(1, pages_max + 1):
            data = self._get_data(page)
            if not data:
                return

            tree = html.fromstring(data)
            for tr in tree.cssselect('tbody:not([id]) tr'):
                try:
                    title = tr.get_element_by_id('titleField')
                except Exception:
                    continue

                log = html.tostring(tr, pretty_print=True)

                try:
                    release = title.cssselect('a')[0].text
                except Exception:
                    logger.error('failed to get title from %s', log)
                    continue
                result = {'release': release}

                try:
                    date = clean(tr.get_element_by_id('dateField').text)
                    result['date'] = datetime.strptime(date, '%m-%d %Y')
                except Exception:
                    logger.error('failed to get date from %s', log)
                    continue

                result['page'] = page
                yield result
