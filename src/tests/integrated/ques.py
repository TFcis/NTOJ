from services.ques import QuestionService
from .util import AsyncTest, AccountContext


class QuesTest(AsyncTest):
    async def main(self):
        with AccountContext('test1@test', 'test') as user_session:
            res = user_session.post('question', data={
                'reqtype': 'ask',
                'qtext': 'question 1'
            })
            self.assertAPIReturnSuccess(res.text)
            _, queslist = await QuestionService.inst.get_queslist(2)
            self.assertEqual(len(queslist), 1)
            self.assertEqual(queslist[0]['Q'], 'question 1')

            res = user_session.post('question', data={
                'reqtype': 'ask',
                'qtext': ''
            })
            self.assertAPIReturnValue(res.text, ('Eparam', 'Question too short'))

            res = user_session.post('question', data={
                'reqtype': 'ask',
                'qtext': 'a' * 5000
            })
            self.assertAPIReturnValue(res.text, ('Eparam', 'Question too long'))

            _, asklist, askcnt = await QuestionService.inst.get_asklist()
            self.assertEqual(asklist[2], True) # NOTE: acct_id
            self.assertEqual(askcnt, 1)

        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('manage/question/reply', data={
                'reqtype': 'rpl',
                'qacct_id': 2,
                'index': 0,
                'rtext': 'reply question 1'
            })
            self.assertAPIReturnSuccess(res.text)
            _, queslist = await QuestionService.inst.get_queslist(2)
            self.assertEqual(queslist[0]['Q'], 'question 1')
            self.assertEqual(queslist[0]['A'], 'reply question 1')
            _, asklist, askcnt = await QuestionService.inst.get_asklist()
            self.assertEqual(asklist[2], False) # NOTE: acct_id
            self.assertEqual(askcnt, 0)

            res = admin_session.post('manage/question/reply', data={
                'reqtype': 'rpl',
                'qacct_id': 2,
                'index': 0,
                'rtext': ''
            })
            self.assertAPIReturnValue(res.text, ('Eparam', 'Reply too short'))

            res = admin_session.post('manage/question/reply', data={
                'reqtype': 'rpl',
                'qacct_id': 2,
                'index': 0,
                'rtext': 'a' * 5000
            })
            self.assertAPIReturnValue(res.text, ('Eparam', 'Reply too long'))

        with AccountContext('test1@test', 'test') as user_session:
            have_reply = await QuestionService.inst.have_reply(2)
            self.assertTrue(have_reply)

            res = user_session.post('question', data={
                'reqtype': 'rm_ques',
                'index': 0
            })
            self.assertAPIReturnSuccess(res.text)
            _, queslist = await QuestionService.inst.get_queslist(2)
            self.assertEqual(len(queslist), 0)
