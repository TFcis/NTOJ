from .util import AsyncTest, AccountContext


class SubmitTest(AsyncTest):
    async def main(self):
        with AccountContext('test1@test', 'test') as user_session:
            # test submit restrict
            res = user_session.post('http://localhost:5501/submit', data={
                'reqtype': 'submit',
                'pro_id': 1,
                'code': '',
                'comp_type': 'g++',
            })
            self.assertEqual(res.text, 'Eempty')

            res = user_session.post('http://localhost:5501/submit', data={
                'reqtype': 'submit',
                'pro_id': 1,
                'code': open('tests/static_file/code/large.cpp').read(),
                'comp_type': 'g++',
            })
            self.assertEqual(res.text, 'Ecodemax')

            res = user_session.post('http://localhost:5501/submit', data={
                'reqtype': 'submit',
                'pro_id': 1,
                'code': 'cc',
                'comp_type': 'tobiichi',
            })
            self.assertEqual(res.text, 'Ecomp')

            res = user_session.post('http://localhost:5501/submit', data={
                'reqtype': 'submit',
                'pro_id': 1,
                'code': 'cc',
                'comp_type': 'g++',
            })
            self.assertEqual(res.text, '10')

            res = user_session.post('http://localhost:5501/submit', data={
                'reqtype': 'submit',
                'pro_id': 1,
                'code': 'cc',
                'comp_type': 'g++',
            })
            self.assertEqual(res.text, 'Einternal30')

            # NOTE: makefile problem only allow C/C++ language
            html = self.get_html('http://localhost:5501/submit/2', user_session)
            for option in html.select('option'):
                self.assertIn(option.attrs['value'], ['g++', 'clang++', 'gcc', 'clang'])
