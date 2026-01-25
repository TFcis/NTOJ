import datetime

from unittest.mock import patch

from .util import AsyncTest, AccountContext
from services.holiday import HolidayService, TimeSlot
import config


async def init():
    with patch('requests.Session.get') as mock_sess_get: # For fetch_gov_data
        with patch('requests.get') as mock_get:          # For fetch_school_data
            mock_sess_get.return_value.status_code = 200
            mock_sess_get.return_value.json.return_value = {
                'result': {
                    'results': [
                        {
                            'date': '20260111',
                            'isholiday': '是',
                            'holidaycategory': '放假之紀念日及節日'
                        },
                        {
                            'date': '20260114',
                            'isholiday': '是',
                            'holidaycategory': '星期六、星期日'
                        },
                        {
                            'date': '20260115',
                            'isholiday': '否',
                            'holidaycategory': 'placeholder'
                        },
                        {
                            'date': '20260117',
                            'isholiday': '是',
                            'holidaycategory': '補假'
                        },
                        {
                            'date': '20260121',
                            'isholiday': '是',
                            'holidaycategory': '星期六、星期日'
                        },
                        {
                            'date': '20260126',
                            'isholiday': '否',
                            'holidaycategory': 'placeholder'
                        },
                        {
                            'date': '20260129',
                            'isholiday': '是',
                            'holidaycategory': '補假'
                        },
                        {
                            'date': '20260212',
                            'isholiday': '是',
                            'holidaycategory': '放假之紀念日及節日'
                        },
                        {
                            'date': '20260215',
                            'isholiday': '是',
                            'holidaycategory': '特定節日'
                        },
                        {
                            '_id': 1800,
                            'date': '20260217',
                            'isholiday': '否',
                            'holidaycategory': 'placeholder'
                        },
                    ]
                }
            }
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                'items': [
                    {'summary': 'not ho1id4y'},
                    {
                        'summary': '這天有放假',
                        'start': {'dateTime': '2026-01-12T00:00:00+08:00'},
                        'end': {'dateTime': '2026-01-13T00:00:00+08:00'}
                    }
                ]
            }
            # The range is not important, because we don't need return value here
            time_slot = TimeSlot(datetime.datetime(2026, 1, 1), datetime.datetime(2026, 1, 1))
            await HolidayService.inst.get_time_slots(time_slot)
            

