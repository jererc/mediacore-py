#!/usr/bin/env python
import os
import re
import shutil
import tempfile
from datetime import timedelta
import unittest
from contextlib import contextmanager, nested
import json
import logging

from mock import patch, Mock

from mediacore.utils.utils import parse_magnet_url
from mediacore.utils.filter import validate_info
from mediacore.utils.filter import logger as filter_logger

from mediacore.web.google import Google
from mediacore.web.youtube import Youtube
from mediacore.web.imdb import Imdb
from mediacore.web.tvrage import Tvrage
from mediacore.web.sputnikmusic import Sputnikmusic
from mediacore.web.lastfm import Lastfm
from mediacore.web.vcdquality import Vcdquality
from mediacore.web.opensubtitles import Opensubtitles, DownloadQuotaReached
from mediacore.web.subscene import Subscene

from mediacore.web.search import Result, results
from mediacore.web.search.plugins.thepiratebay import Thepiratebay
from mediacore.web.search.plugins.torrentz import Torrentz
from mediacore.web.search.plugins.filestube import Filestube


GENERIC_QUERY = 'lost'

MOVIE = 'blue velvet'
MOVIE_DIRECTOR = 'david lynch'
MOVIE_YEAR = 1986

TVSHOW = 'mad men'
TVSHOW_SEASON = '5'
TVSHOW_EPISODE = '06'
TVSHOW_YEAR = 2007

BAND = 'breach'
ALBUM = 'kollapse'
ALBUM_YEAR = 2001
BAND2 = 'radiohead'

OPENSUBTITLES_LANG = 'eng'
SUBSCENE_LANG = 'english'

logging.basicConfig(level=logging.DEBUG)

conf = {
    'opensubtitles_username': '',
    'opensubtitles_password': '',
    'filestube_api_key': '',
    'temp_dir': '/tmp',
    }
try:
    conf_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
            'tests_config.json')
    with open(conf_file) as fd:
        conf.update(json.load(fd))
except Exception, e:
    logging.debug('failed to load tests config: %s' % str(e))

is_connected = Google().accessible


@contextmanager
def mkdtemp(dir=conf['temp_dir']):
    temp_dir = tempfile.mkdtemp(prefix='tests_', dir=dir)
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)


#
# Utils
#
class MagnetUrlTest(unittest.TestCase):

    def setUp(self):
        pass

    def test_parse_single(self):
        url = 'magnet:?xt=urn:btih:HASH&dn=TITLE&key=VALUE'

        res = parse_magnet_url(url)

        self.assertTrue(isinstance(res, dict))
        self.assertEqual(res.get('dn'), ['TITLE'])
        self.assertEqual(res.get('key'), ['VALUE'])

    def test_parse_multiple(self):
        url = 'magnet:?xt=urn:btih:HASH&dn=TITLE&key=VALUE1&key=VALUE2&key=VALUE3'

        res = parse_magnet_url(url)

        self.assertTrue(isinstance(res, dict))
        self.assertEqual(res.get('dn'), ['TITLE'])
        self.assertEqual(sorted(res.get('key')), ['VALUE1', 'VALUE2', 'VALUE3'])


def no_logging(*args, **kwargs): pass

filter_logger.error = no_logging

