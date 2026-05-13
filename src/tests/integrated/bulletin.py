import asyncio
import json

from tornado.websocket import websocket_connect

from services.bulletin import BulletinService

from .util import AsyncTest, AccountContext


class BulletinTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            # bulletin
            received_messages = []
            def _message(msg):
                if msg is None:
                    return
                data = json.loads(msg)
                if data.get('type') == 'bulletinsub':
                    received_messages.append(int(data['data']))

            ws = await websocket_connect('ws://localhost:5501/be/ws', on_message_callback=_message)
            await ws.write_message(json.dumps({'type': 'register', 'data': 'bulletinsub'}))
            res = admin_session.post('manage/bulletin/add', data={
                'reqtype': 'add',
                'title': 'bulletin 1',
                'content': 'bulletin 1',
                'color': 'white',
                'pinned': 'false',
            })
            self.assertAPIReturnSuccess(res.text)
            res = admin_session.post('manage/bulletin/add', data={
                'reqtype': 'add',
                'title': 'bulletin 2 (pinned)',
                'content': 'bulletin 2',
                'color': 'red',
                'pinned': 'true',
            })
            self.assertAPIReturnSuccess(res.text)

            err, bulletin_list = await BulletinService.inst.list_bulletin()
            self.assertIsNone(err)
            self.assertEqual(len(bulletin_list), 2)
            self.assertEqual(bulletin_list[0]['title'], 'bulletin 1')
            self.assertFalse(bulletin_list[0]['pinned'])
            self.assertEqual(bulletin_list[0]['color'], 'white')
            self.assertEqual(bulletin_list[0]['name'], 'admin')
            self.assertEqual(bulletin_list[0]['acct_id'], 1)
            self.assertEqual(bulletin_list[1]['title'], 'bulletin 2 (pinned)')
            self.assertTrue(bulletin_list[1]['pinned'])
            self.assertEqual(bulletin_list[1]['color'], 'red')

            # Wait up to 2 seconds for a message to be received
            for _ in range(20):
                if received_messages:
                    break
                await asyncio.sleep(0.1)
            self.assertGreater(len(received_messages), 0)
            ws.close()
            self.assertEqual(bulletin_list[1]['name'], 'admin')
            self.assertEqual(bulletin_list[1]['acct_id'], 1)

            err, bulletin = await BulletinService.inst.get_bulletin(1)
            self.assertIsNone(err)
            assert bulletin
            self.assertEqual(bulletin['title'], 'bulletin 1')
            self.assertEqual(bulletin['content'], 'bulletin 1')
            self.assertEqual(bulletin['color'], 'white')
            self.assertFalse(bulletin['pinned'])
            self.assertEqual(bulletin['name'], 'admin')
            self.assertEqual(bulletin['acct_id'], 1)
            self.assertIsNotNone(bulletin['timestamp'])

            err, bulletin = await BulletinService.inst.get_bulletin(2)
            self.assertIsNone(err)
            assert bulletin
            self.assertEqual(bulletin['title'], 'bulletin 2 (pinned)')
            self.assertEqual(bulletin['content'], 'bulletin 2')
            self.assertEqual(bulletin['color'], 'red')
            self.assertTrue(bulletin['pinned'])
            self.assertEqual(bulletin['name'], 'admin')
            self.assertEqual(bulletin['acct_id'], 1)
            self.assertIsNotNone(bulletin['timestamp'])

            self.assertTable(
                'manage/bulletin/add',
                {
                    'reqtype': 'add',
                    'title': 'title',
                    'content': 'content',
                    'color': 'white',
                    'pinned': 'true'
                },
                [
                    {'title': '', 'equal_value': ('Eparam', 'Title too short')},
                    {'title': 'title' * 10000, 'equal_value': ('Eparam', 'Title too long')},
                    {'content': 'content' * 10000, 'equal_value': ('Eparam', 'Content too long')},
                ],
                admin_session
            )

            res = admin_session.post('manage/bulletin/update', data={
                'reqtype': 'update',
                'bulletin_id': 2,
                'title': 'bulletin 2 (pinned) updated',
                'content': 'bulletin 2',
                'color': 'red',
                'pinned': 'true',
            })
            self.assertAPIReturnSuccess(res.text)
            err, bulletin = await BulletinService.inst.get_bulletin(2)
            self.assertIsNone(err)
            assert bulletin
            self.assertEqual(bulletin['title'], 'bulletin 2 (pinned) updated')

            res = admin_session.post('manage/bulletin/update', data={
                'reqtype': 'remove',
                'bulletin_id': '2',
            })
            self.assertAPIReturnSuccess(res.text)
            err, bulletin = await BulletinService.inst.get_bulletin(2)
            self.assertEqual(err, ('Enoext', 'Bulletin not found'))
