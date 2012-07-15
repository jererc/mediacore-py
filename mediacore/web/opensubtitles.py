import re
from urlparse import urljoin
import logging

from lxml import html

from mediacore.web import Base
from mediacore.util.title import Title, clean
from mediacore.util.media import is_html


DEFAULT_LANG = 'eng'
RE_URL_FILE = re.compile(r'/file/[^/]+$', re.I)
RE_FILE = re.compile(r'\[IMG\](.*)\s+\(.*?\)$', re.I)
RE_MAXIMUM_DOWNLOAD = re.compile(r'\bmaximum\s+download\s+count\b', re.I)
RE_ERROR = re.compile(r'\bcritical\s+error\b', re.I)
RE_NO_RESULT = re.compile(r'<b>No\s+results</b>\s+found', re.I)
RE_DATE = re.compile(r'\s\((\d{4})\)\W*$')


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
        res = self.submit_form(self.url, name='loginform', fields={
                'user': username,
                'password': password,
                })
        if not res:
            logger.error('failed to login')
        elif 'loginform' in [f.name for f in self.browser.forms()]:
            logger.error('failed to login as %s', username)
        else:
            return True

    def _get_subtitles(self, url):
        info = []

        if self.browser.open(url):
            for link in self.browser.links(url_regex=RE_URL_FILE):
                res = RE_FILE.search(link.text.decode('utf-8', 'replace'))
                if res:
                    info.append({
                        'filename': res.group(1),
                        'url': link.absolute_url,
                        })

        if not info:
            if not RE_NO_RESULT.search(self.browser.response().get_data()):
                logger.error('failed to find subtitles files at %s', url)

        return info

    def _get_date(self, title):
        res = RE_DATE.search(title)
        if res:
            return int(res.group(1))

    def _subtitles_urls(self, re_name, date=None, url=None):
        if not url:
            url = self.browser.geturl()
            res = self.browser.response()
        else:
            res = self.browser.open(url)

        data = res.get_data() if res else None
        if not data:
            raise OpensubtitlesError('no data')

        tree = html.fromstring(data)
        trs = tree.cssselect('#search_results tr[id]')
        if not trs:
            if not tree.cssselect('#search_results'):    # skip tvshow whole season page
                yield self.browser.geturl()
        else:
            for tr in trs:
                links = tr.cssselect('a')
                if links:
                    title = clean(links[0].text)
                    if not re_name.search(title):
                        continue
                    date_ = self._get_date(title)
                    if date and date_ and abs(date - date_) > 1:
                        continue

                    url = urljoin(self.url, links[0].get('href'))
                    for res in self._subtitles_urls(re_name=re_name, date=date, url=url):
                        yield res

    def results(self, name, season=None, episode=None, date=None, lang=DEFAULT_LANG):
        fields = {
            'MovieName': name,
            'SubLanguageID': [lang],
            }
        if season:
            fields['Season'] = str(season)
        if episode:
            fields['Episode'] = str(episode)
        if not self.submit_form(name='searchform', fields=fields):
            return

        if season and episode:
            re_name = Title(name).get_search_re(mode='__all__')
            re_sub = re.compile(r'[^1-9]%s\D*%s\D' % (season, episode), re.I)
        else:
            re_name = Title(name).get_search_re()
            re_sub = None

        for res in self._subtitles_urls(re_name, date=date):
            for result in self._get_subtitles(res):
                if re_sub and not re_sub.search(result['filename']):
                    continue
                yield result

    def save(self, url, dst):
        '''Save the file to the destination and check the content.
        '''
        if not self.logged:
            logger.error('failed to download %s: login required', url)
            return

        res = self.browser.open(url)
        if res:
            data = res.get_data()
            if not data or is_html(data):
                if RE_MAXIMUM_DOWNLOAD.search(data):
                    raise DownloadQuotaReached('failed to download %s: maximum download quota reached' % url)
                elif RE_ERROR.search(data):
                    raise OpensubtitlesError('failed to download %s: opensubtitles error' % url)
                logger.error('downloaded invalid subtitles from %s: %s[...])', url, repr(data[:100]))
                return

            with open(dst, 'wb') as fd:
                fd.write(data)
            return True
