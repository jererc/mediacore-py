import re
import logging

from lxml import html

from mediacore.web import Base, WEB_EXCEPTIONS
from mediacore.util.title import Title, clean


RE_TITLE_URL = re.compile(r'/title/[\w\d]+', re.I)
RE_DATE = re.compile(r'<title>.*?\(.*?(\d{4}).*?\).*?</title>', re.I)


logger = logging.getLogger(__name__)


class Imdb(Base):
    URL = 'http://www.imdb.com'

    def _get_movie_urls(self, query):
        try:
            self.browser.addheaders = [('Accept-Language', 'en-US,en')]
            if self.submit_form(self.URL, fields={'q': query}):
                url = self.browser.geturl()
                if RE_TITLE_URL.search(url):
                    return [url]

                return [r.absolute_url for r in self.browser.links(
                        text_regex=Title(query).get_search_re(),
                        url_regex=RE_TITLE_URL)]

        except WEB_EXCEPTIONS:
            pass
        except Exception:
            logger.exception('exception')

    def _get_data(self, url):
        try:
            self.browser.clear_history()
            res = self.browser.open(url)
            return res.get_data()
        except WEB_EXCEPTIONS:
            return
        except Exception:
            logger.exception('exception')
            return

    def _get_url_info(self, url):
        data = self._get_data(url)
        if not data:
            return

        info = {'url': url}

        res = RE_DATE.search(data)
        if res:
            info['date'] = int(res.group(1))
        else:
            logger.debug('failed to get date from %s', url)

        tree = html.fromstring(data)

        res = tree.get_element_by_id('img_primary').cssselect('img')
        if res:
            info['url_thumbnail'] = res[0].get('src')
        res = tree.cssselect('div.star-box-giga-star')
        if res:
            info['rating'] = float(clean(res[0].text))

        tags = tree.cssselect('div.txt-block') + tree.cssselect('div.inline')
        for tag in tags:
            title = clean(tag[0].text, 1)

            if title.startswith('director'):
                info['director'] = [a.text for a in tag.cssselect('a')]
            elif title == 'country':
                info['country'] = [a.text for a in tag.cssselect('a')]
            elif title == 'stars':
                info['stars'] = [a.text for a in tag.cssselect('a')]
            elif title == 'genres':
                info['genre'] = [a.text for a in tag.cssselect('a')]
            elif title == 'runtime':
                info['runtime'] = tag[1].text

        return info

    def get_info(self, query, year=None):
        urls = self._get_movie_urls(query)
        if not urls:
            return

        for url in urls:
            res = self._get_url_info(url)
            if res:
                year_ = res.get('date')
                if year and year_ and abs(year - year_) > 1:
                    continue
                return res
