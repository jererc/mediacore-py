import re
import logging

from mediacore.util.title import clean

from systools.system import popen


logger = logging.getLogger(__name__)


class MediainfoError(Exception): pass


def parse(file):
    res = {}

    cmd = ['mediainfo', '-language=raw', '-f', file]
    stdout, stderr, return_code = popen(cmd)
    if return_code is None:
        raise MediainfoError('failed to run command "%s"' % ' '.join(cmd))
    elif return_code != 0:
        logger.error('failed to parse file %s: %s, %s', file, stdout, stderr)
        return res

    cat = None
    for line in stdout:
        fields = re.split(r'\s*:\s*', line.decode('utf-8').lower())

        if len(fields) == 1:
            cat = fields[0]
            if cat:
                res[cat] = {}
        elif cat and len(fields) == 2:
            if not res[cat].get(fields[0]):
                res[cat][fields[0]] = fields[1]

    return res

def get_info(file):
    '''Get main info by category.
    '''
    res = {}

    for cat, info in parse(file).items():

        if cat == 'general':
            try:
                res['duration'] = int(info.get('duration')) / 1000     # seconds
            except Exception:
                pass
            try:
                res['bitrate'] = int(info.get('overall bit rate'))     # bps
            except Exception:
                pass

            # Tags
            res['artist'] = clean(info.get('performer', ''), 1)
            res['album'] = clean(info.get('album', ''), 1)
            try:
                res['date'] = int(info.get('recorded date'))
            except Exception:
                pass
            res['title'] = clean(info.get('track name', ''), 1)
            try:
                res['track_number'] = int(info.get('track name/position'))
            except Exception:
                pass

        else:
            if cat == 'audio #1':
                cat = 'audio'

            try:
                res['%s_bitrate' % cat] = int(info.get('bit rate'))    # bps
            except Exception:
                pass
            res['%s_codec' % cat] = info.get('codec')
            res['%s_codec_id' % cat] = info.get('codec id')

    return res
