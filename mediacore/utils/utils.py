import re
import random
from urlparse import parse_qs
import tempfile
import shutil
from contextlib import contextmanager


RE_URL_MAGNET = re.compile(r'^magnet:\?(.*)', re.I)


def list_in(l1, l2, all=True):
    if l1 == l2 == []:
        return True
    elif all:   # True if all items from l1 are in l2
        if not [i for i in l1 if not i in l2]:
            return True
    else:   # True if any item of l1 is in l2
        if [i for i in l1 if i in l2]:
            return True

def randomize(l):
    l_copy = l[:]
    l_random = []
    while l_copy:
        i = random.choice(l_copy)
        l_copy.remove(i)
        l_random.append(i)
    return l_random

def in_range(n, val_min=None, val_max=None):
    if val_min and n < val_min:
        return False
    elif val_max and n > val_max:
        return False
    return True

def parse_magnet_url(url):
    try:
        qs = RE_URL_MAGNET.search(url).group(1)
        return parse_qs(qs)
    except Exception:
        pass

@contextmanager
def mkdtemp(path):
    temp_dir = tempfile.mkdtemp(prefix='tmp_', dir=path)
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)
