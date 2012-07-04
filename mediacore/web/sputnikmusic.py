import re
from datetime import datetime
from urlparse import urljoin
import logging

from lxml import html

from mediacore.web import Base
from mediacore.util.title import Title, is_url, clean


URL_REVIEWS_STAFF = 'http://www.sputnikmusic.com/staffreviews.php'
URL_REVIEWS_CONTRIB = 'http://www.sputnikmusic.com/contribreviews.php'
RE_URL_BAND = re.compile(r'/bands/', re.I)
RE_DATE_ALBUM = re.compile(r'((\d{2})/(\d{2})/)?(\d{4})\s*$')
RE_DATE_REVIEW = re.compile(r'(\d{4})-(\d{2})-(\d{2})\s.*$')
RE_SUGGESTIONS = re.compile(r'search\sresults:', re.I)


logger = logging.getLogger(__name__)


class Sputnikmusic(Base):
    URL = 'http://www.sputnikmusic.com/'

    def _get_data(self, query):
        if is_url(query):
            res = self.browser.open(query)
            if res:
                return res.get_data()

        else:
            res = self.submit_form(self.url, fields={'search_text': query})
            if not res:
                return
            data = res.get_data()
            if not data:
                return
            if not RE_SUGGESTIONS.search(data):
                return data

            re_name = Title(query).get_search_re()
            for link in self.browser.links(text_regex=re_name):
                res = self.browser.open(link.absolute_url)
                if res:
                    return res.get_data()

    def get_info(self, artist):
        data = self._get_data(artist)
        if not data:
            return
        url_band = self.browser.geturl()
        if not RE_URL_BAND.search(url_band):
            return

        info = {
            'url_band': url_band,
            'albums': [],
            }

        tree = html.fromstring(data)

        band_info = tree.cssselect('p.bandbox + table td')
        try:
            info['name'] = clean(band_info[0][0][0].text, 1)
        except Exception:
            logger.error('failed to get band name from %s', url_band)

        # Get similar bands
        for tag in tree.cssselect('p.alt2'):
            if clean(tag[0][0].text, 1) == 'similar bands':
                info['similar_bands'] = [clean(t.text, 1) for t in tag[1:]]  # skip the caption
                break

        for table in tree.cssselect('table.plaincontentbox'):

            # Get albums
            albums = []
            for tr in table:
                try:
                    if tr[0][0].get('href'):    # skip the releases categories
                        albums += tr
                except Exception:
                    pass

            for index in range(0, len(albums), 2):
                tds = albums[index:index + 2]
                if len(tds) != 2:
                    continue

                log = ''.join([html.tostring(tag, pretty_print=True) for tag in tds])

                info_album = {}
                try:
                    info_album['name'] = clean(tds[1][0][0][0][0].text, 1)
                except Exception:
                    logger.error('failed to get album name from %s', log)
                    continue
                try:
                    info_album['url'] = urljoin(self.url, tds[0][0].get('href'))
                except Exception:
                    logger.error('failed to get album url from %s', log)
                    continue
                try:
                    info_album['rating'] = float(tds[1][-1][0][0][0][0][0].text)
                except Exception:
                    info_album['rating'] = None
                try:
                    res = RE_DATE_ALBUM.search(tds[1][2].text)
                    if res:
                        info_album['date'] = int(res.group(4))
                except Exception:
                    info_album['date'] = None
                try:
                    info_album['url_cover'] = urljoin(self.url, tds[0][0][0].get('src'))
                except Exception:
                    logger.error('failed to get cover url from %s', log)

                info['albums'].append(info_album)

        return info

    def get_album_info(self, artist, album):
        info = self.get_info(artist)
        if info:
            re_album = Title(album).get_search_re()
            for res in info['albums']:
                if re_album.search(res['name']):
                    return res

    def get_query_info(self, query):
        if not self.submit_form(self.url, fields={'search_text': query}):
            return

        for link in list(self.browser.links()):
            re_artist = re.compile(r'^(%s)\s+(.*)$' % link.text, re.I)
            res = re_artist.search(query)
            if not res:
                continue

            artist_name, album_name = res.groups()
            info = self.get_info(link.absolute_url)
            if not info:
                continue

            re_album = Title(album_name).get_search_re()
            for res in info['albums']:
                if re_album.search(res['name']):
                    return res

    def reviews(self):
        for url in (URL_REVIEWS_STAFF, URL_REVIEWS_CONTRIB):
            data = self._get_data(url)
            if not data:
                logger.error('failed to get data from %s', url)
                continue

            tree = html.fromstring(data)
            for tr in tree.cssselect('tr.alt1'):
                log = html.tostring(tr, pretty_print=True)

                info = {}
                try:
                    info['artist'] = clean(tr[1][0][0][0].text, 1)
                except Exception:
                    logger.error('failed to get artist from %s', log)
                    continue
                try:
                    info['album'] = clean(tr[1][0][0][1].text, 1)
                except Exception:
                    logger.error('failed to get album from %s', log)
                    continue
                try:
                    info['rating'] = float(tr[1][1].text)
                except Exception:
                    logger.error('failed to get rating from %s', log)
                    continue
                try:
                    y, m, d = RE_DATE_REVIEW.search(tr[1][-1].text).groups()
                    info['date'] = datetime(int(y), int(m), int(d))
                except Exception:
                    logger.debug('failed to get date from %s', log)
                    continue
                try:
                    info['url_review'] = urljoin(self.url, tr[1][0].get('href'))
                except Exception:
                    logger.error('failed to get review url from %s', log)
                try:
                    info['url_thumbnail'] = urljoin(self.url, tr[0][0][0].get('src'))
                except Exception:
                    logger.error('failed to get thumbnail url from %s', log)

                yield info
