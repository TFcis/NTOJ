import json
from .util import AsyncTest, AccountContext
from services.user import UserService
from services.chal import Compiler


class SubmitTest(AsyncTest):
    async def main(self):
        with AccountContext('test1@test', 'test') as user_session:
            # test submit restrict
            res = user_session.post('submit', data={
                'reqtype': 'submit',
                'pro_id': 1,
                'code': '',
                'compiler_type': Compiler.GPP,
            })
            self.assertAPIReturnValue(res.text, ('Eempty', 'Submitted code should not be empty'))

            with open('tests/static_file/code/large.cpp') as f:
                res = user_session.post('submit', data={
                    'reqtype': 'submit',
                    'pro_id': 1,
                    'code': f.read(),
                    'compiler_type': Compiler.GPP,
                })
                self.assertAPIReturnValue(res.text, ('Ecodemax', 'Submitted code too long'))

            res = user_session.post('submit', data={
                'reqtype': 'submit',
                'pro_id': 1,
                'code': 'cc',
                'compiler_type': 'tobiichi',
            })
            self.assertAPIReturnValue(res.text, ('Ecomp', 'The compiler is not allowed'))

            res = user_session.post('submit', data={
                'reqtype': 'submit',
                'pro_id': 1,
                'code': 'cc',
                'compiler_type': Compiler.PYTHON3,
            })
            self.assertAPIReturnValue(res.text, ('S', 10))
            err, acct = await UserService.inst.info_acct(2)
            self.assertIsNone(err)
            self.assertEqual(acct.last_compiler, Compiler.PYTHON3)

            res = user_session.post('submit', data={
                'reqtype': 'submit',
                'pro_id': 1,
                'code': 'cc',
                'compiler_type': Compiler.GPP,
            })
            res = json.loads(res.text)
            self.assertEqual(res['status'], 'Einternal')
