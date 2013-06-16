from datetime import datetime

from mediacore.utils.db import Model


class Result(Model):
    COL = 'results'

    @classmethod
    def add_result(cls, result, search_id):
        spec = {'search_id': search_id}
        if result.get('hash'):
            spec['hash'] = result.hash
        else:
            spec['url'] = result.url

        res = cls.update(spec, {'$set': result}, safe=True)
        if not res['updatedExisting']:
            result['search_id'] = search_id
            result['created'] = datetime.utcnow()
            cls.insert(result, safe=True)
