#!/usr/bin/env python
import os
import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta
import unittest
import logging

import settings

from mediacore.util.db import connect, get_db
from mediacore.util.title import Title, clean, get_episode_info
from mediacore.util.transmission import Transmission

from mediacore.model import Base
from mediacore.model.search import Search

from mediacore.web.google import Google
from mediacore.web.imdb import Imdb
from mediacore.web.tvrage import Tvrage
from mediacore.web.opensubtitles import Opensubtitles, DownloadQuotaReached
from mediacore.web.sputnikmusic import Sputnikmusic
from mediacore.web.vcdquality import Vcdquality

from mediacore.web import torrent
from mediacore.web.torrent.plugins.thepiratebay import Thepiratebay
from mediacore.web.torrent.plugins.torrentz import Torrentz
from mediacore.web.torrent.plugins.isohunt import Isohunt


DB_TESTS = 'test'
GENERIC_QUERY = 'lost'

MOVIE = 'blue velvet'
MOVIE_DIRECTOR = 'david lynch'
MOVIE_YEAR = 1986

TVSHOW = 'mad men'
TVSHOW_SEASON = '5'
TVSHOW_EPISODE = '06'
TVSHOW_YEAR = 2007

# ANIME = 'bleach'

BAND = 'radiohead'
ALBUM = 'ok computer'
ALBUM_YEAR = 1997

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

# TODO: add system requirements tests

class TransmissionTest(unittest.TestCase):

    def setUp(self):
        pass

    def test_transmission(self):
        transmission = Transmission(
                host=settings.TRANSMISSION_HOST,
                port=settings.TRANSMISSION_PORT,
                username=settings.TRANSMISSION_USERNAME,
                password=settings.TRANSMISSION_PASSWORD)

        self.assertTrue(transmission.logged, 'failed to connect to transmission rpc server')


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

            self.assertEquals(res, None)

    def test_title(self):
        for title, name, season, episode, episode_alt, rip in self.fixtures:
            res = Title(title)

            self.assertEquals(res.name, name)
            self.assertEquals(res.season, season)
            self.assertEquals(res.episode, episode)


class TitleTvTest(unittest.TestCase):

    def setUp(self):
        self.fixtures = [
            ('show name s03e02 HDTV XviD TEAM',
                'show name', '3', '02', '', ' HDTV XviD TEAM'),
            ('Show Name S03E02 HDTV XviD TEAM',
                'show name', '3', '02', '', ' HDTV XviD TEAM'),
            ('show name s03e02-03 HDTV XviD TEAM',
                'show name', '3', '02', '', '-03 HDTV XviD TEAM'),
            ('show name s03e02',
                'show name', '3', '02', '', ''),
            ('show name 3x02',
                'show name', '3', '02', '', ''),
            ('show name 11 3x02',
                'show name 11', '3', '02', '', ''),
            ('show name 11 3X02',
                'show name 11', '3', '02', '', ''),
            ('show name 111 3x02',
                'show name 111', '3', '02', '', ''),
            ('show name 102 1998 3x02',
                'show name 102 1998', '3', '02', '', ''),
            ('show name 1998-2008 3x02',
                'show name 1998 2008', '3', '02', '', ''),
            ('show name 302',
                'show name', '3', '02', '302', ''),
            ('show name 11 302',
                'show name 11', '3', '02', '302', ''),
            ('show name part 2 HDTV XviD TEAM',
                'show name', '', '2', '', ' HDTV XviD TEAM'),
            ('show name part2 HDTV XviD TEAM',
                'show name', '', '2', '', ' HDTV XviD TEAM'),

            ('anime name 002',
                'anime name', '', '02', '002', ''),
            ('anime name 02',
                'anime name', '', '02', '02', ''),
            ('anime name 302',
                'anime name', '3', '02', '302', ''),
            ('Naruto_Shippuuden_-_261_[480p]',
                'naruto shippuuden', '2', '61', '261', ' [480p]'),
            ]

    def test_episode_info(self):
        for title, name, season, episode, episode_alt, rip in self.fixtures:
            res = get_episode_info(title)

            self.assertEquals(res, (name, season, episode, episode_alt, rip))

    def test_title(self):
        for title, name, season, episode, episode_alt, rip in self.fixtures:
            res = Title(title)

            self.assertEquals(res.name, name)
            self.assertEquals(res.season, season)
            self.assertEquals(res.episode, episode)


