import re
from urlparse import urljoin
from urllib import urlencode
import logging

from lxml import html

from filetools.title import Title, clean

from systools.system import timeout

from mediacore.web import Base


NETFLIX_CATEGORIES = {
    'movies': 'movies',
    'tv': 'tv',
    'anime': 'tv',
    }
RE_YEAR = re.compile(r'(\d\d\d\d)\b')
RE_TV = re.compile(r'\sseasons\b', re.I)

logger = logging.getLogger(__name__)


class Netflix(Base):
    URL = 'https://www.netflix.com'
    ROBUST_FACTORY = True

    def __init__(self, username, password, cookie_file=None):
        self.cookie_file = cookie_file
        super(Netflix, self).__init__(cookie_file=self.cookie_file)
        self.logged = self._login(username, password) if self.url else False

    def _is_logged(self):
        for form in self.browser.forms():
            for control in form.controls:
                if control.name == 'password':
                    return False
        return True

    def _login(self, username, password):
        if self._is_logged():
            return True

        fields = {'email': username, 'password': password}
        if not self.browser.submit_form(self.url, fields=fields):
            return False
        if not self._is_logged():
            logger.error('failed to login as %s' % username)
            return False

        self.save_cookie(self.cookie_file)
        return True

    @timeout(120)
    def get_info(self, query, category='movies', year=None):
        url = urljoin(self.url, '/WiSearch?%s' % urlencode({'v1': query}))
        self.browser.open(url)

        re_q = Title(query).get_search_re()
        for div in self.browser.cssselect('.mresult', []):
            log = html.tostring(div, pretty_print=True)[:1000]

            duration_ = div.cssselect('.duration')
            if not duration_:
                continue
            category_ = 'tv' if RE_TV.search(duration_[0].text) else 'movies'
            if NETFLIX_CATEGORIES.get(category) != category_:
                continue

            info = {}

            title_ = div.cssselect('.title a')
            if not title_:
                logger.error('failed to get title from %s' % log)
                continue
            info['title'] = clean(title_[0].text, 1)
            if not re_q.search(info['title']):
                continue
            info['url'] = urljoin(self.url, title_[0].get('href'))

            year_ = div.cssselect('.year')
            if not year_:
                logger.error('failed to get year from %s' % log)
                continue
            res = RE_YEAR.search(year_[0].text)
            if not res:
                logger.error('failed to get year from %s' % year_[0].text)
                continue
            info['year'] = int(res.group(1))
            if year and abs(year - info['year']) > 1:
                continue

            return info
