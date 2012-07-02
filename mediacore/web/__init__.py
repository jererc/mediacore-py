import re
import socket
from urlparse import urlparse
from httplib import IncompleteRead, BadStatusLine
from urllib2 import URLError
import logging

import mechanize


USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/536.6 (KHTML, like Gecko) Chrome/20.0.1092.0 Safari/536.6'
TIMEOUT = 300
URL_TIMEOUT = 20
RE_LINK_TITLE = re.compile(r'<a\s*.*?>(.*?)</a>', re.I)


socket.setdefaulttimeout(TIMEOUT)
logger = logging.getLogger(__name__)


class Browser(mechanize.Browser):
    '''Base browser class.
    '''
    def __init__(self, user_agent=USER_AGENT, debug_http=False):
        mechanize.Browser.__init__(self)    # mechanize.Browser is an old style class
        self.addheaders = [('User-Agent', user_agent)]
        self.set_handle_robots(False)
        self.set_handle_refresh(False)
        if debug_http:
            self.set_debug_http(True)

    def _mech_open(self, *args, **kwargs):
        kwargs['timeout'] = URL_TIMEOUT
        try:
            return mechanize.Browser._mech_open(self, *args, **kwargs)
        except (IncompleteRead, BadStatusLine, URLError,
                socket.gaierror, socket.error, mechanize.BrowserStateError), e:
            logger.debug('request failed for %s, %s: %s', args, kwargs, e)
        except Exception:
            logger.exception('exception')

    def follow_link(self, *args, **kwargs):
        try:
            return mechanize.Browser.follow_link(self, *args, **kwargs)
        except mechanize.LinkNotFoundError:
            pass


class Base(object):
    '''Base website class.
    '''
    def __init__(self, debug_http=False):
        self.browser = Browser(debug_http=debug_http)
        self.url = self._get_url()
        if self.url:
            self.accessible = True
        else:
            self.accessible = False
            logger.error('failed to connect to %s', self.URL)

    def _get_url(self):
        if not isinstance(self.URL, (tuple, list)):
            self.URL = [self.URL]

        for url in self.URL:
            if self._is_accessible(url):
                return url

    def _is_accessible(self, url):
        if self.browser.open(url):
            url_ = self.browser.geturl()
            if get_website_name(url_) == get_website_name(url):
                return True
            logger.info('%s is redirected to %s', url, url_)

    def get_link_text(self, val):
        res = RE_LINK_TITLE.search(val)
        if res:
            return res.group(1)
        logger.error('failed to get text from link "%s"', val)

    def submit_form(self, url=None, name=None, index=None, fields=None):
        if url:
            if not self.browser.open(url):
                return
        elif not self.url:
            return

        # for form in self.browser.forms():
        #     print form.attrs

        if name:
            form_info = {'name': name}
        elif index:
            form_info = {'nr': index}
        else:
            form_info = {'nr': 0}

        try:
            self.browser.select_form(**form_info)
        except mechanize.FormNotFoundError:
            logger.error('failed to find form %s at %s', form_info, url or self.browser.geturl())
            return

        for key, val in fields.items():
            try:
                self.browser[key] = val
            except Exception:
                logger.error('failed to set form field "%s" at %s', key, url or self.browser.geturl())

        return self.browser.submit()

def get_website_name(url):
    name = urlparse(url.lower()).netloc
    name = re.sub(r'^www[^\.]*\.|\.[^\.]*$', '', name)
    return name
