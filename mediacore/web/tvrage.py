import re
from urlparse import urljoin
from datetime import datetime
import logging

from lxml import html

from filetools.title import Title, clean, is_url

from systools.system import timeout

from mediacore.web import Base


URL_SCHEDULE = 'http://www.tvrage.com/schedule.php'
RE_EPISODE = re.compile(r'\((\d+)x(\d+)\)', re.I)
RE_EPISODE_INFO = re.compile(r'\b(\d+x\d+)\b.*\((.*?/\d+/\d+)\)', re.I)
RE_COUNTRY = re.compile(r'>\s*(.*?)\s*\)')
RE_YEAR = re.compile(r'\b(\d{4})\b')
RE_SPECIAL = re.compile(r'\(.*?special.*?\)', re.I)
RE_CURRENT_SHOWS = re.compile(r'current shows', re.I)

logger = logging.getLogger(__name__)


def get_year(val):
    res = RE_YEAR.search(val)
    if res:
        return int(res.group(1))


class Tvrage(Base):
    URL = 'http://www.tvrage.com'

    def _process(self, query):
        if is_url(query):
            return self.browser.open(query)

        if self.browser.submit_form(self.url, index=0, fields={'search': query}):
            re_q = Title(query).get_search_re()
            for res in self.browser.cssselect('#show_search a', []):
                url = res.get('href')
                if not url or not res.text:
                    continue
                if not re_q.search(clean(res.text)):
                    continue
                return self.browser.open(urljoin(self.url, url))

    @timeout(120)
    def get_info(self, query):
        if not self._process(query):
            return

        info = {'url': self.browser.geturl()}

        titles = self.browser.cssselect('.content_title a')
        if not titles:
            logger.error('failed to get title from %s', info['url'])
            return
        info['title'] = clean(titles[0].text, 1)

        # Episode info
        for h2 in self.browser.cssselect('div.grid_7_5 h2', []):
            title = h2.text.lower().split(':')[0]
            if title in ('next', 'prev'):
                res = RE_EPISODE_INFO.search(html.tostring(h2))
                if res:
                    key = 'next_episode' if title == 'next' else 'latest_episode'
                    info[key] = clean('%s (%s)' % res.groups()).lower()

        for div in self.browser.cssselect('div.grid_4', []):
            if not div.cssselect('.content_title a'):
                continue

            links = div.cssselect('a')
            try:
                info['network'] = clean(links[1].text, 1)
                info['url_network'] = urljoin(self.url, links[1].get('href'))
            except Exception:
                info['network'] = None

            info_ = {}
            for tag in div:
                if tag.cssselect('img'):
                    res = RE_COUNTRY.search(html.tostring(tag))
                    if res:
                        info['country'] = clean(res.group(1), 1)
                else:
                    res = re.compile(r'>(.*?)<.*?:\s*(.*)$', re.I).search(html.tostring(tag))
                    if res:
                        key, val = res.groups()
                        info_[key.lower()] = val

            for key in ('status', 'runtime', 'airs'):
                info[key] = clean(info_.get(key)).lower()

            info['classification'] = clean(info_.get('classification', '').lower())
            info['genre'] = [clean(g, 1) for g in re.split(r'\s*\|\s*', info_.get('genre', ''))]
            year = get_year(info_.get('premiere', ''))
            if year:
                info['date'] = year

        return info

    def _get_current_shows_url(self, url):
        self._process(url)
        for link in self.browser.links(text_regex=RE_CURRENT_SHOWS):
            return link.absolute_url

    @timeout(120)
    def get_similar(self, query, years_delta=None):
        info = self.get_info(query)
        if not info:
            return
        url = info.get('url_network')
        if not url:
            return
        url = self._get_current_shows_url(url)
        if not url:
            return
        self._process(url)
        res = []
        for tr in self.browser.cssselect('table.b tr#brow', []):
            log = html.tostring(tr, pretty_print=True)[:1000]

            try:
                classification = clean(tr[2].cssselect('td')[0].text).lower()
            except Exception:
                logger.error('failed to get classification from %s', log)
                continue
            if classification != info.get('classification'):
                continue

            info_ = {}
            try:
                link = tr[0].cssselect('a')[0]
                info_['title'] = clean(link.text, 1)
                info_['url'] = urljoin(self.url, link.get('href'))
            except Exception:
                logger.error('failed to get title from %s', log)
            if info_['title'] == clean(query, 1):
                continue

            try:
                info_['date'] = get_year(tr[1].cssselect('td')[0].text)
            except Exception:
                logger.error('failed to get date from %s', log)
            if years_delta is not None and abs(datetime.now().year - info_['date']) > years_delta:
                continue

            res.append(info_)

        return res

    @timeout(120)
    def scheduled_shows(self):
        self._process(URL_SCHEDULE)
        for tr in self.browser.cssselect('table tr[id="brow"]', []):
            log = html.tostring(tr, pretty_print=True)[:1000]
            info = {}

            try:
                info['network'] = clean(tr[0].cssselect('a')[0].text, 1)
            except IndexError:
                info['network'] = clean(tr[0][0][0].text, 1)
            except Exception:
                logger.error('failed to get network from %s', log)

            try:
                link = tr[1].cssselect('a')[0]
                info['title'] = clean(link.text, 1)
                info['url'] = urljoin(self.url, link.get('href'))
            except IndexError:
                info['title'] = clean(tr[1][0][0].text, 1)
            except Exception:
                logger.error('failed to get title from %s', log)
                continue

            try:
                val = html.tostring(tr[2][0])
                if not RE_SPECIAL.search(val):
                    res = RE_EPISODE.search(val)
                    info['season'] = int(res.group(1))
                    info['episode'] = int(res.group(2))
            except Exception:
                logger.debug('failed to get season and episode from %s', log)

            yield info
