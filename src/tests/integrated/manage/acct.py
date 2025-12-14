from services.user import UserService, UserConst
from tests.integrated.util import AsyncTest, AccountContext


class ManageAcctTest(AsyncTest):
    async def main(self):
        self.signup('admin2', 'admin2@test', 'testtest')
        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('manage/acct/update', {
                'reqtype': 'update',
                'acct_id': 3,
                'acct_type': UserConst.ACCTTYPE_KERNEL,
                'specific_ip': '192.168.11.10',
            })
            self.assertAPIReturnSuccess(res.text)

            err, acct = await UserService.inst.info_acct(3)
            self.assertIsNone(err)
            self.assertEqual(acct.acct_type, UserConst.ACCTTYPE_KERNEL)
            self.assertEqual(acct.specific_ip, '192.168.11.10')