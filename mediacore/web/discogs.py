import re
import logging

import discogs_client as discogs

from filetools.title import Title, clean


RE_DATE_ALBUM = re.compile(r'(\d{4})(-(\d{2})-(\d{2}))?$')

logger = logging.getLogger(__name__)
discogs.user_agent = 'mediacore-py/0.1 +https://github.com/jererc/mediacore-py'


class Discogs(object):

    def _get_object(self, artist, album=None):
        params = {'artist': artist}
        if album:
            query = '%s %s' % (artist, album)
            params['type'] = 'master'
            params['album'] = album
            re_name = Title(album).get_search_re()
        else:
            query = artist
            params['type'] = 'artist'
            re_name = Title(artist).get_search_re()

        try:
            for res in discogs.Search(query, **params).results():
                name = res.title if params['type'] == 'master' else res.name
                if re_name.search(clean(name)):
                    return res
        except (discogs.PaginationError, discogs.HTTPError):
            pass
        return None

    def _get_album_info(sef, release):
        res = RE_DATE_ALBUM.search(release.data['released'])
        return {
            'name': clean(release.title, 1),
            'genre': [clean(g, 1) for g in release.data['styles']],
            'date': int(res.group(1)) if res else None,
            'url': release.data['uri'],
            'url_thumbnail': release.data.get('thumb'),
            }

    def get_info(self, artist, album=None):
        obj = self._get_object(artist, album)
        if not obj:
            return None
        if album:
            return self._get_album_info(obj.key_release)

        res = {
            'name': clean(obj.name, 1),
            'url': obj.data['uri'],
            'genre': [],
            'albums': [],
            }
        for release in obj.releases:
            if not isinstance(release, discogs.MasterRelease):
                continue
            if obj.name not in [a.name for a in release.artists]:
                continue
            info = self._get_album_info(release.key_release)
            res['albums'].append(info)
            res['genre'] = list(set(res['genre'] + info['genre']))

        return res

    def get_similar(self, artist, releases_max=10):
        res = []

        artist = self._get_object(artist)
        if artist:
            count = 0
            for release in artist.releases:
                if not isinstance(release, discogs.MasterRelease):
                    continue
                if artist.name not in [a.name for a in release.artists]:
                    continue

                for rel in release.key_release.labels[0].releases:
                    data = {
                        'title': rel['artist'],
                        'url': None,
                        }
                    if data not in res:
                        res.append(data)

                count += 1
                if count >= releases_max:
                    break

        return res