# TODO
# class TitleAudioTest(unittest.TestCase):

#     def setUp(self):
#         self.fixtures = [
#             ('Artist_Name_-_Album_Name_-_2012_-_TEAM',
#                 'artist name', 'album name', 2012),
#             ('Artist_Name-Album_Name-2012-TEAM',
#                 'artist name', 'album name', 2012),
#             ('07-Artist_Name-Album_Name.mp3',
#                 'artist name', 'album name', 2012),
#             ]

#     def test_title(self):
#         for title, artist, album, date in self.fixtures:
#             res = Title(title)


class PreviousEpisodeTest(unittest.TestCase):

    def setUp(self):
        self.fixtures = [
            ('show name 1x23', '1', '22'),
            ('show name s01e03', '1', '02'),
            ('show name 1x01', '1', '00'),
            ('show name s02e01', '2', '00'),
            ('show name 123', '1', '22'),
            ('show name 100', '0', '99'),
            ]

    def test_previous_episode(self):
        for query, season, episode in self.fixtures:
            res = Title(query).get_previous_episode()

            self.assertEquals(res, (season, episode))


class SearchQueryTest(unittest.TestCase):

    def setUp(self):
        self.fixtures = [
            ('show name',
                None, None),
            ('show name 2012',
                None, None),
            ('show name 20x12',
                'show name 20x13', 'show name 21x01'),
            ('show name s03e02',
                'show name 3x03', 'show name 4x01'),
            ('show name 11x03',
                'show name 11x04', 'show name 12x01'),
            ('show name 23 1x02',
                'show name 23 1x03', 'show name 23 2x01'),

            ('anime name 009',
                'anime name 010', None),
            ('anime name 02',
                'anime name 03', None),
            ('anime name 99',
                'anime name 100', None),
            ('anime name 132',
                'anime name 133', None),
            ('anime name 299',
                'anime name 300', None),
            ]

    def test_episode_info(self):
        for query, query_next_episode, query_next_season in self.fixtures:

            res = Search().get_next_episode(query)
            self.assertEquals(query_next_episode, res)

            res = Search().get_next_season(query)
            self.assertEquals(query_next_season, res)


class TitleSearchTest(unittest.TestCase):

    def setUp(self):
        self.fixtures_tv = [
            ('show name', '.show.name.'),
            ('show name', 'the.show.name.'),
            ('show name', 'SHOWS NAMES'),
            ('show name 2011', 'show name 2011'),
            ('show name 20x11', 'show name s20e11'),
            ('show name 1x23', 'show name s01e23'),
            ('show name 01x23', 'show name s01e23'),
            ('show name 1x23', 'show name s01e23 episode title'),
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
            ('my movie name', 'My.Movie.Name.2012.DVDRip.XviD-TEAM')
            ]

        self.fixtures_movies_err = [
            ('my movie name', 'My.Name.Movie.2012.DVDRip.XviD-TEAM')
            # ('my movie name', 'My.Movie.Name.II.2012.DVDRip.XviD-TEAM')
            ]

    def test_search_tv(self):
        for query, title in self.fixtures_tv:
            res = Title(query).get_search_re()

            self.assertTrue(res.search(title), '"%s" should match "%s"' % (res.pattern, title))

        for query, title in self.fixtures_tv_err:
            res = Title(query).get_search_re()

            self.assertFalse(res.search(title), '"%s" should not match "%s"' % (res.pattern, title))

    def test_search_movies(self):
        for query, title in self.fixtures_movies:
            res = Title(query).get_search_re('word3')

            self.assertTrue(res.search(title), '"%s" should match "%s"' % (res.pattern, title))

        for query, title in self.fixtures_movies_err:
            res = Title(query).get_search_re('word3')

            self.assertFalse(res.search(title), '"%s" should not match "%s"' % (res.pattern, title))


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
        self.assertEquals(Base().col.database.name, DB_TESTS)

    def test_insert(self):
        Base().insert(self.doc)

        res = get_db()[self.col].find()
        self.assertEquals(res.count(), 1)
        self.assertEquals(res[0], self.doc)

    def test_find(self):
        doc1 = {'some_field': 'some_value'}
        doc2 = {'some_other_field': 'some_other_value'}
        get_db()[self.col].insert(doc1)
        get_db()[self.col].insert(doc2)

        res = Base().find()
        self.assertEquals(res.count(), 2)
        self.assertTrue(doc1 in res)
        self.assertTrue(doc2 in res)

    def test_find_one(self):
        get_db()[self.col].insert(self.doc)

        res = Base().find()
        self.assertEquals(res.count(), 1)
        self.assertEquals(res[0], self.doc)


