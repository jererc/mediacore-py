#!/usr/bin/env python
import os
import shutil
import tempfile
from datetime import datetime, timedelta
import subprocess
import unittest
from contextlib import contextmanager, nested
import logging

from mock import patch, Mock

import settings

from mediacore.util import util
from mediacore.util.db import connect, get_db
from mediacore.util.title import Title, clean, get_episode_info
from mediacore.util.transmission import Transmission

from mediacore.model import Base

from mediacore.web.google import Google
from mediacore.web.youtube import Youtube
from mediacore.web.imdb import Imdb
from mediacore.web.tvrage import Tvrage
from mediacore.web.sputnikmusic import Sputnikmusic
from mediacore.web.lastfm import Lastfm
from mediacore.web.vcdquality import Vcdquality
from mediacore.web.opensubtitles import Opensubtitles, DownloadQuotaReached

from mediacore.web.search import Result, results
from mediacore.web.search.plugins.thepiratebay import Thepiratebay
from mediacore.web.search.plugins.torrentz import Torrentz
from mediacore.web.search.plugins.filestube import Filestube


DB_TESTS = 'test'
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


logging.basicConfig(level=logging.DEBUG)
connect(DB_TESTS)
is_connected = Google().accessible
db_ok = get_db().name == DB_TESTS


@contextmanager
def mkdtemp(dir='/tmp'):
    temp_dir = tempfile.mkdtemp(prefix='mediacore_tests', dir=dir)
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)


