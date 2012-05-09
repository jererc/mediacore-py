import re
import logging

from lxml import html

from mediacore.web import Base, WEB_EXCEPTIONS
from mediacore.util.title import clean


RE_NB_RESULTS = re.compile(r'(\d+)')
RE_URL_SEARCH = re.compile(r'\bsearch\b')


logger = logging.getLogger(__name__)


class Google(Base):
    URL = 'http://www.google.com'

    def _next(self, page):
        try:
            return self.browser.follow_link(
                text_regex=re.compile(r'^\D*%s\D*$' % page),
                url_regex=RE_URL_SEARCH)
        except Exception:
            pass

    def _pages(self, query, pages_max=1):
        for page in range(1, pages_max + 1):
            data = None
            try:
                if page > 1:
                    res = self._next(page)
                else:
                    self.browser.clear_history()
                    res = self.submit_form(self.URL, fields={'q': query})

                if res:
                    data = res.get_data()
            except WEB_EXCEPTIONS:
                pass
            except Exception:
                logger.exception('exception')

            if not data:
                return
            yield page, data

    def results(self, query, pages_max=1):
        for page, data in self._pages(query, pages_max):
            tree = html.fromstring(data)
            for div in tree.cssselect('div.vsc'):
                log = html.tostring(div, pretty_print=True)

                links = div.cssselect('a')
                if not links:
                    logger.error('failed to get links from %s', log)
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
        res = list(self._pages(query, 1))
        if not res:
            return

        tree = html.fromstring(res[0][1])
        div = tree.get_element_by_id('resultStats')
        res = RE_NB_RESULTS.search(clean(div.text))
        if res:
            return int(res.group(1))

    def get_most_popular(self, queries):
        '''Get the most popular query from a list of queries.
        '''
        stat = [(self.get_nb_results(q), q) for q in queries]
        res, query = sorted(stat)[-1]
        if res:
            return query
