import re
from urlparse import urljoin
from urllib2 import urlopen, URLError
import logging

from transfer.http import download as download_file

from filetools.title import Title, clean
from filetools.media import is_html, remove_file

from mediacore.web import Base


DEFAULT_LANG = 'eng'
RE_URL_FILE = re.compile(r'/file/[^/]+$', re.I)
RE_FILE = re.compile(r'\[IMG\](.*)\s+\(.*?\)$', re.I)
RE_MAXIMUM_DOWNLOAD = re.compile(r'\bmaximum\s+download\s+count\b', re.I)
RE_ERROR = re.compile(r'\bcritical\s+error\b', re.I)
RE_NO_RESULT = re.compile(r'<b>No\s+results</b>\s+found', re.I)
RE_DATE = re.compile(r'\s\((\d{4})\)\W*$')
RE_BAD_CONTENT_TYPE = re.compile(r'\btext/html\b', re.I)

logger = logging.getLogger(__name__)


class OpensubtitlesError(Exception): pass
class DownloadQuotaReached(OpensubtitlesError): pass


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
        info = []
        if self.browser.open(url):
            for link in self.browser.links(url_regex=RE_URL_FILE):
                res = RE_FILE.findall(clean(link.text))
                if res:
                    info.append({
                        'filename': res[0],
                        'url': link.absolute_url,
                        })

        if not info:
            if self.browser.tree \
                    and not RE_NO_RESULT.search(self.browser.tree.text_content()):
                logger.error('failed to find subtitles files at %s' % url)

        return info

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
            re_sub = re.compile(r'[^1-9]%s\D*%s\D' % (season, str(episode).zfill(2)))
        else:
            re_name = Title(name).get_search_re()
            re_sub = None

        for res in self._subtitles_urls(re_name, date=date):
            for result in self._get_subtitles(res):
                if re_sub and not re_sub.search(result['filename']):
                    continue
                yield result

    def _check_url(self, url):
        try:
            remote = urlopen(url)
        except URLError, e:
            logger.error('failed to open url %s: %s' % (url, str(e)))
            return
        if not remote:
            logger.error('failed to get headers for url %s' % url)
            return
        content_type = remote.info().get('content-type')
        if content_type and not RE_BAD_CONTENT_TYPE.search(content_type):
            return True

    def _check_file(self, file):
        with open(file) as fd:
            data = fd.read()

        if not data or is_html(data):
            remove_file(file)
            if RE_MAXIMUM_DOWNLOAD.search(data):
                raise DownloadQuotaReached('maximum download quota reached')
            return
        return True

    def download(self, url, dst, temp_dir):
        if not self._check_url(url):
            return
        res = download_file(url, dst, temp_dir)
        if not res:
            return
        if not self._check_file(res[0]):
            logger.error('invalid subtitles at %s' % url)
            return
        return res
