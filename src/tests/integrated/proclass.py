import json

from services.pro import ProClassService, ProClassConst

from tests.integrated.util import AsyncTest, AccountContext

class ProClassTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('manage/proclass/add', data={
                'reqtype': 'add',
                'name': 'test',
                'list': '1',
                'type': ProClassConst.OFFICIAL_HIDDEN,
                'desc': 'desc'
            })
            self.assertAPIReturnValue(res.text, ('S', 1))
            err, proclasslist = await ProClassService.inst.get_proclass_list()
            self.assertIsNone(err)
            self.assertEqual(len(proclasslist), 1)
            self.assertEqual(proclasslist[0]['name'], 'test')
            self.assertEqual(proclasslist[0]['type'], ProClassConst.OFFICIAL_HIDDEN)
            self.assertEqual(proclasslist[0]['acct_id'], None)

            err, proclass = await ProClassService.inst.get_proclass(1)
            self.assertIsNone(err)
            assert proclass
            self.assertEqual(proclass['name'], 'test')
            self.assertEqual(proclass['type'], ProClassConst.OFFICIAL_HIDDEN)
            self.assertEqual(proclass['acct_id'], None)
            self.assertEqual(proclass['desc'], 'desc')
            self.assertEqual(proclass['list'], [1])

            res = admin_session.post('proset', data={
                'reqtype': 'listproclass',
                'proclass_type': 'official'
            })
            res = json.loads(res.text)
            proclass_list = res['data']
            self.assertNotEqual(proclass_list, [])

            with AccountContext('test1@test', 'test') as user_session:
                for proclass_type in ('official'):
                    res = user_session.post('proset', data={
                        'reqtype': 'listproclass',
                        'proclass_type': proclass_type
                    })
                    self.assertAPIReturnValue(res.text, ("Eacces", "Permission denied"))

            self.assertTable(
                'manage/proclass/add',
                {
                    'reqtype': 'add',
                    'name': 'test',
                    'list': '1',
                    'type': ProClassConst.OFFICIAL_PUBLIC,
                    'desc': 'desc'
                },
                [
                    {'type': ProClassConst.USER_PUBLIC, 'equal_value': ('Eparam', 'Invalid problem class type')},
                    {'name': '', 'equal_value': ('Eparam', 'Name too short')},
                    {'name': 'name' * 10000, 'equal_value': ('Eparam', 'Name too long')},
                    {'desc': 'desc' * 10000, 'equal_value': ('Eparam', 'Desc too long')},
                ],
                admin_session
            )

            res = admin_session.post('manage/proclass/update', data={
                'reqtype': 'update',
                'proclass_id': 1,
                'name': 'test',
                'list': '1, 2',
                'type': ProClassConst.OFFICIAL_PUBLIC,
                'desc': 'desc desc',
            })
            self.assertAPIReturnSuccess(res.text)

            err, proclass = await ProClassService.inst.get_proclass(1)
            self.assertIsNone(err)
            assert proclass
            self.assertEqual(proclass['type'], ProClassConst.OFFICIAL_PUBLIC)
            self.assertEqual(proclass['acct_id'], None)
            self.assertEqual(proclass['desc'], 'desc desc')
            self.assertEqual(proclass['list'], [1, 2])

            # NOTE: permission
            res = admin_session.post('manage/proclass/update', data={
                'reqtype': 'remove',
                'proclass_id': 1,
            })
            self.assertAPIReturnSuccess(res.text)
            err, _ = await ProClassService.inst.get_proclass(1)
            self.assertEqual(err, ('Enoext', 'Problem class not found'))

            res = admin_session.post('manage/proclass/update', data={
                'reqtype': 'remove',
                'proclass_id': 1,
            })
            self.assertAPIReturnValue(res.text, ('Enoext', 'Problem class not found'))
