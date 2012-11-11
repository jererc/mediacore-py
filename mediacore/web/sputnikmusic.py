import re
from datetime import datetime
from urlparse import urljoin
import logging

from lxml import html

from filetools.title import Title, clean

from mediacore.web import Base


URL_REVIEWS_STAFF = 'http://www.sputnikmusic.com/staffreviews.php'
URL_REVIEWS_CONTRIB = 'http://www.sputnikmusic.com/contribreviews.php'
RE_URL_BAND = re.compile(r'/bands/', re.I)
RE_DATE_ALBUM = re.compile(r'((\d{2})/(\d{2})/)?(\d{4})\s*$')
RE_DATE_REVIEW = re.compile(r'(\d{4})-(\d{2})-(\d{2})\s.*$')
RE_SUGGESTIONS = re.compile(r'search results:', re.I)

logger = logging.getLogger(__name__)


class Sputnikmusic(Base):
    URL = 'http://www.sputnikmusic.com/'

    def _get_band_url(self, artist):
        if not self.browser.submit_form(self.url,
                fields={'search_text': artist}):
            return
        if RE_SUGGESTIONS.search(self.browser.tree.text_content()):
            re_name = Title(artist).get_search_re()
            if not self.browser.follow_link(text_regex=re_name):
                return
        url = self.browser.geturl()
        if RE_URL_BAND.search(url):
            return url

    def _get_info(self, artist):
        url = self._get_band_url(artist)
        if not url:
            return
        info = {
            'url_band': url,
            'albums': [],
            }

        # Get band info
        band_info = self.browser.cssselect('table.bandbox td')
        try:
            info['name'] = clean(band_info[0][0][0].text, 1)
        except Exception:
            logger.error('failed to get band name from %s' % url)
        try:
            info['genre'] = [clean(t.text, 1) for t in band_info[0][1] if t.text]
        except Exception:
            logger.error('failed to get band genre from %s' % url)

        for table in self.browser.cssselect('table.plaincontentbox', []):
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

                log = ''.join([html.tostring(tag, pretty_print=True) for tag in tds])[:1000]

                info_album = {}
                if info.get('genre'):
                    info_album['genre'] = info['genre']

                try:
                    info_album['name'] = clean(tds[1][0][0][0][0].text, 1)
                except Exception:
                    logger.error('failed to get album name from %s' % log)
                    continue
                if not info_album['name']:
                    continue
                try:
                    info_album['url'] = urljoin(self.url, tds[0][0].get('href'))
                except Exception:
                    logger.error('failed to get album url from %s' % log)
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
                    logger.error('failed to get cover url from %s' % log)

                info['albums'].append(info_album)

        return info

    def get_info(self, artist, album=None):
        info = self._get_info(artist)
        if not album:
            return info
        if info:
            re_album = Title(album).get_search_re()
            for res in info['albums']:
                if re_album.search(res['name']):
                    return res

    def get_similar(self, artist):
        '''Get similar artists.
        '''
        res = []
        url = self._get_band_url(artist)
        if url:
            for tag in self.browser.cssselect('p.alt2', []):
                if clean(tag[0][0].text, 1) == 'similar bands':
                    for tag_ in tag[1:]:
                        res.append({
                            'title': clean(tag_.text, 1),
                            'url': urljoin(self.url, tag_.get('href'))
                            })
                    break
        return res

    def reviews(self):
        for url in (URL_REVIEWS_STAFF, URL_REVIEWS_CONTRIB):
            self.browser.open(url)
            for tr in self.browser.cssselect('tr.alt1', []):
                log = html.tostring(tr, pretty_print=True)[:1000]

                info = {}
                try:
                    info['artist'] = clean(tr[1][0][0][0].text, 1)
                except Exception:
                    logger.error('failed to get artist from %s' % log)
                    continue
                try:
                    info['album'] = clean(tr[1][0][0][1].text, 1)
                except Exception:
                    logger.error('failed to get album from %s' % log)
                    continue
                try:
                    info['rating'] = float(tr[1][1].text)
                except Exception:
                    logger.error('failed to get rating from %s' % log)
                    continue
                try:
                    y, m, d = RE_DATE_REVIEW.search(tr[1][-1].text).groups()
                    info['date'] = datetime(int(y), int(m), int(d))
                except Exception:
                    logger.debug('failed to get date from %s' % log)
                    continue
                try:
                    info['url_review'] = urljoin(self.url, tr[1][0].get('href'))
                except Exception:
                    logger.error('failed to get review url from %s' % log)
                try:
                    info['url_thumbnail'] = urljoin(self.url, tr[0][0][0].get('src'))
                except Exception:
                    logger.error('failed to get thumbnail url from %s' % log)

                yield info
