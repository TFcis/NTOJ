from .util import AsyncTest, AccountContext


class QuesTest(AsyncTest):
    async def main(self):
        with AccountContext('test1@test', 'test') as user_session:
            res = user_session.post('http://localhost:5501/question', data={
                'reqtype': 'ask',
                'qtext': 'question 1'
            })
            self.assertEqual(res.text, 'S')

            res = user_session.post('http://localhost:5501/question', data={
                'reqtype': 'ask',
                'qtext': ''
            })
            self.assertEqual(res.text, 'Equesempty')

            html = self.get_html('http://localhost:5501/question', user_session)
            self.assertEqual(html.select_one('p').text, 'Wait for Reply')

        with AccountContext('admin@test', 'testtest') as admin_session:
            html = self.get_html('http://localhost:5501/index/', admin_session)
            self.assertEqual(html.select_one('li.ask > a').text.strip().replace('\n', ''), 'get 1 ask')

            html = self.get_html('http://localhost:5501/manage/question', admin_session)
            self.assertEqual(len(html.select('tr')[1:]), 1)
            self.assertEqual(html.select('tr')[1:][0].select_one('td').text, '2')

            html = self.get_html('http://localhost:5501/manage/question/reply?qacct=2', admin_session)
            self.assertEqual(html.select('tr')[1:][0].select_one('td').text, 'question 1')

            res = admin_session.post('http://localhost:5501/manage/question/reply', data={
                'reqtype': 'rpl',
                'qacct_id': 2,
                'index': 0,
                'rtext': 'reply question 1'
            })
            self.assertEqual(res.text, 'S')

            html = self.get_html('http://localhost:5501/manage/question/reply?qacct=2', admin_session)
            self.assertEqual(html.select('tr')[1:][0].select_one('td > textarea').text.strip(), 'reply question 1')

        with AccountContext('test1@test', 'test') as user_session:
            html = self.get_html('http://localhost:5501/index/', user_session)
            self.assertIsNotNone(html.select_one('a[style="color: #e74c3c;"]'))

            html = self.get_html('http://localhost:5501/question', user_session)
            self.assertEqual(html.select('h5')[1].text.strip(), 'reply question 1')

            res = user_session.post('http://localhost:5501/question', data={
                'reqtype': 'rm_ques',
                'index': 0
            })
            self.assertEqual(res.text, 'S')

            html = self.get_html('http://localhost:5501/question', user_session)
            self.assertIsNone(html.select_one('div#abc'))

        with AccountContext('admin@test', 'testtest') as admin_session:
            html = self.get_html('http://localhost:5501/index/', admin_session)
            self.assertIsNone(html.select_one('li.ask > a'))

            html = self.get_html('http://localhost:5501/manage/question', admin_session)
            self.assertEqual(len(html.select('tr')[1:]), 0)
