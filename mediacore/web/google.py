import re
from urlparse import urlparse, urljoin
import logging

from lxml import html

from filetools.title import clean

from mediacore.web import Base


RE_NB_RESULTS = re.compile(r'([\d,\s]+)')
RE_URL_SEARCH = re.compile(r'\bsearch\b')

logger = logging.getLogger(__name__)


class Google(Base):
    URL = 'http://www.google.com'
    ROBUST_FACTORY = True

    def _next(self, page):
        for link in self.browser.cssselect('#nav a'):
            try:
                page_ = int(clean(self.get_link_text(html.tostring(link))))
            except ValueError:
                continue
            if page_ == page:
                url = urljoin(self.url, link.get('href'))
                return self.browser.open(url)

    def results(self, query, pages_max=1):
        for page in range(1, pages_max + 1):
            if page > 1:
                if not self._next(page):
                    break
            else:
                self.browser.submit_form(self.url, fields={'q': query})

            for li in self.browser.cssselect('li.g', []):
                log = html.tostring(li, pretty_print=True)[:1000]

                links = li.cssselect('a')
                if not links:
                    logger.error('failed to get links from %s', log)
                    continue
                url = links[0].get('href')
                if not url or not urlparse(url).scheme:
                    continue
                title = clean(self.get_link_text(html.tostring(links[0])))
                if not title:
                    continue
                yield {
                    'title': title,
                    'url': url,
                    'page': page,
                    }

    def get_results_count(self, query):
        '''Get the results count for a query.
        '''
        self.browser.submit_form(self.url, fields={'q': query})
        stat = self.browser.cssselect('#resultStats')
        if stat:
            res = RE_NB_RESULTS.findall(clean(stat[0].text))
            if res:
                nb = re.sub(r'\D+', '', res[0])
                return int(nb)

    def get_most_popular(self, queries):
        '''Get the most popular query from a list of queries.
        '''
        stat = [(self.get_results_count(q), q) for q in queries]
        res, query = sorted(stat)[-1]
        if res:
            return query
