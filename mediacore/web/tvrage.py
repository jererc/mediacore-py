import re
from urlparse import urljoin
import logging

from lxml import html

from mediacore.web import Base, WEB_EXCEPTIONS
from mediacore.util.title import Title, clean, is_url


URL_SCHEDULE = 'http://www.tvrage.com/schedule.php'
RE_URL_MAIN = re.compile(r'/[^\.]+$', re.I)
RE_EPISODE = re.compile(r'\((\d+)x(\d+)\)', re.I)
RE_EPISODE_INFO = re.compile(r'\b(\d+x\d+)\b.*\((.*?/\d+/\d+)\)', re.I)
RE_COUNTRY = re.compile(r'>\s*(.*?)\s*\)')
RE_YEAR = re.compile(r'\b(\d{4})\b')
RE_SPECIAL = re.compile(r'\(.*?special.*?\)', re.I)


logger = logging.getLogger(__name__)


class Tvrage(Base):
    URL = 'http://www.tvrage.com'

    def _get_data(self, query):
        try:
            self.browser.clear_history()
            if is_url(query):
                return self.browser.open(query).get_data()
            else:
                res = self.submit_form(self.URL, fields={'search': query})
                if not res:
                    return

                re_q = Title(query).get_search_re()
                for link in self.browser.links(url_regex=RE_URL_MAIN):
                    if re_q.search(clean(link.text)):
                        res = self.browser.open(link.absolute_url)
                        return res.get_data()

        except WEB_EXCEPTIONS:
            pass
        except Exception:
            logger.exception('exception')

    def get_info(self, query):
        data = self._get_data(query)
        if not data:
            return

        info = {'url': self.browser.geturl()}

        tree = html.fromstring(data)

        # Episode info
        for h2 in tree.cssselect('div.grid_7_5 h2'):
            title = h2.text.lower().split(':')[0]
            if title in ('next', 'prev'):
                res = RE_EPISODE_INFO.search(html.tostring(h2))
                if res:
                    key = 'next_episode' if title == 'next' else 'latest_episode'
                    info[key] = clean('%s (%s)' % res.groups()).lower()

        for div in tree.cssselect('div.grid_4'):
            if not div.cssselect('.content_title a'):
                continue

            links = div.cssselect('a')
            try:
                info['network'] = clean(links[1].text, 1)
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

            info['style'] = clean(info_.get('classification', '').lower())
            info['genre'] = [clean(g, 1) for g in re.split(r'\s*\|\s*', info_.get('genre', ''))]
            res = RE_YEAR.search(info_.get('premiere', ''))
            if res:
                info['date'] = int(res.group(1))

        return info

    def scheduled_shows(self):
        data = self._get_data(URL_SCHEDULE)
        if not data:
            return

        tree = html.fromstring(data)
        for tr in tree.cssselect('table tr[id="brow"]'):
            log = html.tostring(tr, pretty_print=True)
            info = {}

            try:
                info['network'] = clean(tr[0].cssselect('a')[0].text, 1)
            except IndexError:
                info['network'] = clean(tr[0][0][0].text, 1)
            except Exception:
                logger.error('failed to get network from %s', log)

            try:
                link = tr[1].cssselect('a')[0]
                info['name'] = clean(link.text, 1)
                info['url'] = urljoin(self.URL, link.get('href'))
            except IndexError:
                info['name'] = clean(tr[1][0][0].text, 1)
            except Exception:
                logger.error('failed to get name from %s', log)
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
