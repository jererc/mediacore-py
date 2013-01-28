import re
import logging

from lxml import html

from filetools.title import clean

from mediacore.web import Base


RE_NB_RESULTS = re.compile(r'(\d+)')
RE_URL_SEARCH = re.compile(r'\bsearch\b')

logger = logging.getLogger(__name__)


class Google(Base):
    URL = 'http://www.google.com'

    def _next(self, page):
        return self.browser.follow_link(
                text_regex=re.compile(r'^\D*%s\D*$' % page),
                url_regex=RE_URL_SEARCH)

    def results(self, query, pages_max=1):
        for page in range(1, pages_max + 1):
            if page > 1:
                if not self._next(page):
                    break
            else:
                self.browser.submit_form(self.url, fields={'q': query})

            for div in self.browser.cssselect('div.vsc', []):
                log = html.tostring(div, pretty_print=True)[:1000]

                links = div.cssselect('a')
                if not links:
                    logger.error('failed to get links from %s' % log)
                    continue
                title = self.get_link_text(html.tostring(links[0]))
                if not title:
                    continue
                result = {
                    'title': clean(title),
                    'url': links[0].get('href'),
                    'page': page,
                    }
                yield result

    def get_nb_results(self, query):
        '''Get the results count for a query.
        '''
        self.browser.submit_form(self.url, fields={'q': query})
        stat = self.browser.cssselect('#resultStats')
        if stat:
            res = RE_NB_RESULTS.findall(clean(stat[0].text))
            if res:
                return int(res[0])

    def get_most_popular(self, queries):
        '''Get the most popular query from a list of queries.
        '''
        stat = [(self.get_nb_results(q), q) for q in queries]
        res, query = sorted(stat)[-1]
        if res:
            return query