class FilterTest(unittest.TestCase):

    def setUp(self):
        pass

    # Invalid
    def test_int_invalid_filter_type(self):
        info = {'rating': 5}
        filters = {'rating': 4}
        self.assertEqual(validate_info(info, filters), None)

    def test_int_invalid_filter_name(self):
        info = {'rating': 5}
        filters = {'rating': {'invalid': 4}}
        self.assertEqual(validate_info(info, filters), None)

    def test_string_invalid_filter_type(self):
        info = {'genre': 'genre1'}
        filters = {'genre': 'genre1'}
        self.assertEqual(validate_info(info, filters), None)

    def test_string_invalid_filter_name(self):
        info = {'genre': 'genre1'}
        filters = {'genre': {'invalid': ['genre1']}}
        self.assertEqual(validate_info(info, filters), None)

    def test_int_none_match(self):
        info = {'rating': 5}
        filters = {'rating': {'min': None}}
        self.assertEqual(validate_info(info, filters), True)

    def test_int_empty_string_match(self):
        info = {'rating': 5}
        filters = {'rating': {'min': ''}}
        self.assertEqual(validate_info(info, filters), True)

    def test_include_list_empty_string_match(self):
        info = {'genre': ['genre1', 'genre2']}
        filters = {'genre': {'include': ''}}
        self.assertEqual(validate_info(info, filters), True)

    def test_include_string_empty_list_match(self):
        info = {'genre': ['genre1', 'genre2']}
        filters = {'genre': {'include': []}}
        self.assertEqual(validate_info(info, filters), True)

    def test_exclude_list_empty_string_match(self):
        info = {'genre': ['genre1', 'genre2']}
        filters = {'genre': {'exclude': ''}}
        self.assertEqual(validate_info(info, filters), True)

    def test_exclude_string_empty_list_match(self):
        info = {'genre': ['genre1', 'genre2']}
        filters = {'genre': {'exclude': []}}
        self.assertEqual(validate_info(info, filters), True)

    # Int
    def test_int_no_match(self):
        info = {'rating': 5}
        filters = {'rating': {'min': 6}}
        self.assertEqual(validate_info(info, filters), False)

    def test_int_match(self):
        info = {'rating': 5}
        filters = {'rating': {'min': 4}}
        self.assertEqual(validate_info(info, filters), True)

    # String
    def test_include_empty_string_match(self):
        info = {'genres': ['genre1', 'genre2']}
        filters = {'genres': {'include': ''}}
        self.assertEqual(validate_info(info, filters), True)

    def test_exclude_empty_string_match(self):
        info = {'genres': ['genre1', 'genre2']}
        filters = {'genres': {'exclude': ''}}
        self.assertEqual(validate_info(info, filters), True)

    def test_include_string_no_match(self):
        info = {'genres': ['genre1', 'genre2']}
        filters = {'genres': {'include': '\bgenre3\b'}}
        self.assertEqual(validate_info(info, filters), False)

    def test_include_string_match(self):
        info = {'genres': ['genre1', 'genre2']}
        filters = {'genres': {'include': '\\bgenre1\\b'}}
        self.assertEqual(validate_info(info, filters), True)

    def test_exclude_string_no_match(self):
        info = {'genres': ['genre1', 'genre2']}
        filters = {'genres': {'exclude': '\bgenre3\b'}}
        self.assertEqual(validate_info(info, filters), True)

    def test_exclude_string_match(self):
        info = {'genres': ['genre1', 'genre2']}
        filters = {'genres': {'exclude': '\\bgenre1\\b'}}
        self.assertEqual(validate_info(info, filters), False)

    # List
    def test_include_empty_list_match(self):
        info = {'genres': ['genre1', 'genre2']}
        filters = {'genres': {'include': []}}
        self.assertEqual(validate_info(info, filters), True)

    def test_exclude_empty_list_match(self):
        info = {'genres': ['genre1', 'genre2']}
        filters = {'genres': {'exclude': []}}
        self.assertEqual(validate_info(info, filters), True)

    def test_include_list_no_match(self):
        info = {'genres': ['genre1', 'genre2']}
        filters = {'genres': {'include': ['genre3', 'genre4']}}
        self.assertEqual(validate_info(info, filters), False)

    def test_include_list_match_string(self):
        info = {'genres': 'genre1'}
        filters = {'genres': {'include': ['genre1', 'genre3']}}
        self.assertEqual(validate_info(info, filters), True)

    def test_include_list_single_match_list(self):
        info = {'genres': ['genre1', 'genre2']}
        filters = {'genres': {'include': ['genre1']}}
        self.assertEqual(validate_info(info, filters), True)

    def test_include_list_match(self):
        info = {'genres': ['genre1', 'genre2']}
        filters = {'genres': {'include': ['genre1', 'genre3']}}
        self.assertEqual(validate_info(info, filters), True)

    def test_exclude_list_single_match_list(self):
        info = {'genres': ['genre1', 'genre2']}
        filters = {'genres': {'exclude': ['genre3']}}
        self.assertEqual(validate_info(info, filters), True)

    def test_exclude_list_single_no_match_list(self):
        info = {'genres': ['genre1', 'genre2']}
        filters = {'genres': {'exclude': ['genre1']}}
        self.assertEqual(validate_info(info, filters), False)

    def test_exclude_list_match(self):
        info = {'genres': ['genre1', 'genre2']}
        filters = {'genres': {'exclude': ['genre1', 'genre3']}}
        self.assertEqual(validate_info(info, filters), False)


