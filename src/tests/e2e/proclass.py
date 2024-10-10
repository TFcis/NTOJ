import re
import json

from services.pro import ProClassConst

from tests.e2e.util import AsyncTest, AccountContext

class ProClassTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('http://localhost:5501/manage/proclass/add', data={
                'reqtype': 'add',
                'name': 'test',
                'list': '1',
                'type': ProClassConst.OFFICIAL_HIDDEN,
                'desc': 'desc'
            })
            self.assertEqual(res.text, '1')

            html = self.get_html('http://localhost:5501/manage/proclass/update?proclassid=1', admin_session)
            self.assertEqual(html.select_one('input#name').attrs.get('value'), 'test')
            self.assertEqual(html.select_one('input#list').attrs.get('value'), '1')
            self.assertIsNotNone(html.select('select#type > option')[1].attrs.get('selected'))
            res = admin_session.get('http://localhost:5501/manage/proclass/update?proclassid=1')
            self.assertEqual(re.findall(r'j_form\.find\("#desc"\)\.val\(`(.*)`\);', res.text, re.I)[0], 'desc')

            html = self.get_html('http://localhost:5501/proset?proclass_id=1', admin_session)
            trs = html.select('#prolist > tbody > tr')
            self.assertEqual(len(trs), 1)

            res = admin_session.post('http://localhost:5501/proset', data={
                'reqtype': 'listproclass'
            })
            proclass_cata = json.loads(res.text)
            self.assertNotEqual(proclass_cata['official'], [])
            self.assertEqual(proclass_cata['shared'], [])
            self.assertEqual(proclass_cata['own'], [])
            self.assertEqual(proclass_cata['collection'], [])

            with AccountContext('test1@test', 'test') as user_session:
                res = user_session.post('http://localhost:5501/proset', data={
                    'reqtype': 'listproclass'
                })
                proclass_cata = json.loads(res.text)
                self.assertEqual(proclass_cata['official'], [])
                self.assertEqual(proclass_cata['shared'], [])
                self.assertEqual(proclass_cata['own'], [])
                self.assertEqual(proclass_cata['collection'], [])

                res = self.get_html('http://localhost:5501/proset?proclass_id=1', user_session)
                self.assertEqual(res.text, 'Eacces')

            res = admin_session.post('http://localhost:5501/manage/proclass/add', data={
                'reqtype': 'add',
                'name': 'test',
                'list': '1',
                'type': ProClassConst.USER_PUBLIC,
                'desc': 'desc'
            })
            self.assertEqual(res.text, 'Eparam')

            html = self.get_html('http://localhost:5501/proset?proclass_id=1', admin_session)
            trs = html.select('#prolist > tbody > tr')
            self.assertEqual(len(trs), 1)

            res = admin_session.post('http://localhost:5501/manage/proclass/update', data={
                'reqtype': 'update',
                'proclass_id': 1,
                'name': 'test',
                'list': '1, 2',
                'type': ProClassConst.OFFICIAL_PUBLIC,
                'desc': 'desc desc',
            })
            self.assertEqual(res.text, 'S')

            html = self.get_html('http://localhost:5501/manage/proclass/update?proclassid=1', admin_session)
            self.assertEqual(html.select_one('input#name').attrs.get('value'), 'test')
            self.assertEqual(html.select_one('input#list').attrs.get('value'), '1, 2')
            self.assertIsNotNone(html.select('select#type > option')[0].attrs.get('selected'))
            res = admin_session.get('http://localhost:5501/manage/proclass/update?proclassid=1')
            self.assertEqual(re.findall(r'j_form\.find\("#desc"\)\.val\(`(.*)`\);', res.text, re.I)[0], 'desc desc')

            html = self.get_html('http://localhost:5501/proset?proclass_id=1', admin_session)
            trs = html.select('#prolist > tbody > tr')
            self.assertEqual(len(trs), 2)
            res = admin_session.get('http://localhost:5501/proset?proclass_id=1')
            self.assertEqual(re.findall(r'let cur_proclass_desc = `(.*)`;', res.text, re.I)[0], 'desc desc')

            # NOTE: info button
            html = self.get_html('http://localhost:5501/proset?proclass_id=1', admin_session)
            self.assertIsNotNone(html.select_one('button#infoProClass'))

            html = self.get_html('http://localhost:5501/proset', admin_session)
            self.assertIsNone(html.select_one('button#infoProClass'))

            with AccountContext('test1@test', 'test') as user_session:
                res = user_session.get('http://localhost:5501/proset?proclass_id=1')
                self.assertNotEqual(res.text, 'Eacces')

            res = admin_session.post('http://localhost:5501/proset', data={
                'reqtype': 'collect',
                'proclass_id': 1,
            })
            self.assertEqual(res.text, 'S')
            res = admin_session.post('http://localhost:5501/proset', data={
                'reqtype': 'collect',
                'proclass_id': 1,
            })
            self.assertEqual(res.text, 'Eexist')
            res = admin_session.post('http://localhost:5501/proset', data={
                'reqtype': 'listproclass'
            })
            proclass_cata = json.loads(res.text)
            self.assertNotEqual(proclass_cata['collection'], [])
            self.assertEqual(len(proclass_cata['collection']), 1)
            self.assertEqual(proclass_cata['collection'][0]['proclass_id'], 1)

            res = admin_session.post('http://localhost:5501/proset', data={
                'reqtype': 'decollect',
                'proclass_id': 1,
            })
            self.assertEqual(res.text, 'S')
            res = admin_session.post('http://localhost:5501/proset', data={
                'reqtype': 'decollect',
                'proclass_id': 1,
            })
            self.assertEqual(res.text, 'Enoext')
            res = admin_session.post('http://localhost:5501/proset', data={
                'reqtype': 'listproclass'
            })
            proclass_cata = json.loads(res.text)
            self.assertEqual(proclass_cata['collection'], [])
            self.assertEqual(len(proclass_cata['collection']), 0)

            res = admin_session.post('http://localhost:5501/acct/proclass/1', data={
                'reqtype': 'add',
                'name': 'user shared',
                'list': '1',
                'type': ProClassConst.USER_HIDDEN,
                'desc': 'desc'
            })
            self.assertEqual(res.text, '2')
            res = admin_session.post('http://localhost:5501/acct/proclass/1', data={
                'reqtype': 'add',
                'name': 'user shared',
                'list': '1',
                'type': ProClassConst.OFFICIAL_HIDDEN,
                'desc': 'desc'
            })
            self.assertEqual(res.text, 'Eparam')

            res = admin_session.post('http://localhost:5501/proset', data={
                'reqtype': 'listproclass'
            })
            proclass_cata = json.loads(res.text)
            self.assertNotEqual(proclass_cata['own'], [])
            self.assertEqual(len(proclass_cata['own']), 1)
            self.assertEqual(proclass_cata['own'][0]['proclass_id'], 2)

            with AccountContext('test1@test', 'test') as user_session:
                res = user_session.get('http://localhost:5501/proset?proclass_id=2')
                self.assertEqual(res.text, 'Eacces')

                res = user_session.post('http://localhost:5501/proset', data={
                    'reqtype': 'listproclass'
                })
                proclass_cata = json.loads(res.text)
                self.assertEqual(proclass_cata['shared'], [])
                self.assertEqual(len(proclass_cata['shared']), 0)


            res = admin_session.post('http://localhost:5501/proset', data={
                'reqtype': 'collect',
                'proclass_id': 2,
            })
            self.assertEqual(res.text, 'S')
            res = admin_session.post('http://localhost:5501/proset', data={
                'reqtype': 'listproclass'
            })
            proclass_cata = json.loads(res.text)
            self.assertNotEqual(proclass_cata['collection'], [])
            self.assertEqual(len(proclass_cata['collection']), 1)
            self.assertEqual(proclass_cata['collection'][0]['proclass_id'], 2)

            res = admin_session.post('http://localhost:5501/acct/proclass/1', data={
                'reqtype': 'update',
                'proclass_id': 2,
                'name': 'user shared',
                'list': '1',
                'type': ProClassConst.USER_PUBLIC,
                'desc': 'desc desc'
            })
            self.assertEqual(res.text, 'S')
            res = admin_session.post('http://localhost:5501/proset', data={
                'reqtype': 'listproclass'
            })
            proclass_cata = json.loads(res.text)
            self.assertNotEqual(proclass_cata['shared'], [])
            self.assertEqual(len(proclass_cata['shared']), 1)
            self.assertEqual(proclass_cata['shared'][0]['proclass_id'], 2)

            html = self.get_html('http://localhost:5501/acct/proclass/1?page=update&proclassid=2', admin_session)
            self.assertEqual(html.select_one('input#name').attrs.get('value'), 'user shared')
            self.assertEqual(html.select_one('input#list').attrs.get('value'), '1')
            self.assertIsNotNone(html.select('select#type > option')[0].attrs.get('selected'))
            res = admin_session.get('http://localhost:5501/acct/proclass/1?page=update&proclassid=2')
            self.assertEqual(re.findall(r'j_form\.find\("#desc"\)\.val\(`(.*)`\);', res.text, re.I)[0], 'desc desc')

            with AccountContext('test1@test', 'test') as user_session:
                res = user_session.get('http://localhost:5501/proset?proclass_id=2')
                self.assertNotEqual(res.text, 'Eacces')

                res = user_session.post('http://localhost:5501/proset', data={
                    'reqtype': 'listproclass'
                })
                proclass_cata = json.loads(res.text)
                self.assertNotEqual(proclass_cata['shared'], [])
                self.assertEqual(len(proclass_cata['shared']), 1)
                self.assertEqual(proclass_cata['shared'][0]['proclass_id'], 2)

            html = self.get_html('http://localhost:5501/manage/proclass', admin_session)
            trs = html.select('tbody > tr')
            self.assertEqual(len(trs), 1)
            self.assertEqual(trs[0].select_one('th').text, '1')

            html = self.get_html('http://localhost:5501/acct/proclass/1', admin_session)
            trs = html.select('tbody > tr')
            self.assertEqual(len(trs), 1)
            self.assertEqual(trs[0].select_one('th').text, '2')

            # NOTE: permission
            res = admin_session.post('http://localhost:5501/acct/proclass/1', data={
                'reqtype': 'update',
                'proclass_id': 1, # official
                'name': 'user shared',
                'list': '1',
                'type': ProClassConst.USER_PUBLIC,
                'desc': 'desc desc'
            })
            self.assertEqual(res.text, 'Eacces')

            res = admin_session.post('http://localhost:5501/manage/proclass/update', data={
                'reqtype': 'update',
                'proclass_id': 2, # user
                'name': 'test',
                'list': '1, 2',
                'type': ProClassConst.OFFICIAL_PUBLIC,
                'desc': 'desc desc',
            })
            self.assertEqual(res.text, 'Eacces')

            # NOTE: permission
            res = admin_session.post('http://localhost:5501/manage/proclass/update', data={
                'reqtype': 'remove',
                'proclass_id': 2, # user
            })
            self.assertEqual(res.text, 'Eacces')
            res = admin_session.post('http://localhost:5501/acct/proclass/1', data={
                'reqtype': 'remove',
                'proclass_id': 1,
            })
            self.assertEqual(res.text, 'Eacces')

            # NOTE: permission
            res = admin_session.get('http://localhost:5501/manage/proclass/update?proclassid=2')
            self.assertEqual(res.text, 'Eacces')
            res = admin_session.get('http://localhost:5501/acct/proclass/1?page=update&proclassid=1')
            self.assertEqual(res.text, 'Eacces')

            res = admin_session.post('http://localhost:5501/manage/proclass/update', data={
                'reqtype': 'remove',
                'proclass_id': 1,
            })
            self.assertEqual(res.text, 'S')
            res = admin_session.get('http://localhost:5501/proset?proclass_id=1')
            self.assertEqual(res.text, 'Enoext')

            res = admin_session.post('http://localhost:5501/acct/proclass/1', data={
                'reqtype': 'remove',
                'proclass_id': 2,
            })
            self.assertEqual(res.text, 'S')
            res = admin_session.get('http://localhost:5501/proset?proclass_id=2')
            self.assertEqual(res.text, 'Enoext')

            res = admin_session.post('http://localhost:5501/manage/proclass/update', data={
                'reqtype': 'remove',
                'proclass_id': 1,
            })
            self.assertEqual(res.text, 'Enoext')
            res = admin_session.post('http://localhost:5501/acct/proclass/1', data={
                'reqtype': 'remove',
                'proclass_id': 2,
            })
            self.assertEqual(res.text, 'Enoext')

