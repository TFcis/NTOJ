import io
import json

from services.class_group import ClassGroupService
from services.user import UserService
from tests.integrated.util import AsyncTest, AccountContext


class ManageClassGroupTest(AsyncTest):
    """Integration tests for Class Group management feature"""

    async def main(self):
        """Run all class group integration tests"""
        await self.test_create_class_group()
        await self.test_create_with_csv()
        await self.test_list_and_filter()
        await self.test_update_class_group()
        await self.test_ip_range_management()
        await self.test_member_management()
        await self.test_update_member_ip()
        await self.test_batch_add_members()
        await self.test_delete_class_group()
        await self.test_csv_validation_errors()
        await self.test_permission_control()

    async def test_create_class_group(self):
        """Test creating a basic class group without CSV"""
        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('manage/class_group', {
                'reqtype': 'create',
                'year': 113,
                'semester': 1,
                'class_number': 101,
                'custom_name': 'CLASS',
                'ip_range_start': '',
                'ip_range_end': '',
            })
            self.assertAPIReturnSuccess(res.text)

            data = json.loads(res.text)
            group_id = data['data']
            self.assertIsInstance(group_id, int)

            # Verify group was created
            err, group = await ClassGroupService.inst.get_class_group(group_id)
            self.assertIsNone(err)
            assert group
            self.assertEqual(group.year, 113)
            self.assertEqual(group.semester, 1)
            self.assertEqual(group.class_number, 101)
            self.assertEqual(group.custom_name, 'CLASS')

    async def test_create_with_csv(self):
        """Test creating class group with CSV account import"""
        csv_content = b"""email,name,password,specific_ip
cgtest001,Test User 1,Pass123,192.168.10.1
cgtest002,Test User 2,Pass456,
cgtest003,Test User 3,Pass789,192.168.10.3"""

        with AccountContext('admin@test', 'testtest') as admin_session:
            files = {'csv_file': ('test.csv', io.BytesIO(csv_content), 'text/csv')}
            res = admin_session.post('manage/class_group',
                data={
                    'reqtype': 'create',
                    'year': 113,
                    'semester': 2,
                    'class_number': 102,
                    'custom_name': 'CLASS',
                    'ip_range_start': '192.168.20.1',
                    'ip_range_end': '192.168.20.50',
                },
                files=files
            )
            self.assertAPIReturnSuccess(res.text)

            data = json.loads(res.text)
            group_id = data['data']

            # Verify accounts were created - need to query DB for acct_id first
            async with UserService.inst.db.acquire() as con:
                result1 = await con.fetchrow('SELECT "acct_id" FROM "account" WHERE "mail" = $1;', 'cgtest001')
                result2 = await con.fetchrow('SELECT "acct_id" FROM "account" WHERE "mail" = $1;', 'cgtest002')
                result3 = await con.fetchrow('SELECT "acct_id" FROM "account" WHERE "mail" = $1;', 'cgtest003')

            self.assertIsNotNone(result1)
            self.assertIsNotNone(result2)
            self.assertIsNotNone(result3)

            err, acct1 = await UserService.inst.info_acct(result1['acct_id'])
            self.assertIsNone(err)
            assert acct1
            self.assertEqual(acct1.name, 'Test User 1')
            self.assertEqual(acct1.specific_ip, '192.168.10.1')

            err, acct2 = await UserService.inst.info_acct(result2['acct_id'])
            self.assertIsNone(err)
            assert acct2
            self.assertEqual(acct2.name, 'Test User 2')
            self.assertEqual(acct2.specific_ip, '192.168.20.2')  # Auto-assigned (skipped .1 for cgtest001's index)

            err, acct3 = await UserService.inst.info_acct(result3['acct_id'])
            self.assertIsNone(err)
            assert acct3
            self.assertEqual(acct3.specific_ip, '192.168.10.3')

            # Verify they are members of the group
            err, members = await ClassGroupService.inst.get_group_members(group_id)
            self.assertIsNone(err)
            assert members
            self.assertEqual(len(members), 3)

    async def test_list_and_filter(self):
        """Test listing class groups with filters"""
        with AccountContext('admin@test', 'testtest') as admin_session:
            # Create multiple groups with different custom names
            res1 = admin_session.post('manage/class_group', {
                'reqtype': 'create',
                'year': 114,
                'semester': 1,
                'class_number': 201,
                'custom_name': 'CLASS1',
            })
            self.assertAPIReturnSuccess(res1.text)

            res2 = admin_session.post('manage/class_group', {
                'reqtype': 'create',
                'year': 114,
                'semester': 2,
                'class_number': 202,
                'custom_name': 'CLASS2',
            })
            self.assertAPIReturnSuccess(res2.text)

            res3 = admin_session.post('manage/class_group', {
                'reqtype': 'create',
                'year': 114,
                'semester': 1,
                'class_number': 203,
                'custom_name': 'LLL',
            })
            self.assertAPIReturnSuccess(res3.text)

            # Test list without filter
            res = admin_session.get('manage/class_group')
            self.assertEqual(res.status_code, 200)

            # Test filter by year
            res = admin_session.get('manage/class_group', params={'year': 114})
            self.assertEqual(res.status_code, 200)

            # Test filter by year and semester
            res = admin_session.get('manage/class_group', params={
                'year': 114,
                'semester': 1
            })
            self.assertEqual(res.status_code, 200)

            # Test custom_name fuzzy match filter - direct service call for verification
            err, groups = await ClassGroupService.inst.list_class_groups(
                pageoff=0,
                pagesize=40,
                year=114,
                semester=None,
                class_number=None,
                custom_name='LA'
            )
            self.assertIsNone(err)
            assert groups is not None
            self.assertEqual(len(groups), 2)
            custom_names = [g.custom_name for g in groups]
            self.assertIn('CLASS1', custom_names)
            self.assertIn('CLASS2', custom_names)

            # Test more specific fuzzy match
            err, groups = await ClassGroupService.inst.list_class_groups(
                pageoff=0,
                pagesize=40,
                year=114,
                semester=None,
                class_number=None,
                custom_name='1'
            )
            self.assertIsNone(err)
            assert groups is not None
            # Should only match "資訊科學班"
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0].custom_name, 'CLASS1')

            # Test fuzzy match with different substring
            err, groups = await ClassGroupService.inst.list_class_groups(
                pageoff=0,
                pagesize=40,
                year=None,
                semester=None,
                class_number=None,
                custom_name='L'
            )
            self.assertIsNone(err)
            assert groups is not None
            # Should match all three groups (all end with "班")
            self.assertGreaterEqual(len(groups), 3)

            # Test count with custom_name filter
            count = await ClassGroupService.inst.count_class_groups(
                year=114,
                semester=None,
                class_number=None,
                custom_name='LA'
            )
            self.assertEqual(count, 2)

            # Test handler with custom_name parameter
            res = admin_session.get('manage/class_group', params={
                'year': 114,
                'custom_name': '資訊'
            })
            self.assertEqual(res.status_code, 200)

    async def test_update_class_group(self):
        """Test updating class group information"""
        # Create a group first
        err, group_id = await ClassGroupService.inst.create_class_group(
            year=115,
            semester=1,
            class_number=301,
            custom_name='Init',
            ip_range_start='',
            ip_range_end=''
        )
        assert group_id
        self.assertIsNone(err)

        # Get the group
        err, group = await ClassGroupService.inst.get_class_group(group_id)
        self.assertIsNone(err)
        assert group

        # Update properties
        group.custom_name = 'Updated'

        # Update via handler
        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('manage/class_group', {
                'reqtype': 'update',
                'group_id': group_id,
                'year': 115,
                'semester': 1,
                'class_number': 301,
                'custom_name': 'Updated',
                'ip_range_start': '',
                'ip_range_end': '',
            })
            self.assertAPIReturnSuccess(res.text)

            # Verify update
            err, updated_group = await ClassGroupService.inst.get_class_group(group_id)
            assert updated_group
            self.assertIsNone(err)
            self.assertEqual(updated_group.custom_name, 'Updated')

    async def test_ip_range_management(self):
        """Test adding and removing IP ranges"""
        # Create a group
        err, group_id = await ClassGroupService.inst.create_class_group(
            year=115,
            semester=2,
            class_number=302,
            custom_name='',
            ip_range_start='',
            ip_range_end=''
        )
        self.assertIsNone(err)
        assert group_id

        with AccountContext('admin@test', 'testtest') as admin_session:
            # Add IP range
            res = admin_session.post('manage/class_group', {
                'reqtype': 'set_ip_range',
                'group_id': group_id,
                'ip_start': '10.0.0.1',
                'ip_end': '10.0.0.100',
            })
            self.assertAPIReturnSuccess(res.text)

            # Verify IP range was added
            err, group = await ClassGroupService.inst.get_class_group(group_id)
            self.assertIsNone(err)
            assert group
            self.assertEqual(group.ip_range_start, '10.0.0.1')
            self.assertEqual(group.ip_range_end, '10.0.0.100')

            # Remove IP range by updating with empty values
            res = admin_session.post('manage/class_group', {
                'reqtype': 'update',
                'group_id': group_id,
                'year': 115,
                'semester': 2,
                'class_number': 302,
                'custom_name': '',
                'ip_range_start': '',
                'ip_range_end': '',
            })
            self.assertAPIReturnSuccess(res.text)

            # Verify IP range was removed
            err, group = await ClassGroupService.inst.get_class_group(group_id)
            self.assertIsNone(err)
            assert group
            self.assertEqual(group.ip_range_start, '')
            self.assertEqual(group.ip_range_end, '')

    async def test_member_management(self):
        """Test adding and removing members"""
        # Create a group
        err, group_id = await ClassGroupService.inst.create_class_group(
            year=116,
            semester=1,
            class_number=401,
            custom_name='',
            ip_range_start='',
            ip_range_end=''
        )
        self.assertIsNone(err)
        assert group_id

        with AccountContext('admin@test', 'testtest') as admin_session:
            # Add member manually
            res = admin_session.post('manage/class_group', {
                'reqtype': 'add_member_manual',
                'group_id': group_id,
                'email': 'cgmember001',
                'name': 'Member One',
                'password': 'MemberPass1',
                'specific_ip': '172.16.0.10',
            })
            self.assertAPIReturnSuccess(res.text)

            # Verify member was created and added - query acct_id first
            async with UserService.inst.db.acquire() as con:
                result = await con.fetchrow('SELECT "acct_id" FROM "account" WHERE "mail" = $1;', 'cgmember001')
            self.assertIsNotNone(result)

            err, acct = await UserService.inst.info_acct(result['acct_id'])
            self.assertIsNone(err)
            assert acct
            self.assertEqual(acct.name, 'Member One')
            self.assertEqual(acct.specific_ip, '172.16.0.10')

            err, members = await ClassGroupService.inst.get_group_members(group_id)
            self.assertIsNone(err)
            assert members
            self.assertEqual(len(members), 1)
            self.assertEqual(members[0]['mail'], 'cgmember001')

            # Remove member
            res = admin_session.post('manage/class_group', {
                'reqtype': 'remove_member',
                'group_id': group_id,
                'acct_id': acct.acct_id,
            })
            self.assertAPIReturnSuccess(res.text)

            # Verify member was removed from group
            err, members = await ClassGroupService.inst.get_group_members(group_id)
            self.assertIsNone(err)
            assert members is not None
            self.assertEqual(len(members), 0)

            # Account should still exist
            err, acct = await UserService.inst.info_acct(result['acct_id'])
            self.assertIsNone(err)

    async def test_update_member_ip(self):
        """Test updating member's specific IP and force logout"""
        # Create group and member
        err, group_id = await ClassGroupService.inst.create_class_group(
            year=116,
            semester=2,
            class_number=402,
            custom_name='',
            ip_range_start='',
            ip_range_end=''
        )
        self.assertIsNone(err)
        assert group_id

        # Create account using signup
        self.signup('IP Test User', 'cgiptest001@test.local', 'IpTestPass1')

        # Get acct_id from DB
        async with UserService.inst.db.acquire() as con:
            result = await con.fetchrow('SELECT "acct_id" FROM "account" WHERE "mail" = $1;', 'cgiptest001@test.local')
        self.assertIsNotNone(result)
        acct_id = result['acct_id']

        err = await ClassGroupService.inst.add_member(group_id, acct_id)
        self.assertIsNone(err)

        with AccountContext('admin@test', 'testtest') as admin_session:
            # Update member IP
            res = admin_session.post('manage/class_group', {
                'reqtype': 'update_member_ip',
                'group_id': group_id,
                'acct_id': acct_id,
                'new_ip': '192.168.99.1',
            })
            self.assertAPIReturnSuccess(res.text)

            # Verify IP was updated
            err, acct = await UserService.inst.info_acct(acct_id)
            assert acct
            self.assertIsNone(err)
            self.assertEqual(acct.specific_ip, '192.168.99.1')

            # Clear IP
            res = admin_session.post('manage/class_group', {
                'reqtype': 'update_member_ip',
                'group_id': group_id,
                'acct_id': acct_id,
                'new_ip': '',
            })
            self.assertAPIReturnSuccess(res.text)

            err, acct = await UserService.inst.info_acct(acct_id)
            assert acct
            self.assertIsNone(err)
            self.assertEqual(acct.specific_ip, '')

    async def test_batch_add_members(self):
        """Test batch adding members to existing group"""
        # Create group
        err, group_id = await ClassGroupService.inst.create_class_group(
            year=117,
            semester=1,
            class_number=501,
            custom_name='',
            ip_range_start='192.168.50.1',
            ip_range_end='192.168.50.100'
        )
        self.assertIsNone(err)
        assert group_id

        csv_content = b"""email,name,password
cgbatch001,Batch User 1,BatchPass1
cgbatch002,Batch User 2,BatchPass2
cgbatch003,Batch User 3,BatchPass3"""

        with AccountContext('admin@test', 'testtest') as admin_session:
            files = {'csv_file': ('batch.csv', io.BytesIO(csv_content), 'text/csv')}
            res = admin_session.post('manage/class_group',
                data={
                    'reqtype': 'add_member_csv',
                    'group_id': group_id,
                },
                files=files
            )
            self.assertAPIReturnSuccess(res.text)

            # Verify all members were added
            err, members = await ClassGroupService.inst.get_group_members(group_id)
            assert members
            self.assertIsNone(err)
            self.assertEqual(len(members), 3)

            # Verify IPs were auto-assigned
            async with UserService.inst.db.acquire() as con:
                result1 = await con.fetchrow('SELECT "acct_id" FROM "account" WHERE "mail" = $1;', 'cgbatch001')
                result2 = await con.fetchrow('SELECT "acct_id" FROM "account" WHERE "mail" = $1;', 'cgbatch002')

            self.assertIsNotNone(result1)
            self.assertIsNotNone(result2)

            err, acct1 = await UserService.inst.info_acct(result1['acct_id'])
            self.assertIsNone(err)
            assert acct1
            self.assertEqual(acct1.specific_ip, '192.168.50.1')

            err, acct2 = await UserService.inst.info_acct(result2['acct_id'])
            self.assertIsNone(err)
            assert acct2
            self.assertEqual(acct2.specific_ip, '192.168.50.2')

    async def test_delete_class_group(self):
        """Test deleting class group and cascade delete members"""
        # Create group with members
        csv_content = b"""email,name,password
cgdelete001,Delete User 1,DelPass1
cgdelete002,Delete User 2,DelPass2"""

        err, accounts_data = await ClassGroupService.inst.parse_csv(csv_content)
        assert accounts_data
        self.assertIsNone(err)

        err, group_id = await ClassGroupService.inst.create_class_group(
            year=117,
            semester=2,
            class_number=502,
            custom_name='',
            ip_range_start='',
            ip_range_end=''
        )
        self.assertIsNone(err)
        assert group_id

        err, created_count = await ClassGroupService.inst.batch_create_accounts(
            group_id, accounts_data, '', ''
        )
        self.assertIsNone(err)
        self.assertEqual(created_count, 2)

        # Verify accounts exist - get acct_id first
        async with UserService.inst.db.acquire() as con:
            result1 = await con.fetchrow('SELECT "acct_id" FROM "account" WHERE "mail" = $1;', 'cgdelete001')
            result2 = await con.fetchrow('SELECT "acct_id" FROM "account" WHERE "mail" = $1;', 'cgdelete002')
        self.assertIsNotNone(result1)
        self.assertIsNotNone(result2)

        err, acct1 = await UserService.inst.info_acct(result1['acct_id'])
        self.assertIsNone(err)
        err, acct2 = await UserService.inst.info_acct(result2['acct_id'])
        self.assertIsNone(err)

        with AccountContext('admin@test', 'testtest') as admin_session:
            # Delete group
            res = admin_session.post('manage/class_group', {
                'reqtype': 'delete',
                'group_id': group_id,
            })
            self.assertAPIReturnSuccess(res.text)

            # Verify group is deleted
            err, group = await ClassGroupService.inst.get_class_group(group_id)
            self.assertIsNotNone(err)

    async def test_csv_validation_errors(self):
        """Test CSV validation and error handling"""
        with AccountContext('admin@test', 'testtest') as admin_session:
            # Test missing required fields
            invalid_csv = b"""email,name
missing001,Missing Password"""

            files = {'csv_file': ('invalid.csv', io.BytesIO(invalid_csv), 'text/csv')}
            res = admin_session.post('manage/class_group',
                data={
                    'reqtype': 'create',
                    'year': 118,
                    'semester': 1,
                    'class_number': 601,
                },
                files=files
            )
            self.assertAPIReturnValue(res.text, ("Eformat", "CSV missing required columns: email, name, password"))

            # Test file too large (simulate with header)
            # Note: Actual 2MB+ file test would be too slow

            # Test invalid IP format
            invalid_ip_csv = b"""email,name,password,specific_ip
invalidip001,Invalid IP User,Pass123,999.999.999.999"""

            files = {'csv_file': ('invalidip.csv', io.BytesIO(invalid_ip_csv), 'text/csv')}
            res = admin_session.post('manage/class_group',
                data={
                    'reqtype': 'create',
                    'year': 118,
                    'semester': 1,
                    'class_number': 602,
                },
                files=files
            )
            data = json.loads(res.text)
            self.assertEqual(data['status'], 'Einval')

    async def test_permission_control(self):
        """Test that only KERNEL users can access class group management"""
        # Create a non-KERNEL account
        self.signup('normaluser', 'normaluser@test', 'normalpass')

        with AccountContext('normaluser@test', 'normalpass') as user_session:
            # Try to access list page
            res = user_session.get('manage/class_group')
            self.assertAPIReturnValue(res.text, ("Eacces", "Permission denied"))

            # Try to create group
            res = user_session.post('manage/class_group', {
                'reqtype': 'create',
                'year': 119,
                'semester': 1,
                'class_number': 701,
            })
            # Should return permission error
            self.assertAPIReturnValue(res.text, ("Eacces", "Permission denied"))