class ResultTest(unittest.TestCase):

    def setUp(self):
        self.result = Result()
        self.result.title = 'test title'

    # Include
    def test_not_validate_result_include_regex(self):
        regex = re.compile('\\bother\\b', re.I)
        self.assertFalse(self.result._validate_title(include=regex))

    def test_not_validate_result_include_string(self):
        regex = '\\bother\\b'
        self.assertFalse(self.result._validate_title(include=regex))

    def test_validate_result_include_regex(self):
        regex = re.compile('\\btest\\b', re.I)
        self.assertTrue(self.result._validate_title(include=regex))

    def test_validate_result_include_string(self):
        regex = '\\btest\\b'
        self.assertTrue(self.result._validate_title(include=regex))

    # Exclude
    def test_not_validate_result_exclude_regex(self):
        regex = re.compile('\\btest\\b', re.I)
        self.assertFalse(self.result._validate_title(exclude=regex))

    def test_not_validate_result_exclude_string(self):
        regex = '\\btest\\b'
        self.assertFalse(self.result._validate_title(exclude=regex))

    def test_validate_result_exclude_regex(self):
        regex = re.compile('\\bother\\b', re.I)
        self.assertTrue(self.result._validate_title(exclude=regex))

    def test_validate_result_exclude_string(self):
        regex = '\\bother\\b'
        self.assertTrue(self.result._validate_title(exclude=regex))


#
# Web
#
@unittest.skipIf(not is_connected, 'not connected to the internet')
class GoogleTest(unittest.TestCase):

    def setUp(self):
        self.obj = Google()
        self.pages_max = 3

    def test_results(self):
        res = list(self.obj.results(GENERIC_QUERY, pages_max=self.pages_max))

        self.assertTrue(len(res) > 10, 'failed to find enough results for "%s"' % GENERIC_QUERY)
        for r in res:
            for key in ('title', 'url', 'page'):
                self.assertTrue(r.get(key), 'failed to get %s from %s' % (key, r))
        self.assertEqual(res[-1]['page'], self.pages_max, 'last result page (%s) does not equal max pages (%s) for "%s"' % (res[-1]['page'], self.pages_max, GENERIC_QUERY))

    def test_get_nb_results(self):
        res = self.obj.get_nb_results(GENERIC_QUERY)

        self.assertTrue(res > 0, 'failed to get results count for "%s"' % GENERIC_QUERY)


@unittest.skipIf(not is_connected, 'not connected to the internet')
class YoutubeTest(unittest.TestCase):

    def setUp(self):
        self.obj = Youtube()

    def test_results(self):
        res = list(self.obj.results(GENERIC_QUERY))

        self.assertTrue(len(res) > 5, 'failed to find enough results for "%s" (%s)' % (GENERIC_QUERY, len(res)))
        for r in res:
            for key in ('title', 'duration', 'urls_thumbnails', 'url_watch'):
                self.assertTrue(r.get(key), 'failed to get %s from %s' % (key, r))

    def test_get_trailer(self):
        res = self.obj.get_trailer(MOVIE)

        self.assertTrue(res, 'failed to find trailer for "%s"' % MOVIE)
        self.assertTrue('trailer' in res['title'].lower(), 'failed to find movie title "%s" in "%s"' % (MOVIE, res['title']))

    def test_get_track(self):
        res = self.obj.get_track(BAND, ALBUM)

        self.assertTrue(res, 'failed to find track for band "%s" album "%s" ' % (BAND, ALBUM))
        self.assertTrue(BAND.lower() in res['title'].lower(), 'failed to find artist "%s" in "%s"' % (BAND, res['title']))
        self.assertTrue(ALBUM.lower() in res['title'].lower(), 'failed to find album "%s" in "%s"' % (ALBUM, res['title']))


