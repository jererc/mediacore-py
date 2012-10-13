import re
from urlparse import urlparse, urljoin
import logging

from lxml import html

from mediacore.web import Base
from mediacore.web.search import Result, SearchError
from mediacore.util.title import clean, get_size


PRIORITY = 2
RE_ADVANCED_SEARCH = re.compile(r'\badvanced search\b', re.I)
SUPPORTED_SITES = ['mediafire']
SORT_DEF = {
    'date': ['dd'],
    'popularity': ['pd'],
    }

logger = logging.getLogger(__name__)


class Filestube(Base):
    URL = 'http://www.filestube.com/'

    def _get_site(self, url):
        netloc_parts = urlparse(url).netloc.lower().split('.')
        for site in SUPPORTED_SITES:
            if site in netloc_parts:
                return site

    def _get_download_info(self, url):
        data = self.browser.get_unicode_data(url=url)
        if not data:
            return

        tree = html.fromstring(data)
        tags = tree.cssselect('#copy_paste_links')
        if not tags:
            return
        urls = tags[0].text.splitlines()
        if not self._get_site(urls[0]):
            return

        size = 0
        for tag in tree.cssselect('#js_files_list tr .tright'):
            size_ = get_size(tag.text)
            if size_:
                size += size_
        if not size:
            logger.error('failed to get size from %s' % url)
            return

        return {
            'urls': urls,
            'size': size,
            }

    def results(self, query, sort='date', pages_max=1, **kwargs):
        self.browser.clear_history()

        links = list(self.browser.links(text_regex=RE_ADVANCED_SEARCH))
        if not links:
            raise SearchError('failed to find advanced search link')
        url = links[0].absolute_url

        tree = None
        for i in range(pages_max):
            if tree is None:
                res = self.submit_form(url,
                        fields={'allwords': query, 'sort': SORT_DEF[sort]})
                data = self.browser.get_unicode_data(response=res)
            else:
                links = tree.cssselect('div#pager a')
                if not links or not self.check_next_link(links[-1]):
                    return
                url = urljoin(self.url, links[-1].get('href'))
                data = self.browser.get_unicode_data(url=url)

            if not data:
                raise SearchError('no data')

            tree = html.fromstring(data)
            for div in tree.cssselect('div#newresult'):
                links = div.cssselect('a')
                if not links:
                    continue

                url = urljoin(self.url, links[0].get('href'))
                info = self._get_download_info(url)
                if info:
                    result = Result()
                    result.title = clean(self.get_link_text(html.tostring(links[0])))
                    result.url = info['urls']
                    result.type = 'filestube'
                    result.size = info['size']
                    if not result.validate(**kwargs):
                        continue
                    yield result

    def _get_download_url(self, url):
        netloc_parts = urlparse(url).netloc.split('.')
        if 'mediafire' in netloc_parts:
            data = self.browser.get_unicode_data(url=url)
            if not data:
                return

            tree = html.fromstring(data)
            if tree.cssselect('#form_captcha'):
                logger.error('failed to get url from %s: captcha' % url)
                return

            tags = tree.cssselect('.download_link')
            if tags:
                data_ = html.tostring(tags[0])
                res = re.compile(r'"(http://.*?)"').findall(data_)
                if res:
                    return res[0]
            logger.error('failed to get url from %s' % url)

    def get_download_urls(self, urls):
        res = []
        for url in urls:
            url_ = self._get_download_url(url)
            if not url_:
                return
            res.append(url_)
        return res
