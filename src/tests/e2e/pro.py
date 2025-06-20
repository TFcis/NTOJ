from services.chal import ChalConst
from .util import AsyncTest, AccountContext


class ProTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            # test pdf download
            res = admin_session.get('pro/2/cont.pdf?download=t')
            self.assertIn('Content-Disposition', res.headers)
            self.assertIn('Content-Type', res.headers)
            self.assertEqual(res.headers.get('Content-Disposition'), 'attachment; filename="pro2.pdf"')

            # update tags
            res = admin_session.post('set-tags', data={
                'pro_id': 1,
                'tags': 'GCD',
            })
            self.assertAPIReturnSuccess(res.text)

            html = self.get_html('pro/1', admin_session)
            self.assertEqual(html.select_one('input#tags').attrs.get('value'), 'GCD')

        with AccountContext('test1@test', 'test') as user_session:
            # test proset tags permission
            html = self.get_html('pro/1', user_session)
            self.assertEqual(html.select_one('input#tags').attrs.get('value'), '')

            html = self.get_html('proset', user_session)
            trs = html.select('#prolist > tbody > tr')
            self.assertEqual(trs[0].select('td')[0].text, '1')
            self.assertEqual(trs[0].select('td')[1].text, ChalConst.STATE_LONG_STR[ChalConst.STATE_RE])  # chal_id: 10
            self.assertEqual(trs[0].select('td')[3].text.strip().replace('\n', ''), '50.00%(1/ 2)')
            self.assertEqual(trs[0].select('td')[4].text.strip().replace('\n', ''), '22.22%(2/9)')
            self.assertEqual(trs[0].select('td')[5].text, '')

        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('set-tags', data={
                'pro_id': 1,
                'tags': '',
            })
            self.assertAPIReturnSuccess(res.text)

            html = self.get_html('pro/1', admin_session)
            self.assertEqual(html.select_one('input#tags').attrs.get('value'), '')

        with AccountContext('test1@test', 'test') as user_session:
            # test topcoder
            html = self.get_html('pro/1', user_session)
            topcoder = html.select_one('#topcoder')
            self.assertIsNotNone(topcoder)
            self.assertEqual(topcoder.select_one('a').get_text().strip(), 'admin') # name
            self.assertEqual(topcoder.select_one('p.card-text').get_text().strip(), '') # motto

            html = self.get_html('pro/3', user_session)
            topcoder = html.select_one('#topcoder')
            self.assertIsNotNone(topcoder)
            self.assertIsNone(topcoder.select_one('a')) # name
            self.assertEqual(topcoder.select_one('h5.card-title').get_text().strip(), 'Waiting for you to become the first accepted.') # name