class HolidayTest(AsyncTest):
    def cmp(self, res: list, expect: list, year: int, month: int):
        # Truncate res to only include the expected month
        start_of_month = datetime.datetime(year, month, 1).replace(tzinfo=config.TIMEZONE)
        end_of_month = (start_of_month + datetime.timedelta(days=31)).replace(day=1)
        self.assertGreater(datetime.datetime.fromisoformat(res[0]['end']), start_of_month - datetime.timedelta(days=7))
        self.assertLess(datetime.datetime.fromisoformat(res[-1]['start']), start_of_month + datetime.timedelta(days=41))
        res = [r for r in res 
               if not (datetime.datetime.fromisoformat(r['end']) < start_of_month or
                          datetime.datetime.fromisoformat(r['start']) >= end_of_month)]
        RED = '#ff5555'
        GREEN = '#50fa7b'
        for r, e in zip(res, expect):
            e_s = datetime.datetime.strptime(e[0], '%Y/%m/%d %H:%M').replace(tzinfo=config.TIMEZONE)
            e_e = datetime.datetime.strptime(e[1], '%Y/%m/%d %H:%M').replace(tzinfo=config.TIMEZONE)
            r_s = datetime.datetime.fromisoformat(r['start'])
            r_e = datetime.datetime.fromisoformat(r['end'])
            self.assertEqual(r_s, e_s)
            self.assertEqual(r_e, e_e)
            self.assertEqual(r['backgroundColor'], GREEN if e[2] else RED, f'{e}')

        self.assertEqual(len(res), len(expect))

    async def main(self):
        await HolidayService.inst.delete_range(TimeSlot(
            datetime.datetime(2026, 1, 1),
            datetime.datetime.now() + datetime.timedelta(days=365),
        ))
        await init()
        expect_1 = [
            ('2026/01/12 00:00', '2026/01/13 00:00', False),
            ('2026/01/13 08:00', '2026/01/13 16:00', True),
            ('2026/01/15 08:00', '2026/01/15 16:00', True),
            ('2026/01/16 08:00', '2026/01/16 16:00', True),
            ('2026/01/17 00:00', '2026/01/17 23:59', False),
            ('2026/01/18 08:00', '2026/01/18 16:00', True),
            ('2026/01/19 08:00', '2026/01/19 16:00', True),
            ('2026/01/20 08:00', '2026/01/20 16:00', True),
            ('2026/01/21 00:00', '2026/02/10 23:59', False),
        ]
        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.get('manage/holiday?action=events&year=2026&month=1').json()
            self.cmp(res['data'], expect_1, 2026, 1)
        expect_2 = [
            ('2026/01/21 00:00', '2026/02/10 23:59', False),
            ('2026/02/11 08:00', '2026/02/11 16:00', True),
            ('2026/02/12 00:00', '2026/02/12 23:59', False),
            ('2026/02/13 08:00', '2026/02/13 16:00', True),
            ('2026/02/14 08:00', '2026/02/14 16:00', True),
            ('2026/02/15 08:00', '2026/02/15 16:00', True),
            ('2026/02/16 08:00', '2026/02/16 16:00', True),
            ('2026/02/17 08:00', '2026/02/17 16:00', True),
        ]
        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.get('manage/holiday?action=events&year=2026&month=2').json()
            self.cmp(res['data'], expect_2, 2026, 2)

        is_holiday = [
            '2026/01/12 12:00', # from school data
            '2026/01/14 12:00', # weekend
            '2026/01/17 12:00', # make-up holiday
            '2026/01/22 12:00', # winter vacation
            '2026/01/26 12:00', # winter vacation
            '2026/02/10 12:00', # winter vacation
            '2026/02/12 12:00', # festival holiday
        ]
        for dt_str in is_holiday:
            dt = datetime.datetime.strptime(dt_str, '%Y/%m/%d %H:%M').replace(tzinfo=config.TIMEZONE)
            self.assertFalse(await HolidayService.inst.is_weekday(dt))

        is_weekday = [
            '2026/01/13 12:00',
            '2026/01/15 12:00',
            '2026/01/20 12:00',
            '2026/02/11 12:00',
            '2026/02/16 12:00',
            '2026/02/17 12:00',
        ]
        for dt_str in is_weekday:
            dt = datetime.datetime.strptime(dt_str, '%Y/%m/%d %H:%M').replace(tzinfo=config.TIMEZONE)
            self.assertTrue(await HolidayService.inst.is_weekday(dt))

        with AccountContext('admin@test', 'testtest') as admin_session:
            # Update
            ## Update & overlap with old slot
            res = admin_session.post('manage/holiday', data={
                'reqtype': 'update',
                'old_start': '2026/01/15 08:00',
                'old_end': '2026/01/15 16:00',
                'new_start': '2026/01/13 13:00',
                'new_end': '2026/01/15 12:00',
                'is_weekday': '1',
            })
            self.assertAPIReturnSuccess(res.text)
            expect_1[1] = ('2026/01/13 08:00', '2026/01/13 13:00', True)
            expect_1[2] = ('2026/01/13 13:00', '2026/01/15 12:00', True)
            res = admin_session.get('manage/holiday?action=events&year=2026&month=1').json()
            self.cmp(res['data'], expect_1, 2026, 1)

            ## Update & change type & shrink slot
            res = admin_session.post('manage/holiday', data={
                'reqtype': 'update',
                'old_start': '2026/01/12 00:00',
                'old_end': '2026/01/13 00:00',
                'new_start': '2026/01/12 12:00',
                'new_end': '2026/01/12 16:00',
                'is_weekday': '1',
            })
            self.assertAPIReturnSuccess(res.text)
            expect_1[0] = ('2026/01/12 12:00', '2026/01/12 16:00', True)
            res = admin_session.get('manage/holiday?action=events&year=2026&month=1').json()
            self.cmp(res['data'], expect_1, 2026, 1)

            ## Update but invalid date format
            res = admin_session.post('manage/holiday', data={
                'reqtype': 'update',
                'old_start': '2026/01/12 12:00',
                'old_end': '2026/01/12 16:00',
                'new_start': '2026-01-12 12:00',
                'new_end': '2026/01/12 16:00',
                'is_weekday': '1',
            })
            self.assertAPIReturnValue(res.text, ('Eparam', 'Invalid date format'))

            ## Update but invalid range (start >= end)
            res = admin_session.post('manage/holiday', data={
                'reqtype': 'update',
                'old_start': '2026/01/12 12:00',
                'old_end': '2026/01/12 16:00',
                'new_start': '2026/01/12 13:00',
                'new_end': '2026/01/12 12:00',
                'is_weekday': '1',
            })
            self.assertAPIReturnValue(res.text, ('Eparam', 'Start time must be before end time'))

            ## Update but old not found
            res = admin_session.post('manage/holiday', data={
                'reqtype': 'update',
                'old_start': '2026/01/12 00:00',
                'old_end': '2026/01/13 00:00',
                'new_start': '2026/01/12 12:00',
                'new_end': '2026/01/12 16:00',
                'is_weekday': '1',
            })
            self.assertAPIReturnValue(res.text, ('Enoext', 'Target weekday range not found'))

            # Delete
            ## Delete existing slot
            res = admin_session.post('manage/holiday', data={
                'reqtype': 'delete',
                'old_start': '2026/01/12 12:00',
                'old_end': '2026/01/12 16:00',
            })
            self.assertAPIReturnSuccess(res.text)
            expect_1.pop(0)
            res = admin_session.get('manage/holiday?action=events&year=2026&month=1').json()
            self.cmp(res['data'], expect_1, 2026, 1)

            ## Delete non-existing slot
            res = admin_session.post('manage/holiday', data={
                'reqtype': 'delete',
                'old_start': '2026/01/12 00:00',
                'old_end': '2026/01/13 00:00',
            })
            self.assertAPIReturnValue(res.text, ('Enoext', 'Target weekday range not found'))

            ## Delete with invalid date format
            res = admin_session.post('manage/holiday', data={
                'reqtype': 'delete',
                'old_start': '2026-01-13 08:00',
                'old_end': '2026/01/13 16:00',
            })
            self.assertAPIReturnValue(res.text, ('Eparam', 'Invalid date format'))

            # Add
            # Add with no overlap
            res = admin_session.post('manage/holiday', data={
                'reqtype': 'add',
                'new_start': '2026/02/17 19:00',
                'new_end': '2026/02/17 21:00',
                'is_weekday': '0',
            })
            self.assertAPIReturnSuccess(res.text)
            expect_2.append(('2026/02/17 19:00', '2026/02/17 21:00', False))
            res = admin_session.get('manage/holiday?action=events&year=2026&month=2').json()
            self.cmp(res['data'], expect_2, 2026, 2)

            ## Add with overlap & total cover
            res = admin_session.post('manage/holiday', data={
                'reqtype': 'add',
                'new_start': '2026/02/17 13:00',
                'new_end': '2026/02/18 04:00',
                'is_weekday': '0',
            })
            self.assertAPIReturnSuccess(res.text)
            expect_2[-2] = ('2026/02/17 08:00', '2026/02/17 13:00', True)
            expect_2[-1] = ('2026/02/17 13:00', '2026/02/18 04:00', False)
            res = admin_session.get('manage/holiday?action=events&year=2026&month=2').json()
            self.cmp(res['data'], expect_2, 2026, 2)

            ## Add and split old slot into two
            res = admin_session.post('manage/holiday', data={
                'reqtype': 'add',
                'new_start': '2026/01/31 08:00',
                'new_end': '2026/01/31 12:00',
                'is_weekday': '1',
            })
            self.assertAPIReturnSuccess(res.text)
            expect_1[-1] = ('2026/01/21 00:00', '2026/01/31 08:00', False)
            expect_1.append(('2026/01/31 08:00', '2026/01/31 12:00', True))
            expect_1.append(('2026/01/31 12:00', '2026/02/10 23:59', False))
            res = admin_session.get('manage/holiday?action=events&year=2026&month=1').json()
            self.cmp(res['data'], expect_1, 2026, 1)
            expect_2[0] = ('2026/01/31 12:00', '2026/02/10 23:59', False)
            res = admin_session.get('manage/holiday?action=events&year=2026&month=2').json()
            self.cmp(res['data'], expect_2, 2026, 2)

            ## Add with invalid date format
            res = admin_session.post('manage/holiday', data={
                'reqtype': 'add',
                'new_start': '2026-02-20 08:00',
                'new_end': '2026/02/20 16:00',
                'is_weekday': '1',
            })
            self.assertAPIReturnValue(res.text, ('Eparam', 'Invalid date format'))

            ## Add with invalid range (start >= end)
            res = admin_session.post('manage/holiday', data={
                'reqtype': 'add',
                'new_start': '2026/02/20 16:00',
                'new_end': '2026/02/20 08:00',
                'is_weekday': '1',
            })
            self.assertAPIReturnValue(res.text, ('Eparam', 'Start time must be before end time'))

        nows = [('2026/01/12 06:00', False),
                ('2026/01/12 11:30', False),

                ('2026/01/13 05:00', False),
                ('2026/01/13 14:10', True),

                ('2026/01/15 10:15', True),
                ('2026/01/15 12:15', False),

                ('2026/01/16 02:15', False),
                ('2026/01/16 12:15', True),
        ]
        for t_str, expect_res in nows:
            now = datetime.datetime.strptime(t_str, '%Y/%m/%d %H:%M').replace(tzinfo=config.TIMEZONE)
            with patch('datetime.datetime') as mock_datetime:
                mock_datetime.now.return_value = now
                res = await HolidayService.inst.is_weekday_now()
                self.assertEqual(res, expect_res, f'now={t_str}')
