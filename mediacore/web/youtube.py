import logging

import gdata.youtube.service

from filetools.title import Title, clean

from systools.system import timeout


logger = logging.getLogger(__name__)


class Youtube(object):

    def __init__(self, ssl=True):
        self.yt_service = gdata.youtube.service.YouTubeService()
        self.yt_service.ssl = ssl

    def results(self, query):
        yt_query = gdata.youtube.service.YouTubeVideoQuery()
        yt_query.vq = clean(query)
        yt_query.orderby = 'relevance'
        yt_query.racy = 'include'
        try:
            feed = self.yt_service.YouTubeQuery(yt_query)
        except Exception, e:
            logger.error('failed to process query "%s": %s' % (query, str(e)))
            return

        for entry in feed.entry:
            res = {}
            res['title'] = entry.media.title.text
            res['duration'] = entry.media.duration.seconds
            res['urls_thumbnails'] = [thumbnail.url for thumbnail in entry.media.thumbnail]
            res['url_watch'] = entry.media.player.url
            # res['description'] = entry.media.description.text
            # res['url_flash'] = entry.GetSwfUrl()
            # res['published'] = entry.published.text
            # res['category'] = entry.media.category[0].text
            # res['tags'] = entry.media.keywords.text
            yield res

    @timeout(120)
    def get_trailer(self, title, date=None):
        title = clean(title)
        re_title = Title(title).get_search_re(mode='__all__')

        queries = ['%s trailer' % title, title]
        if date:
            queries.insert(0, '%s %s trailer' % (title, date))

        for query in queries:
            for result in self.results(query):
                if not re_title.search(clean(result['title'])):
                    continue
                if result['url_watch'] and result['urls_thumbnails']:
                    return result

    @timeout(120)
    def get_track(self, artist, album):
        artist = clean(artist)
        album = clean(album)

        re_title = Title(artist).get_search_re(mode='__all__')
        for result in self.results('%s %s' % (artist, album)):
            if not result['title'] or not result['url_watch'] or not result['urls_thumbnails']:
                continue
            if re_title.search(result['title']):
                return result