@unittest.skipIf(not is_connected, 'not connected to the internet')
class ImdbTest(unittest.TestCase):

    def setUp(self):
        self.obj = Imdb()

    def test_get_info_movie(self):
        res = self.obj.get_info(MOVIE)

        self.assertTrue(res, 'failed to get info for "%s"' % MOVIE)
        self.assertEqual(res.get('date'), MOVIE_YEAR)
        self.assertTrue(MOVIE_DIRECTOR in res.get('director'), 'failed to get director for %s: %s' % (MOVIE, res.get('director')))
        for key in ('title', 'url', 'rating', 'country', 'genre',
                'runtime', 'stars', 'url_thumbnail'):
            self.assertTrue(res.get(key), 'failed to get %s for "%s"' % (key, MOVIE))

    def test_get_info_movie_with_year_recent(self):
        movie = 'sleeping beauty'
        movie_year = 2011
        movie_director = 'julia leigh'

        res = self.obj.get_info(movie, year=movie_year)

        self.assertTrue(res, 'failed to get info for "%s" (%s)' % (movie, movie_year))
        self.assertEqual(res.get('date'), movie_year)
        self.assertTrue(movie_director in res.get('director'), 'failed to get director for %s: %s' % (movie, res.get('director')))

    def test_get_info_movie_with_year_old(self):
        movie = 'sleeping beauty'
        movie_year = 1959
        movie_director = 'clyde geronimi'

        res = self.obj.get_info(movie, year=movie_year)

        self.assertTrue(res, 'failed to get info for "%s" (%s)' % (movie, movie_year))
        self.assertEqual(res.get('date'), movie_year)
        self.assertTrue(movie_director in res.get('director'), 'failed to get director for %s: %s' % (movie, res.get('director')))

    def test_get_similar_title(self):
        res = self.obj.get_similar(MOVIE, type='title', year=MOVIE_YEAR)

        self.assertTrue(len(res) > 4)
        for r in res:
            for key in ('title', 'url', 'date'):
                self.assertTrue(r.get(key), 'failed to get %s from %s' % (key, r))

    def test_get_similar_name(self):
        res = self.obj.get_similar(MOVIE_DIRECTOR, type='name', year=MOVIE_YEAR)

        self.assertEqual(len(res), 4)
        for r in res:
            for key in ('title', 'url', 'date'):
                self.assertTrue(r.get(key), 'failed to get %s from %s' % (key, r))


@unittest.skipIf(not is_connected, 'not connected to the internet')
class TvrageTest(unittest.TestCase):

    def setUp(self):
        self.max_results = 10
        self.obj = Tvrage()

    def test_get_info(self):
        res = self.obj.get_info(TVSHOW)

        self.assertTrue(res, 'failed to get info for "%s"' % TVSHOW)
        self.assertEqual(res.get('date'), TVSHOW_YEAR)
        for key in ('title', 'url', 'date', 'status', 'classification',
                'runtime', 'network', 'latest_episode', 'country',
                'airs', 'genre'):
            self.assertTrue(res.get(key), 'failed to get %s for "%s"' % (key, TVSHOW))

    def test_get_similar(self):
        res = self.obj.get_similar(TVSHOW)

        self.assertTrue(len(res) > 1, 'failed to get similar for "%s"' % TVSHOW)
        for r in res:
            for key in ('title', 'url'):
                self.assertTrue(r.get(key), 'failed to get %s from %s' % (key, r))

    def test_scheduled_shows(self):
        count = 0
        season_count = 0
        episode_count = 0
        for res in self.obj.scheduled_shows():
            if not res:
                continue

            for key in ('network', 'title', 'url'):
                self.assertTrue(res.get(key), 'failed to get %s from %s' % (key, res))

            if res.get('season'):
                season_count += 1
            if res.get('episode'):
                episode_count += 1

            count += 1
            if count == self.max_results:
                break

        self.assertEqual(count, self.max_results)
        self.assertTrue(season_count > self.max_results / 2)
        self.assertTrue(episode_count > self.max_results / 2)


