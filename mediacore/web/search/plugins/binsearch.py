import re
from urlparse import urljoin
import logging

from lxml import html

logging.getLogger('requests').setLevel(logging.ERROR)
import requests

from filetools.title import clean, get_size

from mediacore.web import Base, Browser
from mediacore.web.search import Result, SearchError


PRIORITY = 0
RE_ADVANCED_SEARCH = re.compile(r'\badvanced search\b', re.I)
RE_COLLECTION = re.compile(r'\bcollection\b', re.I)
RE_PASSWORD = re.compile(r'\brequires\s+password\b', re.I)
RE_TITLE = re.compile(r'"([^"]+)"', re.I)
RE_SIZE = re.compile(r'\bsize\s*:\s*([^,]+)\s*,', re.I)
RE_PARTS = re.compile(r'\bparts\s+available\s*:\s*(\d+)\s*/\s*(\d+)', re.I)
RE_FILENAME = re.compile(r'filename="(.*)";?', re.I)

logger = logging.getLogger(__name__)


class BinsearchError(Exception): pass


class Binsearch(Base):
    URL = 'http://www.binsearch.info'

    def results(self, query, sort='date', pages_max=1, **kwargs):
        if not self.url:
            raise SearchError('no data')

        # links = list(self.browser.links(text_regex=RE_ADVANCED_SEARCH))
        # if not links:
        #     raise SearchError('failed to find advanced search link')
        # url = links[0].absolute_url
        url = None

        for i in range(pages_max):
            if i == 0:
                if not self.browser.submit_form(url, fields={'q': query}):
                    raise SearchError('no data')
            else:
                tables = self.browser.cssselect('table')
                if not tables:
                    continue
                links = tables[-1].cssselect('a')
                if not links:
                    break
                next_text = self.get_link_text(html.tostring(links[-1]))
                if next_text != '&gt;':
                    break
                url = urljoin(self.url, links[-1].get('href'))
                if not self.browser.open(url):
                    raise SearchError('no data')

            for tr in self.browser.cssselect('table#r2 tr', []):
                if tr.cssselect('th'):
                    continue

                log = html.tostring(tr, pretty_print=True)[:1000]

                result = Result()
                result.type = 'binsearch'

                titles = tr.cssselect('span.s')
                if not titles:
                    continue
                title = titles[0].text
                res = RE_TITLE.findall(title)
                if res:
                    title = res[0]
                result.title = clean(title)

                refs = tr.cssselect('input[type="checkbox"]')
                if not refs:
                    logger.error('failed to get references list from %s' % log)
                    continue
                ref = refs[0].get('name')
                if not ref:
                    logger.error('failed to get reference from %s' % log)
                    continue
                result.ref = ref

                info = tr.cssselect('span.d')
                if not info:
                    continue
                links = info[0].cssselect('a')
                if not links or not RE_COLLECTION.search(links[0].text):
                    continue
                result.url = urljoin(self.url, links[0].get('href'))

                info = clean(html.tostring(info[0]))
                if RE_PASSWORD.search(info):
                    continue

                res = RE_SIZE.search(info)
                if not res:
                    continue
                result.size = get_size(res.group(1))

                res = RE_PARTS.search(info)
                if not res or res.group(1) != res.group(2):
                    continue

                if not result.validate(**kwargs):
                    continue
                yield result


def _get_collection(url):
    browser = Browser()
    browser.open(url)

    res = []
    for tr in browser.cssselect('table#r2 tr', []):
        if tr.cssselect('th'):
            continue

        refs = tr.cssselect('input[type="checkbox"]')
        if not refs:
            continue
        ref = refs[0].get('name')
        if not ref:
            logger.error('failed to get reference from %s' % html.tostring(refs[0], pretty_print=True))
            continue
        res.append(ref)

    return res

def get_nzb(url):
    collection = _get_collection(url)
    if not collection:
        raise BinsearchError('failed to get collection from %s' % url)
    data = {'action': 'nzb'}
    for ref in collection:
        data[ref] = 'on'
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    response = requests.post(url, headers=headers, data=data)
    if response.status_code != requests.codes.ok:
        raise BinsearchError('failed to process request to %s' % url)
    res = RE_FILENAME.findall(response.headers.get('content-disposition', ''))
    if not res:
        raise BinsearchError('failed to get filename from response headers %s' % response.headers)
    return response.content