#
# Web
#

@unittest.skipIf(not is_connected, 'not connected to the internet')
class GoogleTest(unittest.TestCase):

    def setUp(self):
        self.google = Google()
        self.pages_max = 3

    def test_results(self):
        res = list(self.google.results(GENERIC_QUERY, pages_max=self.pages_max))
        self.assertTrue(res, 'failed to find results for "%s"' % GENERIC_QUERY)

        for r in res:
            for key in ('title', 'url', 'page'):
                self.assertTrue(r.get(key), 'failed to get %s from %s' % (key, r))

        self.assertEquals(res[-1]['page'], self.pages_max, 'last result page (%s) does not equal max pages (%s) for "%s"' % (res[-1]['page'], self.pages_max, GENERIC_QUERY))

    def test_get_nb_results(self):
        res = self.google.get_nb_results(GENERIC_QUERY)
        self.assertTrue(res, 'failed to get results count for "%s"' % GENERIC_QUERY)
        self.assertTrue(res > 0, 'failed to get results count for "%s"' % GENERIC_QUERY)


@unittest.skipIf(not is_connected, 'not connected to the internet')
class ImdbTest(unittest.TestCase):

    def setUp(self):
        self.object = Imdb()

    def test_get_info_movie(self):
        res = self.object.get_info(MOVIE)
        self.assertTrue(res, 'failed to get info for "%s"' % MOVIE)

        self.assertEquals(res.get('date'), MOVIE_YEAR)
        self.assertTrue(MOVIE_DIRECTOR in res.get('director'), 'failed to get director for %s: %s' % (MOVIE, res.get('director')))

        for key in ('url', 'rating', 'country', 'genre', 'runtime', 'stars', 'url_thumbnail'):
            self.assertTrue(res.get(key), 'failed to get %s for "%s"' % (key, MOVIE))

    def test_get_info_movie_with_year_recent(self):
        movie = 'sleeping beauty'
        movie_year = 2011
        movie_director = 'julia leigh'

        res = self.object.get_info(movie, year=movie_year)
        self.assertTrue(res, 'failed to get info for "%s" (%s)' % (movie, movie_year))

        self.assertEquals(res.get('date'), movie_year)
        self.assertTrue(movie_director in res.get('director'), 'failed to get director for %s: %s' % (movie, res.get('director')))

    def test_get_info_movie_with_year_old(self):
        movie = 'sleeping beauty'
        movie_year = 1959
        movie_director = 'clyde geronimi'

        res = self.object.get_info(movie, year=movie_year)
        self.assertTrue(res, 'failed to get info for "%s" (%s)' % (movie, movie_year))

        self.assertEquals(res.get('date'), movie_year)
        self.assertTrue(movie_director in res.get('director'), 'failed to get director for %s: %s' % (movie, res.get('director')))


@unittest.skipIf(not is_connected, 'not connected to the internet')
class TvrageTest(unittest.TestCase):

    def setUp(self):
        self.object = Tvrage()

    def test_get_info(self):
        res = self.object.get_info(TVSHOW)
        self.assertTrue(res, 'failed to get info for "%s"' % TVSHOW)

        self.assertEquals(res.get('date'), TVSHOW_YEAR)

        for key in ('date', 'status', 'style', 'runtime', 'network', 'latest_episode',
                'next_episode', 'url', 'country', 'date', 'airs', 'genre',):
            self.assertTrue(res.get(key), 'failed to get %s for "%s"' % (key, TVSHOW))

    def test_scheduled_shows(self):
        res = list(self.object.scheduled_shows())
        self.assertTrue(res, 'failed to get scheduled shows')

        season_count = 0
        episode_count = 0
        for r in res:
            if r.get('season'):
                season_count += 1
            if r.get('episode'):
                episode_count += 1

            for key in ('name', 'network', 'url'):
                self.assertTrue(r.get(key), 'failed to get %s from %s' % (key, r))

        self.assertTrue(season_count > len(res) * 2 / 3)
        self.assertTrue(episode_count > len(res) * 2 / 3)


