from datetime import datetime

from pymongo.objectid import ObjectId

from mediacore.model import Base
from mediacore.util.title import Title
from mediacore.util.media import files, get_size


class File(Base):
    COL = 'files'

    def add(self, file):
        '''Add a file or path to the collection.
        '''
        for file_ in files(file):
            doc = {
                'file': file_.file,
                'type': file_.type,
                'size': get_size(file_.file) / 1024,
                'info': file_.get_file_info(),
                }
            res = self.get(file=file_.file)
            if not res:
                doc['added'] = datetime.utcnow()
                self.col.insert(doc, safe=True)
            elif not self._compare_info(res, doc):
                self.update(res['_id'], info=doc)

    def _compare_info(self, doc, new_doc):
        for key in new_doc:
            if new_doc[key] != doc[key]:
                return False
        return True

    def search(self, title, type):
        '''Get files matching the title.
        '''
        title_ = Title(title)
        re_name = '.*%s' % '.*'.join(title_.name.split())
        re_full_name = Title(title_.full_name).get_search_re()
        re_display_name = Title(title_.display_name).get_search_re()

        files = []
        for res in self.col.find({
                'type': type,
                '$or': [
                    {'info.full_name': {'$regex': re_name}},
                    {'info.display_name': {'$regex': re_name}},
                    ],
                }):
            if re_full_name.search(res['info'].get('full_name', '')) \
                    or re_display_name.search(res['info'].get('display_name', '')):
                files.append(res['file'])
        return files

    def get(self, id=None, file=None, type=None):
        spec = {}
        if id:
            spec['_id'] = ObjectId(id)
        if file:
            spec['file'] = file
        if type:
            spec['type'] = type
        return self.col.find_one(spec)

    def update(self, id=None, file=None, type=None, spec=None, info=None):
        if not info:
            return

        if not spec:
            spec = {}
        if id:
            spec['_id'] = ObjectId(id)
        if file:
            spec['file'] = file
        if type:
            spec['type'] = type
        return self.col.update(spec, {'$set': info}, safe=True, multi=True)

    def remove(self, id=None, file=None, type=None, spec=None):
        if not spec:
            spec = {}
        if id:
            spec['_id'] = ObjectId(id)
        if file:
            spec['file'] = file
        if type:
            spec['type'] = type
        return self.col.remove(spec, safe=True)
