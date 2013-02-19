import re
from urlparse import urljoin
import logging

from filetools.title import Title, clean

from systools.system import timeout

from mediacore.web import Base


RE_URLS = {
    'title': re.compile(r'/title/[\w\d]+', re.I),
    'name': re.compile(r'/name/[\w\d]+', re.I),
    }
RE_TITLE = re.compile(r'(.*)\s+\((\d{4})\)$')
RE_DATE = re.compile(r'.*?\(.*?(\d{4}).*?\).*?')
RE_LIST_DATE = re.compile(r'\b(\d{4})\b')
RE_NAMES_EXCL = re.compile(r'(more credit|full cast)', re.I)

logger = logging.getLogger(__name__)


class Imdb(Base):
    URL = 'http://www.imdb.com'
    ROBUST_FACTORY = True

    def _get_urls(self, query, type='title'):
        self.browser.addheaders = [('Accept-Language', 'en-US,en')]
        if self.browser.submit_form(self.url, fields={'q': query}):
            url = self.browser.geturl()
            if RE_URLS[type].search(url):
                return [url]
            return [r.absolute_url for r in self.browser.links(
                    text_regex=Title(query).get_search_re(),
                    url_regex=RE_URLS[type])]

    def _get_date(self):
        res = self.browser.cssselect('title')
        if res:
            date = RE_DATE.findall(res[0].text)
            if date:
                return int(date[0])

    def _get_title_url_info(self, url):
        if not self.browser.open(url):
            return
        info = {'url': url}

        date = self._get_date()
        if date:
            info['date'] = date
        else:
            logger.debug('failed to get date from %s' % url)

        res = self.browser.cssselect('#img_primary img')
        if res:
            info['url_thumbnail'] = res[0].get('src')

        res = self.browser.cssselect('div.star-box-giga-star')
        if res:
            info['rating'] = float(clean(res[0].text))

        res = self.browser.cssselect('.infobar')
        if res:
            info['details'] = clean(res[0].text, 1)

        tags = self.browser.cssselect('div.txt-block', []) + self.browser.cssselect('div.inline', [])
        for tag in tags:
            if tag is None:
                continue
            title = clean(tag[0].text, 1)
            if title.startswith('director'):
                info['director'] = [clean(a.text, 1) for a in tag.cssselect('a span') if not RE_NAMES_EXCL.search(a.text)]
            elif title == 'stars':
                info['stars'] = [clean(a.text, 1) for a in tag.cssselect('a span') if not RE_NAMES_EXCL.search(a.text)]
            elif title == 'country':
                info['country'] = [clean(a.text, 1) for a in tag.cssselect('a')]
            elif title == 'genres':
                info['genre'] = [clean(a.text, 1) for a in tag.cssselect('a')]
            elif title == 'runtime':
                info['runtime'] = tag[1].text

        return info

    def _get_name_url_info(self, url):
        if not self.browser.open(url):
            return
        info = {
            'url': url,
            'titles_known_for': [],
            'titles_director': [],
            'titles_actor': [],
            }

        # Get "known for" titles
        for div in self.browser.cssselect('div#knownfor div', []):
            links = div.cssselect('a')
            if not links:
                continue

            title = links[-1].text
            res = RE_TITLE.search(title)
            if not res:
                logger.error('failed to get title and date from "%s"' % title)
                continue

            title, date = res.groups()
            info['titles_known_for'].append({
                    'title': clean(title, 1),
                    'date': int(date),
                    'url': urljoin(self.url, links[-1].get('href')),
                    })

        # Get filmography
        category = None
        for div in self.browser.cssselect('div', []):
            id_ = div.get('id')
            if id_ == 'filmo-head-Director':
                category = 'titles_director'
            elif id_ == 'filmo-head-Actor':
                category = 'titles_actor'
            elif id_:
                category = None

            class_ = div.get('class')
            if category and class_ and 'filmo-row' in class_:
                links = div.cssselect('a')
                if not links:
                    continue
                title = {
                    'title': clean(links[0].text, 1),
                    'url': urljoin(self.url, links[0].get('href')),
                    }

                # Get date
                spans = div.cssselect('span')
                if spans:
                    res = RE_LIST_DATE.findall(spans[0].text)
                    if res:
                        title['date'] = int(res[0])

                info[category].append(title)

        return info

    @timeout(120)
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

    @timeout(120)
    def get_similar(self, query=None, type='title', year=None):
        '''Get similar movies.
        '''
        if type == 'name':
            names = [query]
        else:
            info = self.get_info(query=query, type=type, year=year) or {}
            names = info.get('director', []) + info.get('stars', [])

        res = []
        for name in names:
            info = self.get_info(query=name, type='name') or {}
            res.extend(info.get('titles_known_for', []))

        return res
