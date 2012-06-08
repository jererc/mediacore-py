import re
from urlparse import urljoin
import logging

from lxml import html

from mediacore.web import Base, WEB_EXCEPTIONS
from mediacore.util.title import Title, clean


RE_TITLE_URL = re.compile(r'/title/[\w\d]+', re.I)
RE_URLS = {
    'title': re.compile(r'/title/[\w\d]+', re.I),
    'name': re.compile(r'/name/[\w\d]+', re.I),
    }
RE_TITLE = re.compile(r'(.*)\s+\((\d{4})\)$', re.I)
RE_DATE = re.compile(r'<title>.*?\(.*?(\d{4}).*?\).*?</title>', re.I)
RE_NAMES_EXCL = re.compile(r'(more credit|full cast)', re.I)


logger = logging.getLogger(__name__)


class Imdb(Base):
    URL = 'http://www.imdb.com'

    def _get_urls(self, query, type='title'):
        try:
            self.browser.addheaders = [('Accept-Language', 'en-US,en')]
            if self.submit_form(self.URL, fields={'q': query}):
                url = self.browser.geturl()
                if RE_URLS[type].search(url):
                    return [url]

                return [r.absolute_url for r in self.browser.links(
                        text_regex=Title(query).get_search_re(),
                        url_regex=RE_URLS[type])]

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

    def _get_title_url_info(self, url):
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
                info['director'] = [clean(a.text, 1) for a in tag.cssselect('a') if not RE_NAMES_EXCL.search(a.text)]
            elif title == 'stars':
                info['stars'] = [clean(a.text, 1) for a in tag.cssselect('a') if not RE_NAMES_EXCL.search(a.text)]
            elif title == 'country':
                info['country'] = [clean(a.text, 1) for a in tag.cssselect('a')]
            elif title == 'genres':
                info['genre'] = [clean(a.text, 1) for a in tag.cssselect('a')]
            elif title == 'runtime':
                info['runtime'] = tag[1].text

        return info

    def _get_name_url_info(self, url):
        data = self._get_data(url)
        if not data:
            return

        info = {
            'url': url,
            'titles': [],
            }

        tree = html.fromstring(data)
        for div in tree.cssselect('div#knownfor div'):
            links = div.cssselect('a')
            if not links:
                continue

            title = links[-1].text
            res = RE_TITLE.search(title)
            if not res:
                logger.error('failed to get title and date from "%s"', title)
                continue

            title, date = res.groups()
            info['titles'].append({
                    'title': clean(title, 1),
                    'date': int(date),
                    'url': urljoin(self.URL, links[-1].get('href')),
                    })

        return info

    def get_info(self, query=None, url=None, type='title', year=None):
        if url:
            urls = [url]
        else:
            urls = self._get_urls(query, type=type)
            if not urls:
                return

        for url in urls:

            if type == 'title':
                res = self._get_title_url_info(url)
                if res:
                    year_ = res.get('date')
                    if year and year_ and abs(year - year_) > 1:
                        continue
                    return res

            elif type == 'name':
                for url in urls:
                    res = self._get_name_url_info(url)
                    if res:
                        return res