@unittest.skipIf(not is_connected, 'not connected to the internet')
class OpensubtitlesTest(unittest.TestCase):

    def setUp(self):
        self.object = Opensubtitles(settings.OPENSUBTITLES_USERNAME, settings.OPENSUBTITLES_PASSWORD)

    def test_logged(self):
        self.assertTrue(self.object.logged)

    def test_subtitles_movie(self):
        res = list(self.object.results(MOVIE, lang=OPENSUBTITLES_LANG))
        self.assertTrue(res, 'failed to find subtitles for "%s"' % MOVIE)

        for r in res:
            for key in ('filename', 'url'):
                self.assertTrue(r.get(key), 'failed to get %s from subtitles %s' % (key, r))

    def test_subtitles_tvshow(self):
        res = list(self.object.results(TVSHOW, TVSHOW_SEASON, TVSHOW_EPISODE, lang=OPENSUBTITLES_LANG))
        self.assertTrue(res, 'failed to find subtitles for "%s" season %s episode %s' % (TVSHOW, TVSHOW_SEASON, TVSHOW_EPISODE))

        for r in res:
            for key in ('filename', 'url'):
                self.assertTrue(r.get(key), 'failed to get %s from subtitles %s' % (key, r))

    @unittest.skipIf(not settings.OPENSUBTITLES_USERNAME or not settings.OPENSUBTITLES_PASSWORD, 'missing opensubtitles credentials')
    def test_save_subtitles(self):
        res = list(self.object.results(MOVIE, lang=OPENSUBTITLES_LANG))
        self.assertTrue(res, 'failed to find subtitles for "%s"' % MOVIE)

        with mkdtemp() as temp_dir:
            try:
                saved = self.object.save(res[0]['url'], os.path.join(temp_dir, res[0]['filename']))
                self.assertTrue(saved, 'failed to save subtitles %s (%s)' % (res[0]['filename'], res[0]['url']))
            except DownloadQuotaReached:
                pass


@unittest.skipIf(not is_connected, 'not connected to the internet')
class SputnikmusicTest(unittest.TestCase):

    def setUp(self):
        self.object = Sputnikmusic()
        self.artist = BAND
        self.album = ALBUM
        self.album_year = ALBUM_YEAR

    def test_get_info(self):
        res = self.object.get_info(self.artist)
        self.assertTrue(res, 'failed to get info for "%s"' % self.artist)

        for key in ('url_band', 'albums', 'similar_bands'):
            self.assertTrue(res.get(key), 'failed to get %s for "%s"' % (key, self.artist))

    def test_get_album_info(self):
        res = self.object.get_album_info(self.artist, self.album)
        self.assertTrue(res, 'failed to get info for artist "%s" album "%s"' % (self.artist, self.album))

        self.assertEquals(res.get('name'), self.album.lower())
        self.assertEquals(res.get('date'), self.album_year)

        for key in ('rating', 'url', 'url_cover'):
            self.assertTrue(res.get(key), 'failed to get %s for artist "%s" album "%s"' % (key, self.artist, self.album))

    def test_reviews(self):
        res = list(self.object.reviews())
        self.assertTrue(res, 'failed to get reviews')

        for release in res:
            for key in ('artist', 'album', 'rating', 'date', 'url_review', 'url_thumbnail'):
                self.assertTrue(release.get(key), 'failed to get review %s from %s' % (key, release))


@unittest.skipIf(not is_connected, 'not connected to the internet')
class VcdqualityTest(unittest.TestCase):

    def setUp(self):
        self.object = Vcdquality()
        self.pages_max = 3

    def test_results(self):
        res = list(self.object.results(pages_max=self.pages_max))
        self.assertTrue(res, 'failed to find results')

        for r in res:
            for key in ('release', 'date', 'page'):
                self.assertTrue(r.get(key), 'failed to get %s from %s' % (key, r))

        self.assertEquals(res[-1]['page'], self.pages_max, 'failed to get all results pages: last result page (%s) != max pages (%s)' % (res[-1]['page'], self.pages_max))


#
# Torrent
#

