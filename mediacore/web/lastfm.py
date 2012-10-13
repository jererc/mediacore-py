import re
from urlparse import urljoin
import logging

from lxml import html

from mediacore.web import Base
from mediacore.util.title import Title, clean


MIN_ALBUM_TRACKS = 4
MAX_ALBUMS_PAGES = 10
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

    def _artist_albums(self, url):
        tree = None
        for i in range(MAX_ALBUMS_PAGES):
            if tree is not None:
                links = tree.cssselect('.pagination .nextlink')
                if not links or not self.check_next_link(links[-1]):
                    return
                url = urljoin(self.url, links[-1].get('href'))

            data = self.browser.get_unicode_data(url=url)
            if not data:
                return

            tree = html.fromstring(data)
            for tag in tree.cssselect('.album-item'):
                log = html.tostring(tag, pretty_print=True)

                meta_tags = tag.cssselect('[itemprop="name"]')
                if not meta_tags:
                    continue

                name = clean(meta_tags[0].get('content', ''), 1)
                if not name:
                    continue
                info_album = {'name': name}

                url_tags = tag.cssselect('a')
                if not url_tags:
                    logger.error('failed to get album url from %s', log)
                else:
                    info_album['url'] = urljoin(self.url, url_tags[0].get('href'))

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

                yield info_album

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
            logger.debug('failed to find albums link for "%s" at %s', query, url)
            return info
        elif not RE_ALBUMS.search(links[0].text):
            return

        url_albums = urljoin(self.url, links[0].get('href'))
        for info_album in self._artist_albums(url_albums):
            if info.get('genre'):
                info_album['genre'] = info['genre']
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

    def _get_similar_url(self, query):
        url = self._get_artist_url(query)
        data = self.browser.get_unicode_data(url=url)
        if not data:
            return

        tree = html.fromstring(data)
        links = tree.cssselect('.similar-artists a')
        if links and RE_SIMILAR.search(links[0].text):
            return urljoin(self.url, links[0].get('href'))

        logger.error('failed to find similar artists link for %s at %s', query, url)

    def _similar_artists(self, url):
        tree = None
        for i in range(MAX_SIMILAR_PAGES):
            if tree is not None:
                links = tree.cssselect('.pagination .nextlink')
                if not links or not self.check_next_link(links[-1]):
                    return
                url = urljoin(self.url, links[-1].get('href'))

            data = self.browser.get_unicode_data(url=url)
            if not data:
                return

            tree = html.fromstring(data)
            for tag in tree.cssselect('.link-reference h3'):
                yield clean(tag.text, 1)

    def get_similar(self, query):
        '''Get similar artists.
        '''
        url = self._get_similar_url(query)
        return list(self._similar_artists(url))
