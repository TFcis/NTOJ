import re

from tornado.websocket import websocket_connect
from tornado.escape import xhtml_escape

from utils.htmlgen import markdown_escape

from .util import AsyncTest, AccountContext


class BulletinTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            # bulletin
            def _message(msg):
                if msg is None:
                    return

                self.assertEqual(int(msg), 1)

            ws = await websocket_connect('ws://localhost:5501/informsub', on_message_callback=_message)
            res = admin_session.post('manage/bulletin/add', data={
                'reqtype': 'add',
                'title': 'bulletin 1',
                'content': 'bulletin 1',
                'color': 'white',
                'pinned': 'false',
            })
            self.assertEqual(res.text, 'S')
            res = admin_session.post('manage/bulletin/add', data={
                'reqtype': 'add',
                'title': 'bulletin 2 (pinned)',
                'content': 'bulletin 2',
                'color': 'red',
                'pinned': 'true',
            })
            self.assertEqual(res.text, 'S')

            # view info
            html = self.get_html('info', admin_session)
            trs = html.select_one('table > tbody').select('tr')
            self.assertNotEqual(len(trs[0].select('td')[0].select('td > a > font > span')), 0)  # NOTE: span is pin icon
            self.assertTrue(trs[0].select('td')[0].text.strip().find('bulletin 2 (pinned)') != -1)
            self.assertEqual(trs[0].select('td')[2].text.strip(), 'admin')
            self.assertEqual(len(trs[1].select('td')[0].select('td > a > font > span')), 0)
            self.assertEqual(trs[1].select('td')[0].text.strip(), 'bulletin 1')
            self.assertEqual(trs[1].select('td')[2].text.strip(), 'admin')

            # view bulletin
            html = self.get_html('bulletin/2', admin_session)
            self.assertEqual(html.select_one('h2').text.strip(), 'bulletin 2 (pinned)')

            res = admin_session.post('manage/bulletin/update', data={
                'reqtype': 'update',
                'bulletin_id': 2,
                'title': 'bulletin 2 (pinned) updated',
                'content': 'bulletin 2',
                'color': 'red',
                'pinned': 'true',
            })
            self.assertEqual(res.text, 'S')

            html = self.get_html('bulletin/2', admin_session)
            self.assertEqual(html.select_one('h2').text.strip(), 'bulletin 2 (pinned) updated')
            res = admin_session.get('bulletin/2')
            self.assertEqual(re.findall(r'let desc_tex = `(.*)`', res.text, re.I)[0], 'bulletin 2')

            markdown_content ='''<script>alert(1)</script>
```cpp
#include <iostream>
using namespace std;

int main() {
    cout << "escape test\\n" << endl;
    cout << "escape test\\" << endl;
}
```
            '''
            res = admin_session.post('manage/bulletin/update', data={
                'reqtype': 'update',
                'bulletin_id': 2,
                'title': 'bulletin 2 (pinned) updated',
                'content': markdown_content,
                'color': 'red',
                'pinned': 'true',
            })
            self.assertEqual(res.text, 'S')

            html = self.get_html('bulletin/2', admin_session)
            self.assertEqual(html.select_one('h2').text.strip(), 'bulletin 2 (pinned) updated')
            res = admin_session.get('bulletin/2')
            self.assertEqual(re.findall(r'let desc_tex = `(.*)`;', res.text, re.DOTALL)[0].strip(), xhtml_escape(markdown_escape(markdown_content)).strip())

            res = admin_session.post('manage/bulletin/update', data={
                'reqtype': 'remove',
                'bulletin_id': '2',
            })
            self.assertEqual(res.text, 'S')
            res = admin_session.get('bulletin/2')
            self.assertEqual(res.text, 'Enoext')

            ws.close()
