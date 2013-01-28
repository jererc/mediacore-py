import re
import logging


logger = logging.getLogger(__name__)


def _validate_string(val, exclude=None, include=None):
    if isinstance(val, (tuple, list)):
        val = ' '.join(val)
    if exclude and re.compile(exclude, re.I).search(val):
        return
    if include and not re.compile(include, re.I).search(val):
        return
    return True

def _validate_number(val, min=None, max=None):
    if min and val < min:
        return
    if max and val > max:
        return
    return True

def _filter(filters):
    for val in filters.values():
        if isinstance(val, (int, float)):
            return _validate_number
        else:
            return _validate_string

def validate_info(info, filters):
    '''Validate media extra info.

    :return: bool, or None if a field is missing
    '''
    for key, filters in filters.items():
        val = info.get(key)
        if val is None:
            return None

        try:
            if not _filter(filters)(val, **filters):
                return False
        except Exception:
            logger.error('failed to validate field "%s" using filters %s' % (key, filters))
            return None

    return True

def validate_extra(extra, filters):
    '''Validate an object extra info.

    :return: bool or None if not processed
    '''
    if not extra:
        return None

    processed = None
    for key, info in extra.items():
        if key not in filters:
            continue

        processed = True
        res = validate_info(info or {}, filters[key] or {})
        if res is None:
            return None
        elif not res:
            return False

    return processed
