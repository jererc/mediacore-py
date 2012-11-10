import re
from urlparse import urljoin
import logging

from lxml import html

from filetools.title import Title, clean

from mediacore.web import Base


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
        self.browser.submit_form(self.url, fields={'q': query})
        for tag in self.browser.cssselect('#artistResults a', []):
            if RE_ARTISTS.search(tag.text):
                return urljoin(self.url, self._clean_url(tag.get('href')))

    def _get_artist_url(self, query):
        url = self._get_results_url(query)
        if not url:
            return
        re_name = Title(query).get_search_re()
        self.browser.open(url)
        for tag in self.browser.cssselect('.artistsWithInfo li', []):
            links = tag.cssselect('a')
            if links:
                artist = clean(self.get_link_text(html.tostring(links[0])))
                if re_name.search(artist):
                    return urljoin(self.url, self._clean_url(links[0].get('href')))

    def _artist_albums(self, url, pages_max):
        for i in range(pages_max):
            if i > 0:
                links = self.browser.cssselect('.pagination .nextlink')
                if not links or not self.check_next_link(links[-1]):
                    return
                url = urljoin(self.url, links[-1].get('href'))

            self.browser.open(url)
            for tag in self.browser.cssselect('.album-item', []):
                log = html.tostring(tag, pretty_print=True)[:1000]

                meta_tags = tag.cssselect('[itemprop="name"]')
                if not meta_tags:
                    continue
                name = clean(meta_tags[0].get('content', ''), 1)
                if not name:
                    continue
                info_album = {'name': name}

                url_tags = tag.cssselect('a')
                if url_tags:
                    info_album['url'] = urljoin(self.url, url_tags[0].get('href'))
                else:
                    logger.error('failed to get album url from %s' % log)

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

    def _get_info(self, query, pages_max):
        url = self._get_artist_url(query)
        if not url:
            return
        self.browser.open(url)

        info = {
            'url_band': url,
            'albums': [],
            }

        genre = []
        for tag in self.browser.cssselect('.tags li a', []):
            if not RE_MORE_TAGS.search(tag.text):
                genre.append(clean(tag.text))
        if genre:
            info['genre'] = genre

        # Get albums
        links = self.browser.cssselect('.artist-top-albums a')
        if not links:
            logger.debug('failed to find albums link for "%s" at %s', query, url)
            return info
        elif not RE_ALBUMS.search(links[0].text):
            return

        url_albums = urljoin(self.url, links[0].get('href'))
        for info_album in self._artist_albums(url_albums, pages_max):
            if info.get('genre'):
                info_album['genre'] = info['genre']
            info['albums'].append(info_album)

        return info

    def get_info(self, artist, album=None, pages_max=MAX_ALBUMS_PAGES):
        info = self._get_info(artist, pages_max)
        if not album:
            return info
        if info:
            re_album = Title(album).get_search_re()
            for res in info['albums']:
                if re_album.search(res['name']):
                    return res

    def _get_similar_url(self, query):
        url = self._get_artist_url(query)
        if not url:
            return
        self.browser.open(url)
        links = self.browser.cssselect('.similar-artists a')
        if links and RE_SIMILAR.search(links[0].text):
            return urljoin(self.url, links[0].get('href'))
        logger.error('failed to find similar artists link for %s at %s', query, url)

    def _similar_artists(self, url, pages_max):
        for i in range(pages_max):
            if i > 0:
                links = self.browser.cssselect('.pagination .nextlink')
                if not links or not self.check_next_link(links[-1]):
                    return
                url = urljoin(self.url, links[-1].get('href'))

            self.browser.open(url)
            for tag in self.browser.cssselect('.link-reference h3', []):
                yield clean(tag.text, 1)

    def get_similar(self, query, pages_max=MAX_SIMILAR_PAGES):
        '''Get similar artists.
        '''
        url = self._get_similar_url(query)
        return list(self._similar_artists(url, pages_max))
