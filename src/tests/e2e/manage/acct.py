from services.group import GroupConst
from services.user import UserConst
from tests.e2e.util import AsyncTest, AccountContext


class ManageAcctTest(AsyncTest):
    async def main(self):
        self.signup('admin2', 'admin2@test', 'testtest')
        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('http://localhost:5501/manage/acct/update', {
                'reqtype': 'update',
                'acct_id': 3,
                'acct_type': UserConst.ACCTTYPE_KERNEL,
                'group': GroupConst.KERNEL_GROUP,
            })
            self.assertEqual(res.text, 'S')

        with AccountContext('admin2@test', 'testtest') as admin2_session:
            html = self.get_html('http://localhost:5501/index/', session=admin2_session)
            self.assertIsNotNone(html.select_one('li.manage'))
            self.assertEqual(html.select_one('script#indexjs').attrs.get('acct_id'), '3')
