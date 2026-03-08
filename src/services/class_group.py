import csv
import io
from dataclasses import dataclass
from datetime import datetime
from ipaddress import AddressValueError, IPv4Address

from handlers.base import UnifiedWebSocketHandler
from services.user import UserService


@dataclass(slots=True)
class ClassGroup:
    group_id: int
    year: int
    semester: int
    class_number: int
    custom_name: str
    ip_range_start: str
    ip_range_end: str
    ip_login_enabled: bool
    created_at: datetime
    updated_at: datetime

    def get_display_name(self) -> str:
        semester_name = "上學期" if self.semester == 1 else "下學期"
        if self.custom_name:
            return f"{self.year}學年 {semester_name} {self.class_number}班 - {self.custom_name}"
        return f"{self.year}學年 {semester_name} {self.class_number}班"


class ClassGroupService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        ClassGroupService.inst = self

    async def list_class_groups(
        self,
        pageoff: int = 0,
        pagesize: int = 40,
        year: int | None = None,
        semester: int | None = None,
        class_number: int | None = None,
        custom_name: str | None = None,
    ) -> tuple[tuple | None,list[ClassGroup] | None]:
        """List all class groups with filter and pagination support"""
        try:
            async with self.db.acquire() as con:
                # Build query conditions
                where_clause, params, param_count = self._build_filter_conditions(year, semester, class_number, custom_name)

                # Add pagination parameters
                params.append(pagesize)
                params.append(pageoff)

                query = f'''
                    SELECT
                        "group_id", "year", "semester", "class_number",
                        "custom_name", "ip_range_start", "ip_range_end",
                        "ip_login_enabled", "created_at", "updated_at"
                    FROM "class_group"
                    WHERE {where_clause}
                    ORDER BY "year" DESC, "semester" DESC, "class_number" ASC
                    LIMIT ${param_count} OFFSET ${param_count + 1};
                '''

                result = await con.fetch(query, *params)
                groups = [ClassGroup(**row) for row in result]
                return None, groups

        except Exception as e:
            return ("Eunk", f"Database error: {str(e)}"), None

    async def count_class_groups(
        self,
        year: int | None = None,
        semester: int | None = None,
        class_number: int | None = None,
        custom_name: str | None = None,
    ) -> int:
        """Count total class groups with filter support"""
        try:
            async with self.db.acquire() as con:
                where_clause, params, _ = self._build_filter_conditions(year, semester, class_number, custom_name)

                query = f'SELECT COUNT(*) as count FROM "class_group" WHERE {where_clause};'
                result = await con.fetchrow(query, *params)
                return result["count"]

        except Exception:
            return 0

    async def get_class_group(self, group_id: int) -> tuple[tuple | None, ClassGroup | None]:
        """Get single class group information"""
        try:
            async with self.db.acquire() as con:
                result = await con.fetchrow(
                    '''
                    SELECT
                        "group_id", "year", "semester", "class_number",
                        "custom_name", "ip_range_start", "ip_range_end",
                        "ip_login_enabled", "created_at", "updated_at"
                    FROM "class_group"
                    WHERE "group_id" = $1;
                    ''',
                    group_id,
                )

                if not result:
                    return ("Enoext", "Class group not found"), None

                return None, ClassGroup(**result)

        except Exception as e:
            return ("Eunk", f"Database error: {str(e)}"), None

    async def get_group_members(self, group_id: int) -> tuple[tuple | None, list[dict] | None]:
        """Get all members of class group (including account info)"""
        try:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                    SELECT
                        a."acct_id", a."name", a."mail", a."lastip", a."specific_ip",
                        cgm."joined_at"
                    FROM "class_group_member" cgm
                    JOIN "account" a ON cgm."acct_id" = a."acct_id"
                    WHERE cgm."group_id" = $1
                    ORDER BY a."acct_id" ASC;
                    ''',
                    group_id,
                )

                members = []
                for row in result:
                    members.append({**row})

                return None, members

        except Exception as e:
            return ("Eunk", f"Database error: {str(e)}"), None

    async def get_account_id_range(self, group_id: int) -> tuple[tuple | None, tuple | None]:
        """Get account ID range of class group"""
        try:
            async with self.db.acquire() as con:
                result = await con.fetchrow(
                    '''
                    SELECT
                        MIN("acct_id") as min_id,
                        MAX("acct_id") as max_id
                    FROM "class_group_member"
                    WHERE "group_id" = $1;
                    ''',
                    group_id,
                )

                if result and result["min_id"] is not None:
                    return None, (result["min_id"], result["max_id"])
                return None, None

        except Exception as e:
            return ("Eunk", f"Database error: {str(e)}"), None

    # === Create/Update/Delete Methods ===

    async def create_class_group(
        self,
        year: int,
        semester: int,
        class_number: int,
        custom_name: str,
        ip_range_start: str = "",
        ip_range_end: str = "",
    ) -> tuple[tuple | None, int | None]:
        """Create new class group"""
        try:
            async with self.db.acquire() as con:
                result = await con.fetchrow(
                    '''
                    INSERT INTO "class_group"
                    ("year", "semester", "class_number", "custom_name",
                     "ip_range_start", "ip_range_end", "ip_login_enabled")
                    VALUES ($1, $2, $3, $4, $5, $6, FALSE)
                    RETURNING "group_id";
                    ''',
                    year,
                    semester,
                    class_number,
                    custom_name,
                    ip_range_start,
                    ip_range_end,
                )

                return None, result["group_id"]

        except Exception as e:
            return ("Eunk", f"Failed to create class group: {str(e)}"), None

    async def update_class_group(self, group: ClassGroup) -> tuple | None:
        """Update class group information"""
        try:
            async with self.db.acquire() as con:
                async with con.transaction():
                    # Get original IP range
                    old_group = await con.fetchrow(
                        '''
                        SELECT "ip_range_start", "ip_range_end"
                        FROM "class_group"
                        WHERE "group_id" = $1;
                        ''',
                        group.group_id,
                    )

                    if not old_group:
                        return ("Enoext", "Class group not found")

                    # Update class group
                    await con.execute(
                        '''
                        UPDATE "class_group"
                        SET "year" = $2, "semester" = $3, "class_number" = $4,
                            "custom_name" = $5, "ip_range_start" = $6, "ip_range_end" = $7,
                            "updated_at" = NOW()
                        WHERE "group_id" = $1;
                        ''',
                        group.group_id,
                        group.year,
                        group.semester,
                        group.class_number,
                        group.custom_name,
                        group.ip_range_start,
                        group.ip_range_end,
                    )

                    # If IP range is cleared, remove all specific IPs within old range
                    if not group.ip_range_start and not group.ip_range_end:
                        await self._clear_ips_in_range(
                            con, group.group_id, old_group["ip_range_start"], old_group["ip_range_end"]
                        )

                return None

        except Exception as e:
            return ("Eunk", f"Failed to update class group: {str(e)}")

    async def delete_class_group(self, group_id: int) -> tuple | None:
        """Delete class group (CASCADE will auto-delete relations)"""
        try:
            async with self.db.acquire() as con:
                result = await con.execute(
                    '''
                    DELETE FROM "class_group"
                    WHERE "group_id" = $1;
                    ''',
                    group_id,
                )

                if result == "DELETE 0":
                    return ("Enoext", "Class group not found")

                return None

        except Exception as e:
            return ("Eunk", f"Failed to delete class group: {str(e)}")

    # === Member Management Methods ===

    async def add_member(self, group_id: int, acct_id: int) -> tuple | None:
        """Add account to class group"""
        try:
            async with self.db.acquire() as con:
                await con.execute(
                    '''
                    INSERT INTO "class_group_member" ("group_id", "acct_id")
                    VALUES ($1, $2)
                    ON CONFLICT DO NOTHING;
                    ''',
                    group_id,
                    acct_id,
                )
                return None

        except Exception as e:
            return ("Eunk", f"Failed to add member: {str(e)}")

    async def remove_member(self, group_id: int, acct_id: int) -> tuple | None:
        """Remove account from class group (does not delete account itself)"""
        try:
            async with self.db.acquire() as con:
                result = await con.execute(
                    '''
                    DELETE FROM "class_group_member"
                    WHERE "group_id" = $1 AND "acct_id" = $2;
                    ''',
                    group_id,
                    acct_id,
                )

                if result == "DELETE 0":
                    return ("Enoext", "Member not found in this group")

                return None

        except Exception as e:
            return ("Eunk", f"Failed to remove member: {str(e)}")

    async def batch_create_accounts(
        self,
        group_id: int,
        accounts_data: list[dict],
        ip_range_start: str = "",
        ip_range_end: str = "",
    ) -> tuple[tuple | None, int | None]:
        """Batch create accounts and add to class group"""
        if not accounts_data:
            return None, 0

        # Check if IP allocation from range is needed
        need_ip_allocation = ip_range_start and ip_range_end
        ip_list = []

        if need_ip_allocation:
            try:
                ip_list = self._generate_ips_from_range(ip_range_start, ip_range_end)
            except ValueError as e:
                return ("Erange", str(e)), None

        created_acct_ids: list[int] = []
        try:
            async with self.db.acquire() as con:
                async with con.transaction():
                    # Check if emails already exist
                    emails = [acc["email"] for acc in accounts_data]
                    existing = await con.fetch(
                        '''
                        SELECT "mail" FROM "account"
                        WHERE "mail" = ANY($1::text[]);
                        ''',
                        emails,
                    )

                    if existing:
                        existing_emails = [row["mail"] for row in existing]
                        return ("Eexist", f"Accounts already exist: {', '.join(existing_emails)}"), None

                    created_count = 0
                    for idx, acc_data in enumerate(accounts_data):
                        # Determine specific_ip
                        specific_ip = acc_data.get("specific_ip", "")

                        # If no specific_ip and IP range exists, allocate from range
                        if not specific_ip and need_ip_allocation:
                            if idx < len(ip_list):
                                specific_ip = ip_list[idx]

                        # Create account — uses its own DB connection, outside this transaction
                        err, acct_id = await UserService.inst.sign_up(
                            acc_data["email"], acc_data["password"], acc_data["name"]
                        )

                        if err:
                            raise Exception(f"Failed to create account {acc_data['email']}: {err}")
                        assert acct_id

                        # Track created accounts so they can be cleaned up on failure
                        created_acct_ids.append(acct_id)

                        # Set specific_ip
                        if specific_ip:
                            err, acct = await UserService.inst.info_acct(acct_id)
                            if err:
                                raise Exception(f"Failed to get account info: {err}")
                            assert acct

                            acct.specific_ip = specific_ip
                            err, _ = await UserService.inst.update_acct(acct)
                            if err:
                                raise Exception(f"Failed to update account IP: {err}")

                        # Add to class group
                        await con.execute(
                            '''
                            INSERT INTO "class_group_member" ("group_id", "acct_id")
                            VALUES ($1, $2);
                            ''',
                            group_id,
                            acct_id,
                        )

                        created_count += 1

                    return None, created_count

        except Exception as e:
            # Clean up accounts that were created outside the transaction before the failure
            if created_acct_ids:
                try:
                    async with self.db.acquire() as cleanup_con:
                        await cleanup_con.execute(
                            'DELETE FROM "account" WHERE "acct_id" = ANY($1::int[]);',
                            created_acct_ids,
                        )
                except Exception:
                    pass  # best-effort cleanup
            return ("Eunk", f"Failed to create accounts: {str(e)}"), None

    # === IP Management Methods ===

    async def set_ip_range(
        self,
        group_id: int,
        ip_start: str,
        ip_end: str,
    ) -> tuple | None:
        """Set IP range and auto-assign to all members"""
        # Validate IP format
        err = self._validate_ip_range(ip_start, ip_end)
        if err:
            return err

        # Generate IP list
        try:
            ip_list = self._generate_ips_from_range(ip_start, ip_end)
        except ValueError as e:
            return ("Erange", str(e))

        try:
            async with self.db.acquire() as con:
                async with con.transaction():
                    # Update class_group IP range
                    await con.execute(
                        '''
                        UPDATE "class_group"
                        SET "ip_range_start" = $2, "ip_range_end" = $3, "updated_at" = NOW()
                        WHERE "group_id" = $1;
                        ''',
                        group_id,
                        ip_start,
                        ip_end,
                    )

                    # Assign IPs to members sequentially
                    acct_ids = await self._assign_ips_to_members(con, group_id, ip_list)

                    # Clear cache and force logout all members
                    await self._invalidate_accounts_cache(acct_ids)
                    await self._force_logout_accounts(acct_ids)

            return None

        except Exception as e:
            return ("Eunk", f"Failed to set IP range: {str(e)}")

    async def enable_ip_login(self, group_id: int, enabled: bool) -> tuple | None:
        """Enable/disable IP login restriction"""
        try:
            async with self.db.acquire() as con:
                async with con.transaction():
                    # Update class_group ip_login_enabled
                    await con.execute(
                        '''
                        UPDATE "class_group"
                        SET "ip_login_enabled" = $2, "updated_at" = NOW()
                        WHERE "group_id" = $1;
                        ''',
                        group_id,
                        enabled,
                    )

                    if enabled:
                        # Enable: allocate IP from range
                        group_result = await con.fetchrow(
                            '''
                            SELECT "ip_range_start", "ip_range_end"
                            FROM "class_group"
                            WHERE "group_id" = $1;
                            ''',
                            group_id,
                        )

                        if not group_result or not group_result["ip_range_start"] or not group_result["ip_range_end"]:
                            return ("Einval", "IP range not set for this group")

                        ip_start = group_result["ip_range_start"]
                        ip_end = group_result["ip_range_end"]

                        try:
                            ip_list = self._generate_ips_from_range(ip_start, ip_end)
                        except ValueError as e:
                            return ("Erange", str(e))

                        # Get all members and assign IPs
                        acct_ids = await self._assign_ips_to_members(con, group_id, ip_list)

                    else:
                        # Disable: clear all members' specific_ip
                        acct_ids = await con.fetch(
                            '''
                            SELECT "acct_id"
                            FROM "class_group_member"
                            WHERE "group_id" = $1;
                            ''',
                            group_id,
                        )

                        acct_ids = [row["acct_id"] for row in acct_ids]

                        for acct_id in acct_ids:
                            await con.execute(
                                '''
                                UPDATE "account"
                                SET "specific_ip" = ''
                                WHERE "acct_id" = $1;
                                ''',
                                acct_id,
                            )

                    # Clear cache and force logout all members
                    await self._invalidate_accounts_cache(acct_ids)
                    await self._force_logout_accounts(acct_ids)

            return None

        except Exception as e:
            return ("Eunk", f"Failed to toggle IP login: {str(e)}")

    async def remove_all_specific_ip(self, group_id: int) -> tuple | None:
        """Clear all members' specific IPs"""
        try:
            async with self.db.acquire() as con:
                async with con.transaction():
                    # Clear class_group IP range
                    await con.execute(
                        '''
                        UPDATE "class_group"
                        SET "ip_range_start" = '', "ip_range_end" = '',
                            "ip_login_enabled" = FALSE, "updated_at" = NOW()
                        WHERE "group_id" = $1;
                        ''',
                        group_id,
                    )

                    # Get all members
                    acct_ids = await con.fetch(
                        '''
                        SELECT "acct_id"
                        FROM "class_group_member"
                        WHERE "group_id" = $1;
                        ''',
                        group_id,
                    )

                    acct_ids = [row["acct_id"] for row in acct_ids]

                    # Clear all members' specific_ip
                    for acct_id in acct_ids:
                        await con.execute(
                            '''
                            UPDATE "account"
                            SET "specific_ip" = ''
                            WHERE "acct_id" = $1;
                            ''',
                            acct_id,
                        )

                    await self._invalidate_accounts_cache(acct_ids)
                    await self._force_logout_accounts(acct_ids)

            return None

        except Exception as e:
            return ("Eunk", f"Failed to remove all IPs: {str(e)}")

    async def update_member_ip(
        self,
        group_id: int,
        acct_id: int,
        new_ip: str,
    ) -> tuple | None:
        """Update single member's specific IP"""
        # Validate IP format
        if new_ip:
            is_valid, error_msg = self._validate_ip(new_ip)
            if not is_valid:
                return ("Einval", f"Invalid IP: {error_msg}")

        try:
            async with self.db.acquire() as con:
                # Confirm member exists in group
                member_exists = await con.fetchrow(
                    '''
                    SELECT 1 FROM "class_group_member"
                    WHERE "group_id" = $1 AND "acct_id" = $2;
                    ''',
                    group_id,
                    acct_id,
                )

                if not member_exists:
                    return ("Enoext", "Member not found in this group")

                # Update specific_ip
                await con.execute(
                    '''
                    UPDATE "account"
                    SET "specific_ip" = $2
                    WHERE "acct_id" = $1;
                    ''',
                    acct_id,
                    new_ip,
                )

                # Clear cache and force logout
                await self._invalidate_accounts_cache([acct_id])
                await self._force_logout_accounts([acct_id])

            return None

        except Exception as e:
            return ("Eunk", f"Failed to update member IP: {str(e)}")

    # === Helper Methods ===

    def _build_filter_conditions(
        self,
        year: int | None = None,
        semester: int | None = None,
        class_number: int | None = None,
        custom_name: str | None = None,
    ) -> tuple[str, list, int]:
        """Build WHERE clause and parameter list for filter conditions

        Returns:
            (where_clause, params, next_param_count)
        """
        where_clauses = []
        params = []
        param_count = 1

        if year is not None:
            where_clauses.append(f'"year" = ${param_count}')
            params.append(year)
            param_count += 1

        if semester is not None:
            where_clauses.append(f'"semester" = ${param_count}')
            params.append(semester)
            param_count += 1

        if class_number is not None:
            where_clauses.append(f'"class_number" = ${param_count}')
            params.append(class_number)
            param_count += 1

        if custom_name is not None:
            where_clauses.append(f'"custom_name" LIKE ${param_count}')
            params.append(f'%{custom_name}%')
            param_count += 1

        where_clause = " AND ".join(where_clauses) if where_clauses else "TRUE"
        return where_clause, params, param_count

    def _validate_ip(self, ip: str) -> tuple[bool, str | None]:
        """Validate IP format"""
        try:
            IPv4Address(ip)
            return True, None
        except AddressValueError as e:
            return False, str(e)

    def _validate_ip_range(self, ip_start: str, ip_end: str) -> tuple | None:
        """Validate IP range format"""
        is_valid, error_msg = self._validate_ip(ip_start)
        if not is_valid:
            return ("Einval", f"Invalid start IP: {error_msg}")

        is_valid, error_msg = self._validate_ip(ip_end)
        if not is_valid:
            return ("Einval", f"Invalid end IP: {error_msg}")

        return None

    def _generate_ips_from_range(self, ip_start: str, ip_end: str) -> list[str]:
        """Generate IP list from IP range"""
        start = IPv4Address(ip_start)
        end = IPv4Address(ip_end)

        if start > end:
            raise ValueError("Start IP must be less than or equal to end IP")

        ips = []
        current = start
        while current <= end:
            ips.append(str(current))
            current += 1

        return ips

    async def _invalidate_accounts_cache(self, acct_ids: list[int]) -> None:
        """Clear Redis cache for accounts"""
        async with self.rs.pipeline() as pipe:
            for acct_id in acct_ids:
                await pipe.delete(f"account@{acct_id}")
            await pipe.execute()

    async def _assign_ips_to_members(self, con, group_id: int, ip_list: list[str]) -> list[int]:
        """Assign IPs to members sequentially

        Args:
            con: Database connection
            group_id: Class group ID
            ip_list: IP list

        Returns:
            List of affected acct_ids
        """
        # Get all members
        members = await con.fetch(
            '''
            SELECT "acct_id"
            FROM "class_group_member"
            WHERE "group_id" = $1
            ORDER BY "acct_id" ASC;
            ''',
            group_id,
        )

        # Assign IPs to members sequentially
        acct_ids = []
        for idx, member in enumerate(members):
            acct_id = member["acct_id"]
            acct_ids.append(acct_id)

            try:
                specific_ip = ip_list[idx]
            except IndexError:
                specific_ip = ""

            await con.execute(
                '''
                UPDATE "account"
                SET "specific_ip" = $2
                WHERE "acct_id" = $1;
                ''',
                acct_id,
                specific_ip,
            )

        return acct_ids

    async def _force_logout_accounts(self, acct_ids: list[int]) -> None:
        """Force logout account list (clear Redis session and publish logout event)"""
        for acct_id in acct_ids:
            # Publish all session keys to logout channel
            session_keys = await self.rs.hgetall(f"account_session@{acct_id}")
            async with self.rs.pipeline() as pipe:
                for session_key in session_keys:
                    await pipe.publish(UnifiedWebSocketHandler._LOGOUT_EVENT_CHANNEL, session_key.decode())
                # Delete account_session
                await pipe.delete(f"account_session@{acct_id}")
                await pipe.execute()

    async def _clear_ips_in_range(self, con, group_id: int, old_start: str, old_end: str) -> None:
        """Clear all members' specific IPs within specified IP range"""
        if not old_start or not old_end:
            return

        try:
            old_ip_list = self._generate_ips_from_range(old_start, old_end)
        except ValueError:
            return

        if not old_ip_list:
            return

        acct_ids = await con.fetch(
            '''
            UPDATE "account" a
            SET "specific_ip" = ''
            FROM "class_group_member" cgm
            WHERE cgm."group_id" = $1
            AND a."acct_id" = cgm."acct_id"
            AND a."specific_ip" = ANY($2::text[])
            RETURNING a."acct_id";
            ''',
            group_id,
            old_ip_list,
        )

        affected_acct_ids = [row["acct_id"] for row in acct_ids]
        if affected_acct_ids:
            await self._invalidate_accounts_cache(affected_acct_ids)
            await self._force_logout_accounts(affected_acct_ids)

    async def parse_csv(
        self,
        csv_content: bytes,
        max_size: int = 2 * 1024 * 1024,
    ) -> tuple[tuple | None, list[dict] | None]:
        """Parse and validate CSV file"""
        if len(csv_content) > max_size:
            return ("Esize", "CSV file too large (max 2MB)"), None

        try:
            content = csv_content.decode("utf-8")
            reader = csv.DictReader(io.StringIO(content))

            # Validate required fields
            required_fields = {"email", "name", "password"}
            if not required_fields.issubset(set(reader.fieldnames or [])):
                return ("Eformat", "CSV missing required columns: email, name, password"), None

            accounts = []
            for row_num, row in enumerate(reader, start=2):  # start=2 because first line is header
                # Validate each row data
                if not row["email"] or not row["name"] or not row["password"]:
                    return ("Eformat", f"Row {row_num}: Missing required field"), None

                account_data = {
                    "email": row["email"].strip(),
                    "name": row["name"].strip(),
                    "password": row["password"].strip(),
                    "specific_ip": row.get("specific_ip", "").strip(),
                }

                # Validate specific_ip format (if provided)
                if account_data["specific_ip"]:
                    is_valid, error_msg = self._validate_ip(account_data["specific_ip"])
                    if not is_valid:
                        return ("Einval", f"Row {row_num}: Invalid IP address - {error_msg}"), None

                accounts.append(account_data)

            if len(accounts) == 0:
                return ("Eformat", "CSV file is empty"), None

            return None, accounts

        except UnicodeDecodeError:
            return ("Eformat", "CSV file encoding error (use UTF-8)"), None
        except Exception as e:
            return ("Eformat", f"CSV parse error: {str(e)}"), None