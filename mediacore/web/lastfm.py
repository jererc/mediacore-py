import re
from urlparse import urljoin
import logging

from lxml import html

from mediacore.web import Base
from mediacore.util.title import Title, clean


MIN_ALBUM_TRACKS = 4
MAX_SIMILAR_PAGES = 10
RE_ARTISTS = re.compile(r'more artists', re.I)
RE_ALBUMS = re.compile(r'top albums', re.I)
RE_SIMILAR = re.compile(r'similar artists', re.I)
RE_DATE_ALBUM = re.compile(r'^\b(\d{4})\b')
RE_MORE_TAGS = re.compile(r'more tags', re.I)


logger = logging.getLogger(__name__)


class Lastfm(Base):
    URL = 'http://www.last.fm/music'
    ROBUST_FACTORY = True

    def _clean_url(self, url):
        return url.replace(' ', '+')

    def _get_results_url(self, query):
        res = self.submit_form(self.url, fields={'q': query})
        data = self.browser.get_unicode_data(response=res)
        if not data:
            return

        tree = html.fromstring(data)
        for tag in tree.cssselect('#artistResults a'):
            if RE_ARTISTS.search(tag.text):
                return urljoin(self.url, self._clean_url(tag.get('href')))

    def _get_artist_url(self, query):
        url = self._get_results_url(query)
        data = self.browser.get_unicode_data(url=url)
        if not data:
            return

        re_name = Title(query).get_search_re()
        tree = html.fromstring(data)
        for tag in tree.cssselect('.artistsWithInfo li'):
            links = tag.cssselect('a')
            if links:
                artist = clean(self.get_link_text(html.tostring(links[0])))
                if re_name.search(artist):
                    return urljoin(self.url, self._clean_url(links[0].get('href')))

    def _get_albums_url(self, query):
        url = self._get_artist_url(query)
        if not url:
            return
        data = self.browser.get_unicode_data(url=url)
        if not data:
            return

        tree = html.fromstring(data)
        links = tree.cssselect('.artist-top-albums a')
        if not links:
            logger.debug('failed to find artist albums link for "%s" at %s', query, url)
        elif RE_ALBUMS.search(links[0].text):
            return urljoin(self.url, links[0].get('href'))

    def _get_info(self, query):
        url = self._get_artist_url(query)
        data = self.browser.get_unicode_data(url=url)
        if not data:
            return

        info = {
            'url_band': url,
            'albums': [],
            }

        tree = html.fromstring(data)
        genre = []
        for tag in tree.cssselect('.tags li a'):
            if not RE_MORE_TAGS.search(tag.text):
                genre.append(clean(tag.text))
        if genre:
            info['genre'] = genre

        # Get albums
        links = tree.cssselect('.artist-top-albums a')
        if not links:
            logger.debug('failed to find artist albums link for "%s" at %s', query, url)
            return info
        elif not RE_ALBUMS.search(links[0].text):
            return

        url_albums = urljoin(self.url, links[0].get('href'))
        data = self.browser.get_unicode_data(url=url_albums)
        if not data:
            return

        tree = html.fromstring(data)
        for tag in tree.cssselect('.albums li .album-item-detail-wrapper'):
            log = html.tostring(tag, pretty_print=True)

            info_album = {}
            if info.get('genre'):
                info_album['genre'] = info['genre']

            try:
                info_album['name'] = clean(html.tostring(tag[0][0]), 1)
            except Exception:
                logger.error('failed to get album name from %s', log)
                continue
            if not info_album['name']:
                continue
            try:
                info_album['url'] = urljoin(self.url, tag[0][0].get('href'))
            except Exception:
                logger.error('failed to get album url from %s', log)

            date_tags = tag.cssselect('time')
            if not date_tags:
                continue
            try:
                date = RE_DATE_ALBUM.search(date_tags[0].get('datetime'))
                info_album['date'] = int(date.group(1))
            except Exception:
                continue

            # Check nb tracks
            tracks_tags = tag.cssselect('[itemprop="numTracks"]')
            if not tracks_tags:
                continue
            try:
                nb_tracks = int(tracks_tags[0].text)
            except ValueError:
                continue
            if nb_tracks < MIN_ALBUM_TRACKS:
                continue

            info['albums'].append(info_album)

        if not info['albums']:
            logger.debug('failed to get albums from "%s"', query)

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

    def _get_similar_url(self, query):
        url = self._get_artist_url(query)
        data = self.browser.get_unicode_data(url=url)
        if not data:
            return

        tree = html.fromstring(data)
        links = tree.cssselect('.similar-artists a')
        if not links:
            logger.error('failed to find similar artists link for %s at %s', query, url)
        elif RE_SIMILAR.search(links[0].text):
            return urljoin(self.url, links[0].get('href'))

    def _similar_artists(self, url):
        for i in range(MAX_SIMILAR_PAGES):
            data = self.browser.get_unicode_data(url=url)
            if not data:
                return

            tree = html.fromstring(data)
            for tag in tree.cssselect('.artistsWithInfo li'):
                links = tag.cssselect('a')
                if links:
                    yield clean(self.get_link_text(html.tostring(links[0])), 1)

            next_link = tree.cssselect('.pagination .nextlink')
            if not next_link:
                return
            url = urljoin(self.url, next_link[0].get('href'))

    def get_similar(self, query):
        '''Get similar artists.
        '''
        url = self._get_similar_url(query)
        return list(self._similar_artists(url))
