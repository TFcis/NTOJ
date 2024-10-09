from services.chal import ChalConst
from tests.e2e.util import AsyncTest, AccountContext


# FIXME: chal cnt need recalculate
class ProsetTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            html = self.get_html('http://localhost:5501/proset', admin_session)
            trs = html.select('tr')[1:]
            self.assertEqual(trs[0].select('td')[0].text, '1')
            self.assertEqual(trs[0].select('td')[1].text, ChalConst.STATE_LONG_STR[ChalConst.STATE_AC])
            self.assertEqual(trs[0].select('td')[2].text.strip().replace('\n', ''), 'GCD')
            self.assertEqual(trs[0].select('td')[3].text.strip().replace('\n', ''), '50.00%(1/ 2)')
            self.assertEqual(trs[0].select('td')[4].text.strip().replace('\n', ''), '22.22%(2/9)')
            self.assertEqual(trs[0].select('td')[5].text, '')

            self.assertEqual(trs[1].select('td')[0].text, '2')
            self.assertEqual(trs[1].select('td')[1].text, ChalConst.STATE_LONG_STR[ChalConst.STATE_AC])
            self.assertEqual(trs[1].select('td')[2].text.strip().replace('\n', ''), '猜數字')
            self.assertEqual(trs[1].select('td')[3].text.strip().replace('\n', ''), '100.00%(1/ 1)')
            self.assertEqual(trs[1].select('td')[4].text.strip().replace('\n', ''), '100.00%(1/1)')
            self.assertEqual(trs[1].select('td')[5].text, '')

            self.assertEqual(trs[2].select('td')[0].text, '3')
            self.assertEqual(trs[2].select('td')[1].text, 'Todo')
            self.assertEqual(trs[2].select('td')[2].text.strip().replace('\n', ''), 'Move')
            self.assertEqual(trs[2].select('td')[3].text.strip().replace('\n', ''), '0.00%(0/ 0)')
            self.assertEqual(trs[2].select('td')[4].text.strip().replace('\n', ''), '0.00%(0/0)')
            self.assertEqual(trs[2].select('td')[5].text, '')

            html = self.get_html('http://localhost:5501/proset?show=onlyac', admin_session)
            self.assertEqual(len(html.select('tr')), 1 + 2)

            html = self.get_html('http://localhost:5501/proset?show=notac', admin_session)
            self.assertEqual(len(html.select('tr')), 1 + 1)

            html = self.get_html('http://localhost:5501/proset?order=chal&reverse=True', admin_session)
            trs = html.select('tr')[1:]
            self.assertEqual(trs[0].select('td')[0].text, '2')
            self.assertEqual(trs[0].select('td')[1].text, ChalConst.STATE_LONG_STR[ChalConst.STATE_AC])
            self.assertEqual(trs[0].select('td')[2].text.strip().replace('\n', ''), '猜數字')
            self.assertEqual(trs[0].select('td')[3].text.strip().replace('\n', ''), '100.00%(1/ 1)')
            self.assertEqual(trs[0].select('td')[4].text.strip().replace('\n', ''), '100.00%(1/1)')
            self.assertEqual(trs[0].select('td')[5].text, '')

            self.assertEqual(trs[1].select('td')[0].text, '1')
            self.assertEqual(trs[1].select('td')[1].text, ChalConst.STATE_LONG_STR[ChalConst.STATE_AC])
            self.assertEqual(trs[1].select('td')[2].text.strip().replace('\n', ''), 'GCD')
            self.assertEqual(trs[1].select('td')[3].text.strip().replace('\n', ''), '50.00%(1/ 2)')
            self.assertEqual(trs[1].select('td')[4].text.strip().replace('\n', ''), '22.22%(2/9)')
            self.assertEqual(trs[1].select('td')[5].text, '')

            self.assertEqual(trs[2].select('td')[0].text, '3')
            self.assertEqual(trs[2].select('td')[1].text, 'Todo')
            self.assertEqual(trs[2].select('td')[2].text.strip().replace('\n', ''), 'Move')
            self.assertEqual(trs[2].select('td')[3].text.strip().replace('\n', ''), '0.00%(0/ 0)')
            self.assertEqual(trs[2].select('td')[4].text.strip().replace('\n', ''), '0.00%(0/0)')
            self.assertEqual(trs[2].select('td')[5].text, '')
