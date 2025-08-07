import json
from .util import AsyncTest, AccountContext
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

            res = user_session.post('submit', data={
                'reqtype': 'submit',
                'pro_id': 1,
                'code': open('tests/static_file/code/large.cpp').read(),
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
            html = self.get_html('submit/1', user_session)
            compiler_option = html.select_one('option:checked')
            self.assertIsNotNone(compiler_option)
            self.assertEqual(int(compiler_option.attrs['value']), Compiler.PYTHON3)

            res = user_session.post('submit', data={
                'reqtype': 'submit',
                'pro_id': 1,
                'code': 'cc',
                'compiler_type': Compiler.GPP,
            })
            res = json.loads(res.text)
            self.assertEqual(res['status'], 'Einternal')