@unittest.skipIf(not is_connected, 'not connected to the internet')
class SputnikmusicTest(unittest.TestCase):

    def setUp(self):
        self.obj = Sputnikmusic()
        self.artist = BAND
        self.album = ALBUM
        self.album_year = ALBUM_YEAR

    def test_get_info_artist(self):
        res = self.obj.get_info(self.artist)

        self.assertTrue(res, 'failed to get info for "%s"' % self.artist)
        for key in ('url', 'albums'):
            self.assertTrue(res.get(key), 'failed to get %s for "%s"' % (key, self.artist))

    def test_get_info_album(self):
        res = self.obj.get_info(self.artist, self.album)

        self.assertTrue(res, 'failed to get info for artist "%s" album "%s"' % (self.artist, self.album))
        self.assertEqual(res.get('name'), self.album.lower())
        self.assertEqual(res.get('date'), self.album_year)
        for key in ('rating', 'url', 'url_thumbnail'):
            self.assertTrue(res.get(key), 'failed to get %s for artist "%s" album "%s"' % (key, self.artist, self.album))

    def test_get_similar(self):
        res = self.obj.get_similar(self.artist)

        self.assertTrue(res, 'failed to get similar for artist "%s"' % self.artist)
        for r in res:
            for key in ('title', 'url'):
                self.assertTrue(r.get(key), 'failed to get %s from %s' % (key, r))

    def test_reviews(self):
        res = list(self.obj.reviews())

        self.assertTrue(res, 'failed to get reviews')
        for release in res:
            for key in ('artist', 'album', 'rating', 'date', 'url_review', 'url_thumbnail'):
                self.assertTrue(release.get(key), 'failed to get review %s from %s' % (key, release))


@unittest.skipIf(not is_connected, 'not connected to the internet')
class LastfmTest(unittest.TestCase):

    def setUp(self):
        self.artist = BAND
        self.artist2 = BAND2
        self.album = ALBUM
        self.album_year = ALBUM_YEAR
        self.pages_max = 3
        self.obj = Lastfm()

    def test_get_info_artist(self):
        res = self.obj.get_info(self.artist)

        self.assertTrue(res, 'failed to get info for "%s"' % self.artist)
        for key in ('url', 'albums'):
            self.assertTrue(res.get(key), 'failed to get %s for "%s"' % (key, self.artist))

    def test_get_info_album(self):
        res = self.obj.get_info(self.artist, self.album)

        self.assertTrue(res, 'failed to get info for artist "%s" album "%s"' % (self.artist, self.album))
        self.assertEqual(res.get('name'), self.album.lower())
        self.assertEqual(res.get('date'), self.album_year)
        self.assertTrue(res.get('url'))

    def test_get_info_pages(self):
        orig = self.obj.check_next_link

        with nested(patch.object(Lastfm, 'check_next_link'),
                ) as (mock_next,):
            mock_next.side_effect = orig

            self.obj.get_info(self.artist2, pages_max=self.pages_max)

        self.assertEqual(len(mock_next.call_args_list), self.pages_max - 1)

    def test_get_similar(self):
        res = self.obj.get_similar(self.artist)

        self.assertTrue(res, 'failed to get similar for artist "%s"' % self.artist)
        for r in res:
            for key in ('title', 'url'):
                self.assertTrue(r.get(key), 'failed to get %s from %s' % (key, r))

    def test_get_similar_pages(self):
        orig = self.obj.check_next_link

        with nested(patch.object(Lastfm, 'check_next_link'),
                ) as (mock_next,):
            mock_next.side_effect = orig

            list(self.obj.get_similar(self.artist, pages_max=self.pages_max))

        self.assertEqual(len(mock_next.call_args_list), self.pages_max - 1)


@unittest.skipIf(not is_connected, 'not connected to the internet')
class VcdqualityTest(unittest.TestCase):

    def setUp(self):
        self.pages_max = 3
        self.max_results = 10
        self.obj = Vcdquality()

    def test_results(self):
        count = 0
        for res in self.obj.releases(pages_max=self.pages_max):
            if not res:
                continue

            for key in ('release', 'date'):
                self.assertTrue(res.get(key), 'failed to get %s from %s' % (key, res))

            count += 1
            if count == self.max_results:
                break

        self.assertEqual(count, self.max_results)

    def test_results_pages(self):
        orig = self.obj._next

        with nested(patch.object(Vcdquality, '_next'),
                ) as (mock_next,):
            mock_next.side_effect = orig

            list(self.obj.releases(pages_max=self.pages_max))

        self.assertEqual(len(mock_next.call_args_list), self.pages_max - 1)


