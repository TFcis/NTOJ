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
            pass
