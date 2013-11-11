import re
from urlparse import urljoin
import logging

from lxml import html

from filetools.title import Title, clean

from systools.system import timeout

from mediacore.web import Base


RE_URLS = {
    'title': re.compile(r'/title/[\w\d]+', re.I),
    'name': re.compile(r'/name/[\w\d]+', re.I),
    }
RE_TITLE = re.compile(r'(.*)\s+\((\d\d\d\d)\)$')
RE_DATE = re.compile(r'\b(\d\d\d\d)\b')
RE_NAMES_EXCL = re.compile(r'(more credit|full cast)', re.I)
RE_RELEASES_URLS = {
    'dvd_new': re.compile(r'DVD & Blu-Ray', re.I),
    'watch_now': re.compile(r'Watch Now', re.I),
    }
logger = logging.getLogger(__name__)


class Imdb(Base):
    URL = 'http://www.imdb.com'
    ROBUST_FACTORY = True

    def _get_urls(self, query, type='title'):
        urls = []
        self.browser.addheaders = [('Accept-Language', 'en-US,en')]
        if self.browser.submit_form(self.url, fields={'q': query}):
            url = self.browser.geturl()
            if RE_URLS[type].search(url):
                urls = [url]
            else:
                re_name = Title(query).get_search_re()
                for res in self.browser.cssselect('.result_text a', []):
                    if not re_name.search(clean(res.text)):
                        continue
                    url = urljoin(self.url, res.get('href'))
                    if not RE_URLS[type].search(url):
                        continue
                    urls.append(url)

        return urls

    def _get_title_url_info(self, url):
        if not self.browser.open(url):
            return
        info = {'url': url}

        headers = self.browser.cssselect('.header')
        if not headers:
            logger.error('failed to get title from %s' % url)
            return
        titles = headers[0].cssselect('[itemprop="name"]')
        if not titles:
            return
        info['title'] = clean(titles[0].text, 1)

        dates = headers[0].cssselect('.nobr')
        if dates:
            res = RE_DATE.search(clean(html.tostring(dates[0]), 1))
            if res:
                info['date'] = int(res.group(1))

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
            if tag is None or not len(tag):
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
                    res = RE_DATE.findall(spans[0].text)
                    if res:
                        title['date'] = int(res[0])

                info[category].append(title)

        return info

    @timeout(120)
    def get_info(self, query=None, url=None, type='title', year=None):
        urls = [url] if url else self._get_urls(query, type=type)
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
    def get_similar(self, query, type='title', year=None):
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

    @timeout(120)
    def releases(self):
        for release_type, re_release in RE_RELEASES_URLS.items():
            if not self.browser.follow_link(text_regex=re_release):
                logger.error('failed to get %s releases', release_type)
                continue

            for item in self.browser.cssselect('.list_item', []):
                log = html.tostring(item, pretty_print=True)[:1000]

                link_ = item.cssselect('.info a')
                if not link_:
                    logger.error('failed to get link from %s' % log)
                    continue

                result = {
                    'title': clean(link_[0].text, 1),
                    'url': urljoin(self.url, link_[0].get('href')),
                    }
                rating_ = item.cssselect('.rating-rating .value')
                if not rating_:
                    logger.error('failed to get rating from %s' % log)
                    continue
                try:
                    result['rating'] = float(rating_[0].text)
                except ValueError:
                    logger.error('failed to get rating from %s' % log)
                    pass

                yield result