@unittest.skipIf(not is_connected, 'not connected to the internet')
class OpensubtitlesTest(unittest.TestCase):

    def setUp(self):
        self.max_results = 4
        self.obj = Opensubtitles(conf['opensubtitles_username'],
                conf['opensubtitles_password'])

    def test_logged(self):
        self.assertTrue(self.obj.logged)

    def test_results_movie(self):
        count = 0
        for res in self.obj.results(MOVIE, lang=OPENSUBTITLES_LANG):
            self.assertTrue(res, 'failed to get subtitles url')

            count += 1
            if count == self.max_results:
                break

        self.assertEqual(count, self.max_results, 'failed to find enough subtitles for "%s"' % MOVIE)

    def test_results_tvshow(self):
        count = 0
        for res in self.obj.results(TVSHOW,
                TVSHOW_SEASON, TVSHOW_EPISODE, lang=OPENSUBTITLES_LANG):
            self.assertTrue(res, 'failed to get subtitles url')

            count += 1
            if count == self.max_results:
                break

        self.assertTrue(count > 1, 'failed to find enough subtitles for "%s" season %s episode %s' % (TVSHOW, TVSHOW_SEASON, TVSHOW_EPISODE))

    @unittest.skipIf(not conf['opensubtitles_username'] or not conf['opensubtitles_password'],
            'missing opensubtitles username or password')
    def test_download(self):
        result = False
        for res in self.obj.results(MOVIE, lang=OPENSUBTITLES_LANG):
            with mkdtemp() as temp_dir:
                try:
                    downloaded = self.obj.download(res,
                            os.path.join(temp_dir, 'temp-sub-file'), temp_dir)
                    self.assertTrue(downloaded, 'failed to download subtitles from %s' % res)
                    result = True
                except DownloadQuotaReached:
                    pass
            break

        self.assertTrue(result, 'failed to find subtitles for "%s"' % MOVIE)


@unittest.skipIf(not is_connected, 'not connected to the internet')
class SubsceneTest(unittest.TestCase):

    def setUp(self):
        self.max_results = 4
        self.obj = Subscene()

    def test_results_movie(self):
        count = 0
        for res in self.obj.results(MOVIE, lang=SUBSCENE_LANG):
            self.assertTrue(res, 'failed to get subtitles url')

            count += 1
            if count == self.max_results:
                break

        self.assertEqual(count, self.max_results, 'failed to find enough subtitles for "%s"' % MOVIE)

    def test_results_tvshow(self):
        count = 0
        for res in self.obj.results(TVSHOW,
                TVSHOW_SEASON, TVSHOW_EPISODE, lang=SUBSCENE_LANG):
            self.assertTrue(res, 'failed to get subtitles url')

            count += 1
            if count == self.max_results:
                break

        self.assertTrue(count > 1, 'failed to find enough subtitles for "%s" season %s episode %s' % (TVSHOW, TVSHOW_SEASON, TVSHOW_EPISODE))

    def test_download(self):
        result = False
        for res in self.obj.results(MOVIE, lang=SUBSCENE_LANG):
            with mkdtemp() as temp_dir:
                downloaded = self.obj.download(res,
                        os.path.join(temp_dir, 'temp-sub-file'), temp_dir)
                self.assertTrue(downloaded, 'failed to download subtitles from %s' % res)
                result = True
            break

        self.assertTrue(result, 'failed to find subtitles for "%s"' % MOVIE)


