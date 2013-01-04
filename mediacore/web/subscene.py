import os.path
import re
from urlparse import urljoin, parse_qs
import logging

logging.getLogger('requests').setLevel(logging.ERROR)
import requests

from filetools.title import Title, clean
from filetools.media import files, clean_file, move_file
from filetools.download import unpack_download

from mediacore.web import Base, RealBrowser
from mediacore.utils.utils import mkdtemp


DEFAULT_LANG = 'english'
URL_POST = 'http://subscene.com/subtitle/download'
RE_FILENAME = re.compile(r'filename=(.*);?', re.I)
RE_DATE = re.compile(r'\s\((\d{4})\)\W*$')

logger = logging.getLogger(__name__)


class SubsceneError(Exception): pass


class Subscene(Base):
    URL = 'http://subscene.com'

    def __init__(self):
        super(Subscene, self).__init__()

    def _get_date(self, title):
        res = RE_DATE.findall(title)
        if res:
            return int(res[0])

    def _subtitles_urls(self, re_name, re_sub, re_lang, date=None, url=None):
        if url and not self.browser.open(url):
            return

        for tr in self.browser.cssselect('table tr', []):
            links = tr.cssselect('.a1 a')
            if not links:
                continue
            spans = links[0].cssselect('span')
            if len(spans) < 2:
                continue
            if not re_lang.search(clean(spans[0].text)):
                continue
            title = clean(spans[1].text)
            if re_sub and not re_sub.search(title):
                continue
            url_ = urljoin(self.url, links[0].get('href'))
            yield {
                'filename': title,
                'url': url_,
                }

        uls = self.browser.cssselect('.box ul')
        if uls:
            for li in uls[-1]:
                links = li.cssselect('.title a')
                if not links:
                    continue
                for link in links:
                    title = link.text
                    if not re_name.search(title):
                        continue
                    date_ = self._get_date(title)
                    if date and date_ and abs(date - date_) > 1:
                        continue
                    url = urljoin(self.url, link.get('href'))
                    for res in self._subtitles_urls(re_name,
                            re_sub, re_lang, date, url):
                        yield res

    def results(self, name, season=None, episode=None, date=None,
            lang=DEFAULT_LANG):
        if not self.browser.submit_form(self.url, fields={'q': name}):
            return

        if season and episode:
            re_name = Title(name).get_search_re(mode='__all__')
            re_sub = re.compile(r'[^1-9]%s\D*%s\D' % (season, str(episode).zfill(2)))
        else:
            re_name = Title(name).get_search_re()
            re_sub = None

        re_lang = re.compile(r'\b%s\b' % lang, re.I)
        for res in self._subtitles_urls(re_name, re_sub, re_lang, date):
            yield res

    def _get_subscene_id(self, url):
        browser = RealBrowser()
        if browser.open(url):
            links = browser.find_elements_by_css_selector('#downloadButton')
            if links:
                url = links[0].get_attribute('href')
                if url:
                    return parse_qs(url).values()[0]

    def _download(self, url, dst):
        mac = self._get_subscene_id(url)
        if not mac:
            return
        data = {'mac': mac}
        response = requests.post(URL_POST, data=data)
        res = RE_FILENAME.findall(response.headers.get('content-disposition', ''))
        if not res:
            return
        filename = res[0]

        if response.status_code == requests.codes.ok:
            file = os.path.join(dst, filename)
            with open(file, 'wb') as fd:
                fd.write(response.content)
            return file

    def download(self, url, dst, temp_dir):
        files_dst = []
        with mkdtemp(temp_dir) as temp_dst:
            file = self._download(url, temp_dst)
            if not file:
                return
            dir = unpack_download(file)
            for file_ in files(dir, types='subtitles'):
                file_dst = move_file(clean_file(file_.file), dst)
                if file_dst:
                    files_dst.append(file_dst)

        if not files_dst:
            logger.error('failed to get subtitles from %s' % url)
        return files_dst
