import json
from .util import AsyncTest, AccountContext


class SubmitTest(AsyncTest):
    async def main(self):
        with AccountContext('test1@test', 'test') as user_session:
            # test submit restrict
            res = user_session.post('submit', data={
                'reqtype': 'submit',
                'pro_id': 1,
                'code': '',
                'comp_type': 'g++',
            })
            self.assertAPIReturnValue(res.text, ('Eempty', 'Submitted code should not be empty'))

            res = user_session.post('submit', data={
                'reqtype': 'submit',
                'pro_id': 1,
                'code': open('tests/static_file/code/large.cpp').read(),
                'comp_type': 'g++',
            })
            self.assertAPIReturnValue(res.text, ('Ecodemax', 'Submitted code too long'))

            res = user_session.post('submit', data={
                'reqtype': 'submit',
                'pro_id': 1,
                'code': 'cc',
                'comp_type': 'tobiichi',
            })
            self.assertAPIReturnValue(res.text, ('Ecomp', 'The compiler is not allowed'))

            res = user_session.post('submit', data={
                'reqtype': 'submit',
                'pro_id': 1,
                'code': 'cc',
                'comp_type': 'python3',
            })
            self.assertAPIReturnValue(res.text, ('S', 10))
            html = self.get_html('submit/1', user_session)
            compiler_option = html.select_one('option:checked')
            self.assertIsNotNone(compiler_option)
            self.assertEqual(compiler_option.attrs['value'], 'python3')

            res = user_session.post('submit', data={
                'reqtype': 'submit',
                'pro_id': 1,
                'code': 'cc',
                'comp_type': 'g++',
            })
            res = json.loads(res.text)
            self.assertEqual(res['status'], 'Einternal')

            # NOTE: makefile problem only allow C/C++ language
            html = self.get_html('submit/2', user_session)
            for option in html.select('option'):
                self.assertIn(option.attrs['value'], ['g++', 'clang++', 'gcc', 'clang'])