@unittest.skipIf(not is_connected, 'not connected to the internet')
class ThepiratebayTest(unittest.TestCase):

    def setUp(self):
        self.pages_max = 3
        self.max_results = 10
        self.obj = Thepiratebay()

    def test_results(self):
        count = 0
        seeds_count = 0
        for res in self.obj.results(GENERIC_QUERY):
            if not res:
                continue

            for key in ('title', 'url', 'category', 'size', 'date'):
                self.assertTrue(res.get(key) is not None, 'failed to get %s from %s' % (key, res))

            if res.get('seeds') is not None:
                seeds_count += 1

            count += 1
            if count == self.max_results:
                break

        self.assertEqual(count, self.max_results, 'failed to find enough results for "%s"' % (GENERIC_QUERY))
        self.assertTrue(seeds_count > self.max_results * 2 / 3.0)

    def test_results_sort(self):
        for sort in ('date', 'popularity'):
            count = 0
            val_prev = None
            for res in self.obj.results(GENERIC_QUERY, sort=sort):
                if not res:
                    continue

                if sort == 'date':
                    val = res.date
                    if val_prev:
                        self.assertTrue(val <= val_prev + timedelta(seconds=60), '%s %s is not older than %s' % (sort, val, val_prev))
                    val_prev = val

                elif sort == 'popularity':
                    val = res.seeds
                    if val_prev:
                        self.assertTrue(val <= val_prev, '%s %s is not less than %s' % (sort, val, val_prev))
                    val_prev = val

                count += 1
                if count == self.max_results:
                    break

            self.assertTrue(count > self.max_results * 3 / 4.0)

    def test_results_pages(self):
        orig = self.obj._next

        with nested(patch.object(Thepiratebay, '_next'),
                patch.object(Result, 'get_hash'),
                ) as (mock_next, mock_hash):
            mock_next.side_effect = orig
            mock_hash.return_value = None

            list(self.obj.results(GENERIC_QUERY, pages_max=self.pages_max))

        self.assertEqual(len(mock_next.call_args_list), self.pages_max - 1)


@unittest.skipIf(not is_connected, 'not connected to the internet')
class TorrentzTest(unittest.TestCase):

    def setUp(self):
        self.pages_max = 3
        self.max_results = 10
        self.obj = Torrentz()

    def test_results(self):
        count = 0
        seeds_count = 0
        for res in self.obj.results(TVSHOW):
            if not res:
                continue

            for key in ('title', 'url', 'category', 'size', 'date'):
                self.assertTrue(res.get(key) is not None, 'failed to get %s from %s' % (key, res))

            if res.get('seeds') is not None:
                seeds_count += 1

            count += 1
            if count == self.max_results:
                break

        self.assertEqual(count, self.max_results, 'failed to find enough results for "%s"' % (GENERIC_QUERY))
        self.assertTrue(seeds_count > self.max_results * 2 / 3.0)

    def test_results_sort(self):
        for sort in ('date',):  # we do not test popularity since torrentz does not really sort by seeds
            count = 0
            val_prev = None
            for res in self.obj.results(TVSHOW, sort=sort):
                if not res:
                    continue

                if sort == 'date':
                    val = res.date
                    if val_prev:
                        self.assertTrue(val <= val_prev + timedelta(seconds=60), '%s %s is not older than %s' % (sort, val, val_prev))
                    val_prev = val

                elif sort == 'popularity':
                    val = res.seeds
                    if val_prev:
                        self.assertTrue(val <= val_prev, '%s %s is not less than %s' % (sort, val, val_prev))
                    val_prev = val

                count += 1
                if count == self.max_results:
                    break

            self.assertTrue(count > self.max_results * 3 / 4.0)

    def test_results_pages(self):
        orig = self.obj._next

        with nested(patch.object(Torrentz, '_next'),
                patch.object(Torrentz, 'get_link_text'),
                ) as (mock_next, mock_getlink):
            mock_next.side_effect = orig
            mock_getlink.return_value = None

            list(self.obj.results(TVSHOW, pages_max=self.pages_max))

        self.assertEqual(len(mock_next.call_args_list), self.pages_max - 1)


@unittest.skipIf(not is_connected, 'not connected to the internet')
class FilestubeTest(unittest.TestCase):

    def setUp(self):
        self.pages_max = 3
        self.max_results = 10
        self.obj = Filestube(api_key=conf['filestube_api_key'])
        self.query = GENERIC_QUERY

    def test_results(self):
        count = 0
        for res in self.obj.results(self.query):
            if not res:
                continue

            for key in ('title', 'url', 'size', 'date'):
                self.assertTrue(res.get(key) is not None, 'failed to get %s from %s' % (key, res))

            count += 1
            if count == self.max_results:
                break

        self.assertTrue(count > self.max_results * 2 / 3.0, 'failed to find enough results for "%s"' % (self.query))

    def test_results_pages(self):
        orig = self.obj._send

        with nested(patch.object(Filestube, '_send'),
                ) as (mock_send,):
            mock_send.side_effect = orig

            list(self.obj.results(GENERIC_QUERY, pages_max=self.pages_max))

        self.assertEqual(len(mock_send.call_args_list), self.pages_max)


if __name__ == '__main__':
    unittest.main()
