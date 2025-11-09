from .util import AsyncTest, AccountContext
from services.pro import ProService, ProConst


class ProTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            # test pdf download
            # TODO:
            # res = admin_session.get('pro/2/cont.pdf?download=t')
            # self.assertIn('Content-Disposition', res.headers)
            # self.assertIn('Content-Type', res.headers)
            # self.assertEqual(res.headers.get('Content-Disposition'), 'attachment; filename="pro2.pdf"')

            # update tags
            res = admin_session.post('set-tags', data={
                'pro_id': 1,
                'tags': 'GCD',
            })
            self.assertAPIReturnSuccess(res.text)
            err, pro = await ProService.inst.get_pro(1, allow_statuses=ProConst.PRO_STATUS_NORMAL_USER)
            self.assertIsNone(err)
            self.assertEqual(pro.tags, 'GCD')

            res = admin_session.post('set-tags', data={
                'pro_id': 1,
                'tags': '',
            })
            self.assertAPIReturnSuccess(res.text)
            err, pro = await ProService.inst.get_pro(1, allow_statuses=ProConst.PRO_STATUS_NORMAL_USER)
            self.assertIsNone(err)
            self.assertEqual(pro.tags, '')

            # NOTE: test set-tags permission
            with AccountContext('test1@test', 'test') as user_session:
                res = user_session.post('set-tags', data={
                    'pro_id': 1,
                    'tags': 'eazy',
                })
                self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))
                err, pro = await ProService.inst.get_pro(1, allow_statuses=ProConst.PRO_STATUS_NORMAL_USER)
                self.assertIsNone(err)
                self.assertNotEqual(pro.tags, 'eazy')
