import os.path
import re
from urlparse import urlparse
from urllib import unquote_plus
from urllib2 import urlopen
import tempfile
import shutil
from contextlib import contextmanager
import logging

import pycurl

from mediacore.util.media import move_file


RE_CONTENT = re.compile(r'filename="(.*?)"', re.I)

logger = logging.getLogger(__name__)


@contextmanager
def mkdtemp(path):
    temp_dir = tempfile.mkdtemp(prefix='download_', dir=path)
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)

def get_filename(url):
    remotefile = urlopen(url)
    data = remotefile.info().get('Content-Disposition')
    if data:
        res = RE_CONTENT.findall(data)
        if res:
            return res[0]

    path = urlparse(url).path
    filename = os.path.basename(path)
    return unquote_plus(filename)

def _download(url, file):
    with open(file, 'wb') as fd:
        curl = pycurl.Curl()
        curl.setopt(pycurl.URL, url)
        curl.setopt(pycurl.FOLLOWLOCATION, 1)
        curl.setopt(pycurl.MAXREDIRS, 5)
        curl.setopt(pycurl.CONNECTTIMEOUT, 30)
        curl.setopt(pycurl.AUTOREFERER, 1)
        # curl.setopt(pycurl.TIMEOUT, 5*3600)
        curl.setopt(pycurl.WRITEDATA, fd)

        try:
            curl.perform()
        except pycurl.error, e:
            logger.error('failed to download %s: %s' % (url, str(e)))
            return
        finally:
            curl.close()

    return True

def download(src, dst, temp_dir):
    if not isinstance(src, (tuple, list)):
        src = [src]

    temp_files = []
    dst_files = []
    with mkdtemp(temp_dir) as temp_dst:
        for url in src:
            filename = get_filename(url)
            temp_file = os.path.join(temp_dst, filename)
            if not _download(url, temp_file):
                return
            temp_files.append(temp_file)

        for temp_file in temp_files:
            res = move_file(temp_file, dst)
            if not res:
                return
            dst_files.append(res)

    return dst_files