#
# System
#
def popen(bin):
        proc = subprocess.Popen(['which', bin],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        return stdout, stderr, proc.returncode

class SystemTest(unittest.TestCase):

    def setUp(self):
        pass

    def test_transmission(self):
        transmission = Transmission(
                host=settings.TRANSMISSION_HOST,
                port=settings.TRANSMISSION_PORT,
                username=settings.TRANSMISSION_USERNAME,
                password=settings.TRANSMISSION_PASSWORD)

        self.assertTrue(transmission.logged, 'failed to connect to transmission rpc server')

    def test_mediainfo(self):
        bin = 'mediainfo'
        stdout, stderr, return_code = popen(bin)
        self.assertEqual(return_code, 0, 'failed to find %s' % bin)

    def test_unzip(self):
        bin = 'unzip'
        stdout, stderr, return_code = popen(bin)
        self.assertEqual(return_code, 0, 'failed to find %s' % bin)

    def test_unrar(self):
        bin = 'unrar'
        stdout, stderr, return_code = popen(bin)
        self.assertEqual(return_code, 0, 'failed to find %s' % bin)

    def test_xvfb(self):
        bin = 'xvfb-run'
        stdout, stderr, return_code = popen(bin)
        self.assertEqual(return_code, 0, 'failed to find %s' % bin)


#
# Title
#

# TODO
# class TitleCleanTest(unittest.TestCase):

#     def setUp(self):
#         self.fixtures = [
#             ('Artist_Name_-_Album_Name_-_2012_-_TEAM',
#                 'artist name', 'album name', 2012),
#             ('Artist_Name-Album_Name-2012-TEAM',
#                 'artist name', 'album name', 2012),
#             ('07-Artist_Name-Album_Name.mp3',
#                 'artist name', 'album name', 2012),
#             ]

#     def test_clean_special(self):
#         pass


class TitleMovieTest(unittest.TestCase):

    def setUp(self):
        self.fixtures = [
            ('movie name DVDrip XviD TEAM',
                'movie name', '', '', '', ' DVDRip XviD TEAM'),
            ('movie name BRRip XviD TEAM',
                'movie name', '', '', '', ' BRRip XviD TEAM'),
            ('movie name 2012 DVDrip XviD TEAM',
                'movie name', '', '', '', ' 2012 DVDRip XviD TEAM'),
            ('movie name (2012) DVDrip',
                'movie name', '', '', '', ' DVDRip'),
            ('movie name 2012 LIMITED BDRip XviD TEAM',
                'movie name', '', '', '', ' LIMITED BDRip XviD TEAM'),
            ('movie name LIMITED BDRip XviD TEAM',
                'movie name', '', '', '', ' LIMITED BDRip XviD TEAM'),
            ('4.44.Last.Day.On.Earth.2011.VODRiP.XViD.AC3-MAJESTiC',
                '4 44 last day on earth', '', '', '', '.VODRiP.XViD.AC3-MAJESTiC'),
            ('movie name 312 LIMITED BDRip XviD TEAM',
                'movie name 312', '', '', '', ' LIMITED BDRip XviD TEAM'),
            ]

    def test_episode_info(self):
        for title, name, season, episode, episode_alt, rip in self.fixtures:
            res = get_episode_info(title)

            self.assertEqual(res, None)

    def test_title(self):
        for title, name, season, episode, episode_alt, rip in self.fixtures:
            res = Title(title)

            self.assertEqual(res.name, name)
            self.assertEqual(res.season, season)
            self.assertEqual(res.episode, episode)


class TitleTvTest(unittest.TestCase):

    def setUp(self):
        self.fixtures = [
            ('show name s03e02 HDTV XviD TEAM',
                'show name', '3', '02', '', ' HDTV XviD TEAM', '3', '02'),
            ('Show Name S03E02 HDTV XviD TEAM',
                'show name', '3', '02', '', ' HDTV XviD TEAM', '3', '02'),
            ('show name s03e02-03 HDTV XviD TEAM',
                'show name', '3', '02', '', '-03 HDTV XviD TEAM', '3', '02'),
            ('show name s03e02',
                'show name', '3', '02', '', '', '3', '02'),
            ('show name 3x02',
                'show name', '3', '02', '', '', '3', '02'),
            ('show name 11 3x02',
                'show name 11', '3', '02', '', '', '3', '02'),
            ('show name 11 3X02',
                'show name 11', '3', '02', '', '', '3', '02'),
            ('show name 111 3x02',
                'show name 111', '3', '02', '', '', '3', '02'),
            ('show name 102 1998 3x02',
                'show name 102 1998', '3', '02', '', '', '3', '02'),
            ('show name 1998-2008 3x02',
                'show name 1998 2008', '3', '02', '', '', '3', '02'),
            ('show name 302',
                'show name', '3', '02', '302', '', '', '302'),
            ('show name 11 302',
                'show name 11', '3', '02', '302', '', '', '302'),
            ('show name part 2 HDTV XviD TEAM',
                'show name', '', '2', '', ' HDTV XviD TEAM', '', '2'),
            ('show name part2 HDTV XviD TEAM',
                'show name', '', '2', '', ' HDTV XviD TEAM', '', '2'),

            ('anime name 002',
                'anime name', '', '02', '002', '', '', '002'),
            ('anime name 02',
                'anime name', '', '02', '02', '', '', '02'),
            ('anime name 302',
                'anime name', '3', '02', '302', '', '', '302'),
            ('Naruto_Shippuuden_-_261_[480p]',
                'naruto shippuuden', '2', '61', '261', ' [480p]', '', '261'),
            ]

    def test_episode_info(self):
        for title, name, season, episode, episode_alt, rip, real_season, real_episode in self.fixtures:
            res = get_episode_info(title)

            self.assertEqual(res, (name, season, episode, episode_alt, rip))

    def test_title(self):
        for title, name, season, episode, episode_alt, rip, real_season, real_episode in self.fixtures:
            res = Title(title)

            self.assertEqual(res.name, name)
            self.assertEqual(res.season, real_season)
            self.assertEqual(res.episode, real_episode)


class PreviousEpisodeTest(unittest.TestCase):

    def setUp(self):
        self.fixtures = [
            ('show name 1x23', '1', '22'),
            ('show name s01e03', '1', '02'),
            ('show name 1x01', '1', '00'),
            ('show name s02e01', '2', '00'),
            ('show name 123', '', '122'),
            ('show name 100', '', '099'),
            ]

    def test_previous_episode(self):
        for query, season, episode in self.fixtures:
            res = Title(query)._get_prev_episode()

            self.assertEqual(res, (season, episode))


class TitleSearchTest(unittest.TestCase):

    def setUp(self):
        self.fixtures_tv = [
            ('show name', '.show.name.'),
            ('show name', 'the.show.name.'),
            ('show name', 'SHOW NAME'),
            ('show name', 'show\'s name\'s'),
            ('show name 2011', 'show name 2011'),
            ('show name 20x11', 'show name s20e11'),
            ('show name 1x23', 'show name s01e23'),
            ('show name 01x23', 'show name s01e23'),
            ('show name 1x23', 'show name s01e23 episode title'),
            ('show name 1x23', 'show name s01e22-23 episode title'),
            ('show name 1x23', 'show name s01e23-24 episode title'),
            ('show name 78 1x23', 'show name 78 s01e23 episode title'),
            ('show name 23 1x23', 'show name 23 s01e23 episode title'),

            ('anime name 123', '[TEAM]_Anime_Name-123_[COMMENT]'),
            ('anime name 123', '[TEAM]_Anime_Name-0123_[COMMENT]'),
            ('anime name 123', '[TEAM]_Anime_Name-ep123_[COMMENT]'),
            ]

        self.fixtures_tv_err = [
            ('show name', '.show.name2.'),
            ('show name', 'that.show.name.'),
            ('show name', 'SHOWS NAMEZ'),
            ('show name 2011', 'show name 2012'),
            ('show name 20x11', 'show name s20e12'),
            ('show name 1x23', 'show name s1e24'),
            ('show name 01x23', 'show name s01e24'),
            ('show name 1x23', 'show name s02e23 episode title'),

            ('anime name 123', '[TEAM]_Anime_Name-124_[COMMENT]'),
            ('anime name 123', '[TEAM]_Anime_Name-1123_[COMMENT]'),
            ('anime name 123', '[TEAM]_Anime_Name-23_[COMMENT]'),
            ]

        self.fixtures_movies = [
            ('my movie name', 'my.movie.name.2012.DVDRip.XviD-TEAM'),
            ('movie name', 'the.movie.name.2012.DVDRip.XviD-TEAM'),
            ('my movie name', 'My.Movie.Name.2012.DVDRip.XviD-TEAM'),
            ('my movie name', 'My.Movie\'s.Name.2012.DVDRip.XviD-TEAM'),
            ]

        self.fixtures_movies_err = [
            ('my movie name', 'My.Other.Movie.Name.2012.DVDRip.XviD-TEAM'),
            ]

    def test_search_tv(self):
        for query, title in self.fixtures_tv:
            res = Title(query).get_search_re()

            self.assertTrue(res.search(title), '"%s" (%s) should match "%s"' % (query, res.pattern, title))

        for query, title in self.fixtures_tv_err:
            res = Title(query).get_search_re()

            self.assertFalse(res.search(title), '"%s" (%s) should not match "%s"' % (query, res.pattern, title))

    def test_search_movies(self):
        for query, title in self.fixtures_movies:
            res = Title(query).get_search_re(mode='__all__')

            self.assertTrue(res.search(title), '"%s" (%s) should match "%s"' % (query, res.pattern, title))

        for query, title in self.fixtures_movies_err:
            res = Title(query).get_search_re(mode='__all__')

            self.assertFalse(res.search(title), '"%s" (%s) should not match "%s"' % (query, res.pattern, title))


#
# Model
#
@unittest.skipIf(not db_ok, 'not connected to the right database')
class ModelTest(unittest.TestCase):

    def setUp(self):
        self.col = 'test_col'
        Base.COL = self.col

        get_db()[self.col].drop()

        self.doc = {'field': 'value'}

    def test_db_name(self):
        self.assertEqual(Base().col.database.name, DB_TESTS)

    def test_insert(self):
        Base().insert(self.doc)

        res = get_db()[self.col].find()
        self.assertEqual(res.count(), 1)
        self.assertEqual(res[0], self.doc)

    def test_find(self):
        doc1 = {'some_field': 'some_value'}
        doc2 = {'some_other_field': 'some_other_value'}
        get_db()[self.col].insert(doc1)
        get_db()[self.col].insert(doc2)

        res = Base().find()
        self.assertEqual(res.count(), 2)
        self.assertTrue(doc1 in res)
        self.assertTrue(doc2 in res)

    def test_find_one(self):
        get_db()[self.col].insert(self.doc)

        res = Base().find()
        self.assertEqual(res.count(), 1)
        self.assertEqual(res[0], self.doc)


#
# Utils
#
class MagnetUrlTest(unittest.TestCase):

    def setUp(self):
        pass

    def test_parse_single(self):
        url = 'magnet:?xt=urn:btih:HASH&dn=TITLE&key=VALUE'
        res = util.parse_magnet_url(url)

        self.assertTrue(isinstance(res, dict))
        self.assertEqual(res.get('dn'), ['TITLE'])
        self.assertEqual(res.get('key'), ['VALUE'])

    def test_parse_multiple(self):
        url = 'magnet:?xt=urn:btih:HASH&dn=TITLE&key=VALUE1&key=VALUE2&key=VALUE3'
        res = util.parse_magnet_url(url)

        self.assertTrue(isinstance(res, dict))
        self.assertEqual(res.get('dn'), ['TITLE'])
        self.assertEqual(sorted(res.get('key')), ['VALUE1', 'VALUE2', 'VALUE3'])


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
        self.assertTrue(len(res) > 10, 'failed to find enough results for "%s"' % GENERIC_QUERY)

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

        for key in ('url', 'rating', 'country', 'genre', 'runtime', 'stars', 'url_thumbnail'):
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

        for key in ('date', 'status', 'classification', 'runtime', 'network',
                'latest_episode', 'url', 'country', 'date', 'airs',
                'genre'):
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

            for key in ('network', 'name', 'url'):
                self.assertTrue(res.get(key), 'failed to get %s from %s' % (key, res))

            if res.get('season'):
                season_count += 1
            if res.get('episode'):
                episode_count += 1

            count += 1
            if count == self.max_results:
                break

        print season_count

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

    def test_get_artist_info(self):
        res = self.obj.get_info(self.artist)
        self.assertTrue(res, 'failed to get info for "%s"' % self.artist)

        for key in ('url_band', 'albums', 'similar_bands'):
            self.assertTrue(res.get(key), 'failed to get %s for "%s"' % (key, self.artist))

    def test_get_album_info(self):
        res = self.obj.get_info(self.artist, self.album)
        self.assertTrue(res, 'failed to get info for artist "%s" album "%s"' % (self.artist, self.album))

        self.assertEqual(res.get('name'), self.album.lower())
        self.assertEqual(res.get('date'), self.album_year)

        for key in ('rating', 'url', 'url_cover'):
            self.assertTrue(res.get(key), 'failed to get %s for artist "%s" album "%s"' % (key, self.artist, self.album))

    def test_get_similar(self):
        res = self.obj.get_similar(self.artist)
        self.assertTrue(res, 'failed to get info for artist "%s" album "%s"' % (self.artist, self.album))

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

        for key in ('url_band', 'albums'):
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

            res = self.obj.get_info(self.artist2, pages_max=self.pages_max)

        self.assertEqual(len(mock_next.call_args_list), self.pages_max - 1)

    def test_get_similar(self):
        res = self.obj.get_similar(self.artist)
        self.assertTrue(res, 'failed to get info for artist "%s" album "%s"' % (self.artist, self.album))

    def test_get_similar_pages(self):
        orig = self.obj.check_next_link

        with nested(patch.object(Lastfm, 'check_next_link'),
                ) as (mock_next,):
            mock_next.side_effect = orig

            res = list(self.obj.get_similar(self.artist, pages_max=self.pages_max))

        self.assertEqual(len(mock_next.call_args_list), self.pages_max - 1)


@unittest.skipIf(not is_connected, 'not connected to the internet')
class VcdqualityTest(unittest.TestCase):

    def setUp(self):
        self.pages_max = 3
        self.max_results = 10
        self.obj = Vcdquality()

    def test_result(self):
        count = 0
        for res in self.obj.results(pages_max=self.pages_max):
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

            res = list(self.obj.results(pages_max=self.pages_max))

        self.assertEqual(len(mock_next.call_args_list), self.pages_max - 1)


@unittest.skipIf(not is_connected, 'not connected to the internet')
class OpensubtitlesTest(unittest.TestCase):

    def setUp(self):
        self.max_results = 10
        self.obj = Opensubtitles(settings.OPENSUBTITLES_USERNAME, settings.OPENSUBTITLES_PASSWORD)

    def test_logged(self):
        self.assertTrue(self.obj.logged)

    def test_results_movie(self):
        count = 0
        for res in self.obj.results(MOVIE, lang=OPENSUBTITLES_LANG):
            for key in ('filename', 'url'):
                self.assertTrue(res.get(key), 'failed to get %s from subtitles %s' % (key, res))

            count += 1
            if count == self.max_results:
                break

        self.assertEqual(count, self.max_results, 'failed to find enough subtitles for "%s"' % MOVIE)

    def test_results_tvshow(self):
        count = 0
        for res in self.obj.results(TVSHOW,
                TVSHOW_SEASON, TVSHOW_EPISODE, lang=OPENSUBTITLES_LANG):
            for key in ('filename', 'url'):
                self.assertTrue(res.get(key), 'failed to get %s from subtitles %s' % (key, res))

            count += 1
            if count == self.max_results:
                break

        self.assertTrue(count > 1, 'failed to find enough subtitles for "%s" season %s episode %s' % (TVSHOW, TVSHOW_SEASON, TVSHOW_EPISODE))

    @unittest.skipIf(not settings.OPENSUBTITLES_USERNAME or not settings.OPENSUBTITLES_PASSWORD, 'missing opensubtitles credentials')
    def test_save(self):
        result = False
        for res in self.obj.results(MOVIE, lang=OPENSUBTITLES_LANG):
            with mkdtemp() as temp_dir:
                try:
                    saved = self.obj.save(res['url'], os.path.join(temp_dir, res['filename']))
                    self.assertTrue(saved, 'failed to save subtitles %s (%s)' % (res['filename'], res['url']))
                    result = True
                except DownloadQuotaReached:
                    pass
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

            res = list(self.obj.results(GENERIC_QUERY, pages_max=self.pages_max))

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
        for sort in ('date',):  # we do not test popularity since torrentz does not really sort by seeds
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

        with nested(patch.object(Torrentz, '_next'),
                patch.object(Torrentz, 'get_link_text'),
                ) as (mock_next, mock_getlink):
            mock_next.side_effect = orig
            mock_getlink.return_value = None

            res = list(self.obj.results(GENERIC_QUERY, pages_max=self.pages_max))

        self.assertEqual(len(mock_next.call_args_list), self.pages_max - 1)


@unittest.skipIf(not is_connected, 'not connected to the internet')
class FilestubeTest(unittest.TestCase):

    def setUp(self):
        self.pages_max = 3
        self.max_results = 10
        self.obj = Filestube()
        self.query = 'mediafire'

    def test_results(self):
        count = 0
        for res in self.obj.results(self.query):
            if not res:
                continue

            for key in ('title', 'url', 'size'):
                self.assertTrue(res.get(key) is not None, 'failed to get %s from %s' % (key, res))

            count += 1
            if count == self.max_results:
                break

        self.assertTrue(count > self.max_results * 2 / 3.0, 'failed to find enough results for "%s"' % (self.query))

    def test_results_pages(self):
        orig = self.obj.check_next_link

        with nested(patch.object(Filestube, 'check_next_link'),
                patch.object(Filestube, '_get_download_info'),
                ) as (mock_next, mock_info):
            mock_next.side_effect = orig
            mock_info.return_value = None

            res = list(self.obj.results(GENERIC_QUERY, pages_max=self.pages_max))

        self.assertEqual(len(mock_next.call_args_list), self.pages_max - 1)


if __name__ == '__main__':
    unittest.main(catchbreak=True, verbosity=2)
