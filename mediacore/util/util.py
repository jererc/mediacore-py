import re
import random
from copy import deepcopy


def list_in(l1, l2, all=True):
    if l1 == l2 == []:
        return True
    elif all:   # True if all items from l1 are in l2
        if not [i for i in l1 if not i in l2]:
            return True
    else:   # True if any item of l1 is in l2
        if [i for i in l1 if i in l2]:
            return True

def get_common(s1, s2, len_min=1):
    '''Get the longest common string.
    '''
    for l in range(len(s1), len_min - 2, -1):
        for i in range(len(s1) - l):
            s = s1[i:i + l + 1]
            if s in s2:
                return s

def split_words(s, sep=r'[\W_]+'):
    return [w for w in re.split(sep, s) if w]

def compare_words(s1, s2):
    '''Get the percentage of common words.
    '''
    result = 0
    for sep in (r'[\W_]+', r'\D+'):
        w1 = split_words(s1.lower(), sep=sep)
        if w1:
            w2 = split_words(s2.lower())
            result += sum([1 for w in w1 if w in w2]) / float(len(w1))
    return result

def randomize(l):
    l_copy = l[:]
    l_random = []
    while l_copy:
        i = random.choice(l_copy)
        l_copy.remove(i)
        l_random.append(i)
    return l_random

def get_re_group(regex, s, i=1, default=''):
    '''Get the group value from a regex search.
    '''
    try:
        return regex.search(s).group(i)
    except AttributeError:
        return default

def get_unique_list(seq):
    '''Return the list without duplicates.
    '''
    keys = {}
    for e in seq:
        keys[e] = 1
    return keys.keys()

def in_range(n, val_min=None, val_max=None):
    if val_min and n < val_min:
        return False
    elif val_max and n > val_max:
        return False
    return True

def update_dict(dict_src, dict_update):
    '''Return the copy of dict with an update.
    '''
    res = deepcopy(dict_src)
    res.update(dict_update)
    return res

def prefix_dict(dict_src, prefix):
    res = {}
    for key, val in dict_src.items():
        res['%s%s' % (prefix, key)] = val
    return res
