import re
from urlparse import urljoin
import logging

from lxml import html

from filetools.title import Title, clean

from systools.system import timeout

from mediacore.web import Base, Browser


URLS = {
    'dvd_new': 'http://www.rottentomatoes.com/dvd/new-releases',
    'dvd_current': 'http://www.rottentomatoes.com/dvd/current_releases.php',
    }
RE_INVALID_IMG = re.compile(r'\bposter_default\b', re.I)
RE_RATING = re.compile(r'(\d+)')

logger = logging.getLogger(__name__)


class Rottentomatoes(Base):
    URL = 'http://www.rottentomatoes.com/'

    def _get_thumbnail_url(self, url):
        browser = Browser()
        browser.open(url)
        img_ = browser.cssselect('.movie_poster_area img')
        if img_:
            url = img_[0].get('src')
            if not RE_INVALID_IMG.search(url):
                return url

    @timeout(120)
    def get_info(self, query):
        if not self.browser.submit_form(self.url,
                fields={'search': query}):
            return

        info = {}

        re_q = Title(query).get_search_re()
        for li in self.browser.cssselect('#movie_results_ul li', []):
            log = html.tostring(li, pretty_print=True)[:1000]

            rating_ = li.cssselect('.tMeterScore')
            if not rating_:
                continue
            res = RE_RATING.search(rating_[0].text)
            if not res:
                logger.error('failed to get rating from "%s"', log)
                continue
            info['rating'] = int(res.group(1))

            title_ = li.cssselect('.nomargin a')
            if not title_:
                logger.error('failed to get title from %s', log)
                continue
            info['title'] = clean(title_[0].text, 1)
            if not re_q.search(info['title']):
                continue
            info['url'] = urljoin(self.url, title_[0].get('href'))

            url = self._get_thumbnail_url(info['url'])
            if url:
                info['url_thumbnail'] = url
            return info

    def _releases(self, type, pages_max):
        url_root = URLS.get(type)
        if not url_root:
            logger.error('unhandled release type "%s"', type)
            return
        url = url_root

        for i in range(pages_max):
            if i > 0:
                links = self.browser.cssselect('a.pagination.right:not(.disabled)')
                if not links:
                    return
                url = urljoin(url_root, links[-1].get('href'))
            self.browser.open(url)

            for div in self.browser.cssselect('.movie_item', []):
                log = html.tostring(div, pretty_print=True)[:1000]

                info = {}

                title_ = div.cssselect('.heading a')
                if not title_:
                    continue
                info['title'] = clean(title_[0].text, 1)
                info['url'] = urljoin(self.url, title_[0].get('href'))

                rating_ = div.cssselect('.tMeterScore')
                if not rating_:
                    continue
                res = RE_RATING.search(rating_[0].text)
                if not res:
                    logger.error('failed to get rating from "%s"', log)
                    continue
                info['rating'] = int(res.group(1))

                yield info

    @timeout(120)
    def releases(self, types, pages_max=5):
        if not isinstance(types, (list, tuple)):
            types = [types]
        for type in types:
            for res in self._releases(type, pages_max):
                yield res
