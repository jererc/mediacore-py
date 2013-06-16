import re
from urlparse import urlparse, urljoin
import logging

from lxml import html

from filetools.title import clean, get_size

from mediacore.web import Base, Browser
from mediacore.web.search import Result, SearchError


PRIORITY = 1
RE_ADVANCED_SEARCH = re.compile(r'\badvanced search\b', re.I)
SORT_DEF = {
    'date': ['dd'],
    'popularity': ['pd'],
    }

logger = logging.getLogger(__name__)


class FilestubeError(Exception): pass


class Filestube(Base):
    URL = 'http://www.filestube.com/'

    def _get_download_info(self, url):
        browser = Browser()
        browser.open(url)
        tags = browser.cssselect('#copy_paste_links')
        if not tags or not tags[0].text:
            return
        urls = tags[0].text.splitlines()

        size = 0
        for tag in browser.cssselect('#js_files_list tr .tright', []):
            size += get_size(tag.text) or 0
        return {'urls': urls, 'size': size}

    def results(self, query, sort='date', pages_max=1, **kwargs):
        if not self.url:
            raise SearchError('no data')

        links = list(self.browser.links(text_regex=RE_ADVANCED_SEARCH))
        if not links:
            raise SearchError('failed to find advanced search link')
        url = links[0].absolute_url

        for i in range(pages_max):
            if i == 0:
                if not self.browser.submit_form(url,
                        fields={'allwords': query, 'sort': SORT_DEF[sort]}):
                    raise SearchError('no data')
            else:
                links = self.browser.cssselect('div#pager a')
                if not links or not self.check_next_link(links[-1]):
                    break
                url = urljoin(self.url, links[-1].get('href'))
                if not self.browser.open(url):
                    raise SearchError('no data')

            divs = self.browser.cssselect('div#newresult')
            if divs is None:
                raise SearchError('no data')

            for div in divs:
                links = div.cssselect('a')
                if not links:
                    continue

                url = urljoin(self.url, links[0].get('href'))
                info = self._get_download_info(url)
                if info:
                    result = Result()
                    result.auto = False
                    result.type = 'filestube'
                    result.title = clean(self.get_link_text(html.tostring(links[0])))
                    result.url = info['urls']
                    result.size = info['size']
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

    res = []
    for url_ in url:
        res.append(_get_download_url(url_))
    return res
