import re
import logging


logger = logging.getLogger(__name__)


def _get_pattern(val):
    if isinstance(val, (list, tuple)):
        return r'\b(%s)\b' % '|'.join(val)
    return val

def _validate_string(val, include=None, exclude=None):
    if isinstance(val, (list, tuple)):
        val = ' '.join(val)
    if include and not re.compile(_get_pattern(include), re.I).search(val):
        return
    if exclude and re.compile(_get_pattern(exclude), re.I).search(val):
        return
    return True

def _validate_number(val, min=None, max=None):
    if min and val < min:
        return
    if max and val > max:
        return
    return True

def _validate(val, filters):
    if isinstance(val, (int, float)):
        callable = _validate_number
    else:
        callable = _validate_string
    return callable(val, **filters)

def validate_info(info, filters):
    for key, filters in filters.items():
        val = info.get(key)
        if val is None:
            return None

        try:
            if not _validate(val, filters):
                return False
        except Exception:
            logger.error('failed to validate field "%s" (%s) using filters %s', key, val, filters)
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
        if key not in filters or not info:
            continue

        processed = True
        res = validate_info(info, filters[key] or {})
        if res is None:
            return None
        elif not res:
            return False

    return processed
