import logging

import gdata.youtube.service

from mediacore.util.title import Title, clean


logger = logging.getLogger(__name__)


class Youtube(object):

    def __init__(self, ssl=True):
        self.yt_service = gdata.youtube.service.YouTubeService()
        self.yt_service.ssl = ssl

    def results(self, query):
        # Convert non unicode characters
        query = clean(query)

        yt_query = gdata.youtube.service.YouTubeVideoQuery()
        yt_query.vq = query
        yt_query.orderby = 'relevance'
        yt_query.racy = 'include'
        feed = self.yt_service.YouTubeQuery(yt_query)
        for entry in feed.entry:
            res = {}
            res['title'] = entry.media.title.text
            res['duration'] = entry.media.duration.seconds
            res['urls_thumbnails'] = [thumbnail.url for thumbnail in entry.media.thumbnail]
            res['url_watch'] = entry.media.player.url
            # res['url_flash'] = entry.GetSwfUrl()
            # res['published'] = entry.published.text
            # res['description'] = entry.media.description.text
            # res['category'] = entry.media.category[0].text
            # res['tags'] = entry.media.keywords.text
            yield res

    def get_trailer(self, title, date=None):
        # Convert non unicode characters
        title = clean(title)

        re_title = Title(title).get_search_re('word3')
        query = '%s%s trailer' % (title, date or '')
        for result in self.results(query):
            if re_title.search(result['title']) and result['url_watch'] and result['urls_thumbnails']:
                return result

    def get_track(self, artist, album):
        # Convert non unicode characters
        artist = clean(artist)
        album = clean(album)

        re_title = Title(artist).get_search_re('word3')
        for result in self.results('%s %s' % (artist, album)):
            if re_title.search(result['title']) and result['url_watch'] and result['urls_thumbnails']:
                return result
