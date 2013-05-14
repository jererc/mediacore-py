import re
from datetime import datetime
from urlparse import urljoin
import logging

from lxml import html

from filetools.title import Title, clean

from systools.system import timeout

from mediacore.web import Base, Browser


URLS = {
    'movies_dvd': 'http://www.metacritic.com/browse/dvds/release-date/new-releases/date',
    'movies_theater': 'http://www.metacritic.com/browse/movies/release-date/theaters/date',
    'music_new': 'http://www.metacritic.com/browse/albums/release-date/new-releases/date',
    }
CAT_DEF = {
    'anime': re.compile(r'\b(movie|tv\sshow)\b', re.I),
    'games': re.compile(r'\bgames\b', re.I),
    'movies': re.compile(r'\bmovie\b', re.I),
    'music': re.compile(r'\balbum\b', re.I),
    'tv': re.compile(r'\btv\sshow\b', re.I),
    }
RE_DATE = re.compile(r'(\w+)\s+(\d+)')
RE_NA_SCORE = re.compile(r'\btbd\b', re.I)

logger = logging.getLogger(__name__)


class Metacritic(Base):
    URL = 'http://www.metacritic.com/'

    def _get_media_info(self, url):
        browser = Browser()
        browser.open(url)

        info = {}

        band_ = browser.cssselect('.band_name')
        if band_:
            info['artist'] = clean(band_[0].text, 1)

        genre_ = browser.cssselect('.product_genre .data')
        if genre_:
            info['genre'] = [clean(g, 1) for g in genre_[0].text.split(',')]

        return info

    @timeout(120)
    def get_info(self, query, category, artist=None):
        re_cat = CAT_DEF.get(category)
        if not re_cat:
            logger.error('unknown category %s' % category)
            return
        if not self.browser.submit_form(self.url,
                fields={'search_term': query}):
            return

        info = {}

        re_q = Title(query).get_search_re()
        re_artist = Title(artist).get_search_re() if artist else None
        for li in self.browser.cssselect('.search_results li.result', []):
            log = html.tostring(li, pretty_print=True)[:1000]

            type_ = li.cssselect('.result_type')
            if not type_:
                logger.error('failed to get type from %s' % log)
                continue
            if not re_cat.search(clean(type_[0][0].text, 1)):
                continue

            title_ = li.cssselect('.product_title a')
            if not title_:
                logger.error('failed to get title from %s' % log)
                continue
            info['title'] = clean(title_[0].text, 1)
            if not re_q.search(info['title']):
                continue
            info['url'] = urljoin(self.url, title_[0].get('href'))

            scores = []
            rating_ = li.cssselect('.metascore')
            if rating_:
                try:
                    scores.append(int(rating_[0].text))
                except ValueError:
                    if not RE_NA_SCORE.search(rating_[0].text):
                        logger.error('failed to get metascore from "%s"' % log)
            rating_ = li.cssselect('.textscore')
            if rating_:
                try:
                    scores.append(int(float(rating_[0].text) * 10))
                except ValueError:
                    if not RE_NA_SCORE.search(rating_[0].text):
                        logger.error('failed to get user score from %s' % html.tostring(rating_[0]))
            if scores:
                info['rating'] = sum(scores) / len(scores)

            info.update(self._get_media_info(info['url']))

            if re_artist and not re_artist.search(info.get('artist', '')):
                continue

            return info

    def _releases(self, type):
        url = URLS.get(type)
        if not url:
            logger.error('unhandled release type "%s"' % type)
            return
        self.browser.open(url)

        now = datetime.utcnow()
        year = now.year

        for li in self.browser.cssselect('li.product', []):
            log = html.tostring(li, pretty_print=True)[:1000]

            info = {}

            title_ = li.cssselect('.product_title a')
            if not title_:
                continue
            info['title'] = clean(title_[0].text, 1)
            info['url'] = urljoin(self.url, title_[0].get('href'))

            if type.startswith('music_'):
                artist_ = li.cssselect('.product_artist .data')
                if not artist_:
                    continue
                info['artist'] = clean(artist_[0].text, 1)

            rating_ = li.cssselect('.metascore')
            if not rating_:
                continue
            try:
                info['rating'] = int(rating_[0].text)
            except ValueError:
                if not RE_NA_SCORE.search(rating_[0].text):
                    logger.error('failed to get rating from "%s"' % log)
                continue

            date_ = li.cssselect('.release_date .data')
            if not date_:
                continue
            res = RE_DATE.search(date_[0].text)
            if not res:
                logger.error('failed to get date from "%s"' % log)
                continue
            date_str = '%s %s %02d' % (year, res.group(1).lower(), int(res.group(2)))
            date = datetime.strptime(date_str, '%Y %b %d')
            if date > now:
                date = datetime(date.year - 1, date.month, date.day)
            info['date'] = date

            yield info

    @timeout(120)
    def releases(self, types):
        if not isinstance(types, (list, tuple)):
            types = [types]
        for type in types:
            for res in self._releases(type):
                yield res
