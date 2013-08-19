import re
from urlparse import urljoin
import logging

from transfer.http import download as download_file

from filetools.title import Title, clean
from filetools.media import (is_html, files, clean_file, move_file,
        remove_file, mkdtemp)
from filetools.download import unpack_download

from mediacore.web import Base, throttle, update_rate, RateLimitReached


DEFAULT_LANG = 'eng'
RE_MAXIMUM_DOWNLOAD = re.compile(r'\bmaximum\s+download\s+count\b', re.I)
RE_NO_RESULT = re.compile(r'\bno\s+results\s+found\b', re.I)
RE_DATE = re.compile(r'\s\((\d{4})\)\W*$')

logger = logging.getLogger(__name__)


class Opensubtitles(Base):
    URL = 'http://www.opensubtitles.org'

    def __init__(self, username, password):
        super(Opensubtitles, self).__init__()
        if self.url:
            self.logged = self._login(username, password)
        else:
            self.logged = False

    def _login(self, username, password):
        fields = {'user': username, 'password': password}
        if not self.browser.submit_form(self.url,
                name='loginform', fields=fields):
            return False
        if 'loginform' in [f.name for f in self.browser.forms()]:
            logger.error('failed to login as %s' % username)
            return False
        return True

    def _get_subtitles(self, url):
        urls = []
        if self.browser.open(url):
            urls = []
            for link in self.browser.cssselect('a[title="Download"]', []):
                url_ = urljoin(self.url, link.get('href'))
                if url_ not in urls:
                    urls.append(url_)

        if not urls and self.browser.tree is not None \
                and not RE_NO_RESULT.search(self.browser.tree.text_content()):
            logger.error('failed to find subtitles files at %s' % url)

        return urls

    def _get_date(self, title):
        res = RE_DATE.findall(title)
        if res:
            return int(res[0])

    def _subtitles_urls(self, re_name, date=None, url=None):
        if url and not self.browser.open(url):
            return

        trs = self.browser.cssselect('#search_results tr[id]')
        if not trs:
            if not self.browser.cssselect('#search_results'):    # skip tvshow whole season page
                yield self.browser.geturl()
            return

        for tr in trs:
            links = tr.cssselect('a')
            if not links:
                continue
            title = clean(links[0].text)
            if not re_name.search(title):
                continue
            date_ = self._get_date(title)
            if date and date_ and abs(date - date_) > 1:
                continue

            url = urljoin(self.url, links[0].get('href'))
            for res in self._subtitles_urls(re_name=re_name,
                    date=date, url=url):
                yield res

    def results(self, name, season=None, episode=None, date=None,
            lang=DEFAULT_LANG):
        if not self.logged:
            return

        fields = {
            'MovieName': name,
            'SubLanguageID': [lang],
            }
        if season:
            fields['Season'] = str(season)
        if episode:
            fields['Episode'] = str(episode)
        if not self.browser.submit_form(self.url,
                name='searchform', fields=fields):
            return

        if season and episode:
            re_name = Title(name).get_search_re(mode='__all__')
        else:
            re_name = Title(name).get_search_re()

        for res in self._subtitles_urls(re_name, date=date):
            for result in self._get_subtitles(res):
                yield result

    def _check_file(self, file):
        with open(file) as fd:
            data = fd.read()

        if not data or is_html(data):
            remove_file(file)
            if RE_MAXIMUM_DOWNLOAD.search(data):
                update_rate(self.__module__.rsplit('.', 1)[-1], count=9999)
                logger.error('download limit reached')
                raise RateLimitReached('opensubtitles download limit reached')
            return
        return True

    @throttle(15, 120)
    def download(self, url, dst, temp_dir):
        files_dst = []
        with mkdtemp(temp_dir) as temp_dst:
            res = download_file(url, temp_dst, temp_dst)
            if not res:
                return
            if not self._check_file(res[0]):
                return
            dir = unpack_download(res[0])
            for file_ in files(dir, types='subtitles'):
                file_dst = move_file(clean_file(file_.file), dst)
                if file_dst:
                    files_dst.append(file_dst)

        return files_dst
