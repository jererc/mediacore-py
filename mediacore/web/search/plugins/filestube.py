import re
from datetime import datetime
from urlparse import urlparse
from urllib import urlencode
import requests
import logging

from lxml import html, etree

from filetools.title import clean, get_size

from mediacore.web import Browser, throttle
from mediacore.web.search import Result, SearchError


PRIORITY = 1
API_URL = 'http://api.filestube.com'
SORT_DEF = {
    'date': 'dd',
    'popularity': 'pd',
    }

logger = logging.getLogger(__name__)


class FilestubeError(Exception): pass


class Filestube(object):

    def __init__(self, api_key):
        self.api_key = api_key
        super(Filestube, self).__init__()

    def _send(self, query, page, sort):
        info = {
            'key': self.api_key,
            'phrase': query,
            'sort': sort,
            'page': page,
            }
        url = '%s?%s' % (API_URL, urlencode(info))
        try:
            response = requests.get(url)
        except Exception, e:
            raise SearchError('failed to get %s: %s' % (url, str(e)))
        if response.status_code != requests.codes.ok:
            raise SearchError('failed to get %s: %s' % (url, response.status_code))
        return response.content

    @throttle(300)
    def results(self, query, sort='date', pages_max=1, **kwargs):
        sort = SORT_DEF[sort]
        for page in range(1, pages_max + 1):
            data = self._send(query, page, sort)
            tree = etree.fromstring(data)
            try:
                results = int(tree.xpath('hasResults')[0].text)
            except (ValueError, IndexError):
                raise SearchError('failed to get results count from "%s"' % data)
            if not results:
                return
            hits = int(tree.xpath('results/hitsForThisPage')[0].text)
            if not hits:
                return
            for res in tree.xpath('results/hits'):
                url = res.xpath('link')[0].text
                if not url:
                    logger.error('failed to get url from %s', data)
                    continue
                size = res.xpath('size')[0].text
                if not size:
                    logger.error('failed to get size from %s', data)
                    continue
                date = res.xpath('added')[0].text
                if not date:
                    logger.error('failed to get date from %s', data)
                    continue

                result = Result()
                result.auto = False
                result.type = 'filestube'
                result.title = clean(res.xpath('name')[0].text)
                result.url = url
                result.size = get_size(size)
                result.date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
                if not result.validate(**kwargs):
                    continue
                yield result


def _get_download_url(url):
    browser = Browser()
    netloc_parts = urlparse(url).netloc.split('.')

    if 'mediafire' in netloc_parts:
        browser.open(url)
        if browser.cssselect('#form_captcha'):
            raise FilestubeError('failed to get url from %s: captcha' % url)
        tags = browser.cssselect('.error_msg_title')
        if tags:
            raise FilestubeError('failed to get download url from %s: %s' % (url, tags[0].text))

        tags = browser.cssselect('.download_link')
        if tags:
            data_ = html.tostring(tags[0])
            res = re.compile(r'"(http://.*?)"').findall(data_)
            if res:
                return res[0]

    raise FilestubeError('failed to get download url from %s' % url)

def get_download_urls(url):
    if not isinstance(url, (list, tuple)):
        url = [url]
    return [_get_download_url(u) for u in url]