class MagnetUrlTest(unittest.TestCase):

    def setUp(self):
        pass

    def test_parse_single(self):
        url = 'magnet:?xt=urn:btih:HASH&dn=TITLE&key=VALUE'
        res = torrent.parse_magnet_url(url)

        self.assertTrue(isinstance(res, dict))
        self.assertEquals(res.get('dn'), ['TITLE'])
        self.assertEquals(res.get('key'), ['VALUE'])

    def test_parse_multiple(self):
        url = 'magnet:?xt=urn:btih:HASH&dn=TITLE&key=VALUE1&key=VALUE2&key=VALUE3'
        res = torrent.parse_magnet_url(url)

        self.assertTrue(isinstance(res, dict))
        self.assertEquals(res.get('dn'), ['TITLE'])
        self.assertEquals(sorted(res.get('key')), ['VALUE1', 'VALUE2', 'VALUE3'])


@unittest.skipIf(not is_connected, 'not connected to the internet')
class TorrentSearchTest(unittest.TestCase):

    def setUp(self):
        self.pages_max = 3

    def tearDown(self):
        pass

    def test_plugins_results(self):
        for obj_name, obj in [
                ('thepiratebay', Thepiratebay()),
                ('torrentz', Torrentz()),
                # ('isohunt', Isohunt()),
                ]:

            res = list(obj.results(GENERIC_QUERY, pages_max=self.pages_max))
            self.assertTrue(res, 'failed to find results for "%s" with %s' % (GENERIC_QUERY, obj_name))

            seeds_count = 0
            for r in res:
                self.assertTrue(r)

                for key in ('title', 'category', 'size', 'date', 'page'):
                    self.assertTrue(r.get(key) is not None, 'failed to get %s from %s with %s' % (key, r, obj_name))

                self.assertTrue(r.get('url_magnet') or r.get('url_torrent'), 'failed to get torrent url from %s with %s' % (r, obj_name))

                if r.get('seeds') is not None:
                    seeds_count += 1

            self.assertTrue(seeds_count > len(res) * 2 / 3)

            self.assertEquals(res[-1].page, self.pages_max, 'last result page (%s) does not equal max pages (%s) for "%s" with %s' % (res[-1].page, self.pages_max, GENERIC_QUERY, obj_name))

    def test_plugins_results_sort(self):
        for obj_name, obj in [
                ('thepiratebay', Thepiratebay()),
                ('torrentz', Torrentz()),
                # ('isohunt', Isohunt()),
                ]:
            for sort in ('age', 'seeds'):

                if sort == 'seeds' and obj_name == 'torrentz':  # not really sorted by seeds...
                    continue

                val_prev = None
                for res in obj.results(GENERIC_QUERY, sort=sort, pages_max=2):

                    if sort == 'age':
                        val = res.date
                        if val_prev:
                            self.assertTrue(val <= val_prev + timedelta(seconds=60), '%s is not older than %s with %s' % (val, val_prev, obj_name))
                        val_prev = val

                    elif sort == 'seeds':
                        val = res.seeds
                        if val_prev:
                            self.assertTrue(val <= val_prev, '%s is not less than %s with %s' % (val, val_prev, obj_name))
                        val_prev = val

    def test_results(self):
        res = list(torrent.results(GENERIC_QUERY, pages_max=self.pages_max))
        self.assertTrue(res, 'failed to get results for "%s"' % GENERIC_QUERY)

        seeds_count = 0
        for r in res:
            self.assertTrue(r)

            for key in ('net_name', 'title', 'category', 'size', 'page'):
                self.assertTrue(r.get(key) is not None, 'failed to get %s from %s' % (key, r))

            url = r.get('url_magnet') or r.get('url_torrent')
            self.assertTrue(url, 'failed to get url from %s' % r)

            self.assertTrue(isinstance(r.get('date'), datetime), 'date "%s" is not a datetime' % r.get('date'))
            self.assertTrue(isinstance(r.get('size'), float), 'size "%s" is not a float' % r.get('size'))

            if r.get('seeds') is not None:
                seeds_count += 1

        self.assertTrue(seeds_count > len(res) * 2 / 3)

        self.assertEquals(res[-1].page, self.pages_max, 'last result page (%s) does not equal max pages (%s) for "%s"' % (res[-1].page, self.pages_max, GENERIC_QUERY))


if __name__ == '__main__':
    unittest.main(catchbreak=True, verbosity=2)
