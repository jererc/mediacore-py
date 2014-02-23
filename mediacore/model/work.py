from mediacore.utils.db import Model


class Work(Model):
    COL = 'work'

    @classmethod
    def get_info(cls, section, key=None, default=None):
        res = cls.find_one({'section': section}) or {}
        info = res.get('info', {})
        return info.get(key, default) if key else info

    @classmethod
    def set_info(cls, section, key, value):
        cls.update({'section': section},
                {'$set': {'section': section, 'info.%s' % key: value}},
                upsert=True, safe=True)

    @classmethod
    def set_infos(cls, section, info, overwrite=False):
        doc = {'section': section, 'info': info}
        cls.update({'section': section},
                doc if overwrite else {'$set': doc}, upsert=True, safe=True)
