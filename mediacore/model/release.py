from mediacore.model import Base


class Release(Base):
    COL = 'releases'

    def get_search(self, release, langs=None):
        subtype = release['info']['subtype']
        res = {
            'name': release['name'],
            'category': subtype,
            'langs': langs or [],
            'release_id': release['_id'],
            }
        if subtype == 'tv':
            res['mode'] = 'inc'
            res['season'] = 1
            res['episode'] = 1
        elif subtype == 'music':
            res['name'] = release['artist']
            res['album'] = release['album']

        return res
