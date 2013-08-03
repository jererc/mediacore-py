import os.path
import re
import socket
import cookielib
from httplib import HTTPException
from urllib2 import URLError, HTTPError
import gzip
import logging

import mechanize

from lxml import html

logging.getLogger('selenium').setLevel(logging.ERROR)
from selenium import webdriver

logging.getLogger('pyvirtualdisplay').setLevel(logging.ERROR)
logging.getLogger('pyscreenshot').setLevel(logging.ERROR)
logging.getLogger('easyprocess').setLevel(logging.ERROR)
from pyvirtualdisplay.smartdisplay import SmartDisplay

from systools.system import timeout, TimeoutError

from filetools.title import clean


USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/536.6 (KHTML, like Gecko) Chrome/20.0.1092.0 Safari/536.6'
RE_LINK_TITLE = re.compile(r'<a\s*.*?>(.*?)</a>', re.I)
RE_ENCODING = re.compile(r'.*charset=([^\s]+)', re.I)
REQUEST_TIMEOUT = 30

logger = logging.getLogger(__name__)


class NoHistory(object):
    def add(self, *args, **kwargs): pass
    def clear(self): pass

class Browser(mechanize.Browser):

    def __init__(self, user_agent=USER_AGENT, robust_factory=False,
                debug_http=False, cookie_jar=None, cookie_file=None):
        args = {'history': NoHistory()}
        if robust_factory:
            args['factory'] = mechanize.RobustFactory()
        mechanize.Browser.__init__(self, **args)    # mechanize.Browser is an old style class
        self.addheaders = [('User-Agent', user_agent)]
        self.set_handle_robots(False)
        self.set_handle_refresh(False)

        if cookie_file and cookie_jar is not None:
            self.set_cookiejar(cookie_jar)
            if os.path.exists(cookie_file):
                cookie_jar.load(cookie_file,
                        ignore_discard=False, ignore_expires=False)

        if debug_http:
            self.set_debug_http(True)
        self.tree = None
        self.url_error = None

    def _handle_response(self, response):
        if response.info().getheader('content-encoding') == 'gzip':
            try:
                gz = gzip.GzipFile(fileobj=response, mode='rb')
                data = gz.read()
                response.set_data(data)
                self.set_response(response)
            except IOError:
                pass
            finally:
                gz.close()
        return response

    def _get_tree(self, response):
        data = response.get_data()
        content_type = response.info().getheader('content-type')
        res = RE_ENCODING.findall(content_type)
        if res:
            try:
                data = data.decode(res[0], 'replace')
            except Exception, e:
                logger.error('failed to decode "%s" at %s: %s' % (res[0],
                        response.geturl(), str(e)))
        try:
            return html.fromstring(data)
        except Exception, e:
            logger.error('failed to parse "%s": %s' % (data, str(e)))

    @timeout(REQUEST_TIMEOUT)
    def _mech_open_wrapper(self, *args, **kwargs):
        return mechanize.Browser._mech_open(self, *args, **kwargs)

    def _mech_open(self, *args, **kwargs):
        def get_url():
            url = kwargs.get('url', args[0])
            if hasattr(url, 'get_full_url'):
                url = url.get_full_url()
            return url

        kwargs['timeout'] = REQUEST_TIMEOUT
        try:
            res = self._mech_open_wrapper(*args, **kwargs)
            res = self._handle_response(res)
            self.tree = self._get_tree(res)
            self.url_error = None
            return res
        except HTTPError, e:
            self.url_error = e
            logger.error('failed to open %s: %s' % (get_url(), str(e)))
        except (socket.timeout, TimeoutError), e:
            logger.error('failed to open %s (timeout): %s' % (get_url(), str(e)))
        except (HTTPException, URLError, socket.gaierror,
                socket.error, mechanize.BrowserStateError), e:
            logger.error('failed to open %s: %s' % (get_url(), str(e)))
        except Exception, e:
            logger.exception('exception (args: %s, %s): %s' % (args, kwargs, str(e)))
        self.tree = None

    def follow_link(self, *args, **kwargs):
        try:
            return mechanize.Browser.follow_link(self, *args, **kwargs)
        except (mechanize.LinkNotFoundError, mechanize.BrowserStateError):
            pass

    def cssselect(self, selector, default=None):
        if self.tree is None:
            return default
        return self.tree.cssselect(selector)

    def submit_form(self, url=None, name=None, index=None, fields=None,
            debug=False):
        if url and not self.open(url):
            return
        try:
            self.viewing_html()
        except mechanize.BrowserStateError:
            return

        if debug:
            for form in self.forms():
                logger.info('form: %s' % str(form))

        form_info = {'name': name} if name else {'nr': index or 0}
        try:
            self.select_form(**form_info)
        except mechanize.FormNotFoundError:
            logger.error('failed to find form %s at %s' % (form_info, url or self.geturl()))
            return
        except Exception, e:
            logger.error('failed to find form %s at %s: %s' % (form_info, url or self.geturl(), str(e)))
            return

        for key, val in fields.items():
            try:
                self[key] = val
            except Exception:
                logger.error('failed to set field "%s" to "%s" for form %s' % (key, val, str(self)))

        return self.submit()


class RealBrowser(webdriver.Firefox):

    def __init__(self, timeout=30):
        self._abstract_display = SmartDisplay(visible=0)
        self._abstract_display.start()

        super(RealBrowser, self).__init__()
        self.implicitly_wait(timeout)

    def __del__(self):
        self.quit()
        self._abstract_display.stop()

    @timeout(REQUEST_TIMEOUT)
    def _open(self, url):
        self.get(url)

    def open(self, url):
        try:
            self._open(url)
            return True
        except Exception, e:
            logger.error('failed to open %s: %s' % (url, str(e)))


class Base(object):
    '''Base website class.
    '''
    ROBUST_FACTORY = False

    def __init__(self, cookie_file=None, debug_http=False):
        self.cookie_jar = cookielib.LWPCookieJar() if cookie_file else None
        self.browser = Browser(robust_factory=self.ROBUST_FACTORY,
                cookie_jar=self.cookie_jar, cookie_file=cookie_file,
                debug_http=debug_http)
        self.url = self._get_url()
        self.accessible = True if self.url else False

    def _get_url(self):
        if not isinstance(self.URL, (tuple, list)):
            self.URL = [self.URL]

        for url in self.URL:
            if self.browser.open(url):
                return url

    def save_cookie(self, cookie_file):
        if self.cookie_jar:
            self.cookie_jar.save(cookie_file,
                    ignore_discard=False, ignore_expires=False)

    def get_link_text(self, val):
        res = RE_LINK_TITLE.search(val)
        if res:
            return res.group(1)
        logger.error('failed to get text from link "%s"' % val)

    def check_next_link(self, link, text='next'):
        next_text = clean(self.get_link_text(html.tostring(link)), 1)
        return next_text == text
