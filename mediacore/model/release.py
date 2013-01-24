from mediacore.utils.db import Model


class Release(Model):
    COL = 'releases'

    @classmethod
    def get_search(cls, release, langs=None):
        category = release['info']['subtype']
        res = {
            'name': release['name'],
            'category': category,
            'langs': langs or [],
            'release_id': release['_id'],
            }
        if category == 'tv':
            res['mode'] = 'inc'
            res['season'] = 1
            res['episode'] = 1
        elif category == 'music':
            res['name'] = release['artist']
            res['album'] = release['album']
        return res
