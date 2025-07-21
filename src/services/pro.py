import json
import os
import re

from msgpack import packb, unpackb

import config
from services.pack import PackService


class ProConst:
    """
    Constants used in problem management for status codes, checker types,
    name/code length constraints, and allowed user problem status sets.
    """

    NAME_MIN = 1
    NAME_MAX = 64
    CODE_MAX = 16384

    RATE_PRECISION_MIN = 0
    RATE_PRECISION_MAX = 3

    STATUS_ONLINE = 0
    STATUS_CONTEST = 1
    STATUS_HIDDEN = 2

    CHECKER_DIFF = 0
    CHECKER_DIFF_STRICT = 1
    CHECKER_DIFF_FLOAT = 2
    CHECKER_IOREDIR = 3
    CHECKER_CMS = 4

    CHECKER_TYPE = {
        CHECKER_DIFF: "diff",
        CHECKER_DIFF_STRICT: "diff-strict",
        CHECKER_DIFF_FLOAT: "diff-float",
        CHECKER_IOREDIR: "ioredir",
        CHECKER_CMS: "cms",
    }

    STR_2_CHECKER_TYPE = {t: s for s, t in CHECKER_TYPE.items()}

    PACKTYPE_FULL = 1
    PACKTYPE_CONTHTML = 2
    PACKTYPE_CONTPDF = 3

    # NOTE: collection for problem status
    PRO_STATUS_NORMAL_USER = [STATUS_ONLINE]
    PRO_STATUS_KERNEL_USER = [STATUS_ONLINE, STATUS_HIDDEN]
    PRO_STATUS_CONTEST_USER = [STATUS_ONLINE, STATUS_CONTEST]


class ProService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        ProService.inst = self

    async def get_pro(self, pro_id: int, allow_statuses: list[int]):
        """
        Fetch problem configuration and metadata by ID, ensuring it's in the allowed status.

        Args:
            pro_id (int): The ID of the problem to fetch.
            allow_statuses (list[int]): Allowed problem statuses for access.

        Returns:
            Tuple[Optional[Tuple[str, str]], Optional[dict]]:
                - Error code and message if any error occurs.
                - A dictionary containing problem metadata if successful.
        """

        for status in allow_statuses:
            assert ProConst.STATUS_ONLINE <= status <= ProConst.STATUS_HIDDEN
        pro_id = int(pro_id)

        async with self.db.acquire() as con:
            result = await con.fetch(
                """
                    SELECT "name", "status", "tags", "allow_submit",
                    "check_type", "is_makefile", "chalmeta", "limit", "rate_precision"
                    FROM "problem" WHERE "pro_id" = $1;
                """,
                pro_id,
            )
            if len(result) != 1:
                return ("Enoext", "Problem not found"), None
            result = result[0]

            name, status, tags, allow_submit, check_type, is_makefile, rate_precision, limit, chalmeta = (
                result["name"],
                result["status"],
                result["tags"],
                result["allow_submit"],
                result["check_type"],
                result["is_makefile"],
                result["rate_precision"],
                json.loads(result["limit"]),
                json.loads(result["chalmeta"]),
            )

            if status not in allow_statuses:
                return ("Eacces", "Permission denied"), None

            result = await con.fetch(
                """
                    SELECT "test_idx", "weight", "metadata"
                    FROM "test_config" WHERE "pro_id" = $1 ORDER BY "test_idx" ASC;
                """,
                pro_id,
            )

        test_groups = {}
        for test_group_idx, weight, metadata in result:
            test_groups[test_group_idx] = {
                "weight": weight,
                "metadata": json.loads(metadata),
            }

        testm_conf = {
            "chalmeta": chalmeta,
            "limit": limit,
            "check_type": check_type,
            "is_makefile": is_makefile,
            "test_group": test_groups,
            "rate_precision": rate_precision,
        }

        return (
            None,
            {
                "pro_id": pro_id,
                "name": name,
                "status": status,
                "testm_conf": testm_conf,
                "tags": tags,
                "allow_submit": allow_submit,
            },
        )

    async def list_pro(self, allow_pro_statuses: list[int]):
        """
        List problems with statuses in `allow_pro_statuses`, with Redis caching.

        Args:
            allow_pro_statuses (list[int]): List of allowed statuses.

        Returns:
            Tuple[None, list[dict]]:
                - None for error placeholder (always succeeds).
                - List of problems matching the given statuses.
        """

        for status in allow_pro_statuses:
            assert ProConst.STATUS_ONLINE <= status <= ProConst.STATUS_HIDDEN

        field = f"{allow_pro_statuses}"
        if (prolist := (await self.rs.hget("prolist", field))) is not None:
            prolist = unpackb(prolist)

        else:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    f"""
                        SELECT "problem"."pro_id", "problem"."name", "problem"."status", "problem"."tags"
                        FROM "problem"
                        WHERE "problem"."status" IN ({"".join(map(str, allow_pro_statuses))})
                        ORDER BY "pro_id" ASC;
                    """
                )

            prolist = []
            for pro_id, name, status, tags in result:
                if tags is None:
                    tags = ""

                prolist.append(
                    {
                        "pro_id": pro_id,
                        "name": name,
                        "status": status,
                        "tags": tags,
                    }
                )

            await self.rs.hset("prolist", field, packb(prolist))

        return None, prolist

    async def add_pro(self, name: str, status: int):
        """
        Add a new problem to the system with initial folders and symbolic links.

        Args:
            name (str): The name of the problem.
            status (int): Initial status (online/contest/hidden).

        Returns:
            Tuple[Optional[Tuple[str, str]], Optional[int]]:
                - Error code and message if invalid.
                - The newly created problem ID if successful.
        """

        name_len = len(name)
        if name_len < ProConst.NAME_MIN:
            return ("Enamemin", "Problem name too short"), None
        if name_len > ProConst.NAME_MAX:
            return ("Enamemax", "Problem name too long"), None
        if status < ProConst.STATUS_ONLINE or status > ProConst.STATUS_HIDDEN:
            return ("Eparam", "Invalid problem status"), None

        async with self.db.acquire() as con:
            result = await con.fetch(
                """
                    INSERT INTO "problem"
                    ("name", "status")
                    VALUES ($1, $2) RETURNING "pro_id";
                """,
                name,
                status,
            )
            if len(result) != 1:
                return ("Eunk", "Unknown error"), None

            pro_id = int(result[0]["pro_id"])

            os.mkdir(f"problem/{pro_id}")
            os.chmod(os.path.abspath(f"problem/{pro_id}"), 0o755)
            os.mkdir(f"problem/{pro_id}/res")
            os.mkdir(f"problem/{pro_id}/http")
            os.mkdir(f"problem/{pro_id}/res/testdata")
            os.symlink(
                os.path.abspath(f"problem/{pro_id}/http"),
                f"{config.WEB_PROBLEM_STATIC_FILE_DIRECTORY}/{pro_id}",
            )

        await self.rs.delete("prolist")

        return None, pro_id

    async def update_pro(self, pro_id: int, name: str, status: int, tags="", allow_submit=True):
        """
        Update problem metadata such as name, status, tags, and submission permission.

        Args:
            pro_id (int): The ID of the problem to update.
            name (str): New name.
            status (int): New status (online/contest/hidden).
            tags (str, optional): Tag string. Defaults to "".
            allow_submit (bool, optional): Submission permission. Defaults to True.

        Returns:
            Tuple[Optional[Tuple[str, str]], None]:
                - Error code and message if any error occurs.
                - None if successful.
        """

        assert ProConst.STATUS_ONLINE <= status <= ProConst.STATUS_HIDDEN
        name_len = len(name)
        if name_len < ProConst.NAME_MIN:
            return ("Enamemin", "Problem name too short"), None
        if name_len > ProConst.NAME_MAX:
            return ("Enamemax", "Problem name too long"), None
        if status < ProConst.STATUS_ONLINE or status > ProConst.STATUS_HIDDEN:
            return ("Eparam", "Invalid problem status"), None
        if tags and not re.match(r"^[a-zA-Z0-9-_, ]+$", tags):
            return ("Etags", "Invalid problem tag"), None

        async with self.db.acquire() as con:
            result = await con.fetch(
                """
                    UPDATE "problem"
                    SET "name" = $1, "status" = $2, "tags" = $3, "allow_submit" = $4
                    WHERE "pro_id" = $5 RETURNING "pro_id";
                """,
                name,
                status,
                tags,
                allow_submit,
                int(pro_id),
            )
            if len(result) != 1:
                return ("Enoext", "Problem not found"), None


        await self.rs.delete("prolist")

        return None, None

    async def update_test_config(self, pro_id: int, testm_conf: dict):
        """
        Update the test configuration (testm_conf) for a given problem.

        Args:
            pro_id (int): The ID of the problem to update.
            testm_conf (dict): The test configuration, with the following structure:

                - is_makefile (bool): Whether the problem uses a Makefile-based compilation.
                See: https://wiki.tfcis.org/TOJ#Makefile%E9%A1%8C%E7%9B%AE_(%E7%B7%A8%E8%AD%AF%E4%BA%92%E5%8B%95%E9%A1%8C)

                - check_type (int): One of the values defined in ProConst.CHECKER_TYPE, indicating
                the type of checker (e.g., diff, float-diff, ioredir).

                - limit (dict[str, dict[str, int]]): Per-language time and memory limits.
                    - Keys are compiler types (e.g., "gcc", "clang", "default").
                        Allowed compilers can be found in `ChalConst.ALLOW_COMPILERS`.
                    - Each value must contain:
                        - "timelimit" (int): Time limit in seconds (≥ 0)
                        - "memlimit" (int): Memory limit in kilobytes (≥ 0)
                    - Must include a "default" configuration.

                - rate_precision (int): Precision of the score (e.g., 0 for integers, 2 for 2 decimal places).

                - test_group (dict[int, dict]): Configuration for each test group (subtask). Each key is
                a test group index, and each value is a dict:
                    - "weight" (int): The score weight of this test group.
                    - "metadata" (dict): Metadata describing the test cases, e.g., input/output file names.

        Returns:
            Tuple[None, None]: Always returns (None, None) on success.

        Side Effects:
            - All existing `Challenge` records associated with this problem will be reset to
            the `NotStart` state, due to test configuration changes.
            - `test_valid_rate` materialized view will be refreshed.
            - Related Redis cache (`rate`, `pro_rate`) will be invalidated.
        """

        insert_values = []
        is_makefile = testm_conf['is_makefile']
        check_type = testm_conf['check_type']
        chalmeta = testm_conf['chalmeta']
        limit = testm_conf['limit']
        rate_precision = testm_conf['rate_precision']
        for test_group_idx, test_group_conf in testm_conf['test_group'].items():
            weight = test_group_conf['weight']
            insert_values.append((pro_id, test_group_idx, weight, json.dumps(test_group_conf['metadata'])))

        async with self.db.acquire() as con:
            await con.execute('DELETE FROM "test_config" WHERE "pro_id" = $1;', int(pro_id))
            await con.execute(
                'UPDATE "problem" SET is_makefile = $1, check_type = $2, chalmeta = $3, "limit" = $4, "rate_precision" = $5 WHERE pro_id = $6',
                is_makefile, check_type, json.dumps(chalmeta), json.dumps(limit), rate_precision, pro_id
            )

            if insert_values:
                await con.executemany(
                    '''INSERT INTO "test_config"
                        ("pro_id", "test_idx", "weight", "metadata")
                        VALUES ($1, $2, $3, $4);''',
                    insert_values
                )

        await self.db.execute("REFRESH MATERIALIZED VIEW test_valid_rate;")
        await self.rs.delete('rate')
        await self.rs.hdel('pro_rate', pro_id)

        return None, None

    async def unpack_pro(self, pro_id: int, pack_token: str):
        """
        Unpack and apply a packed problem archive.

        Args:
            pro_id (int): The ID of the problem to unpack into.
            pack_token (str): Token for identifying the uploaded archive.

        Returns:
            Tuple[Optional[Tuple[str, str]], None]:
                - Error code and message if unpacking or config fails.
                - None if successful.
        """

        from services.chal import ChalConst
        err, _ = await PackService.inst.unpack(pack_token, f"problem/{pro_id}", True)
        if err:
            return err, None

        try:
            os.chmod(os.path.abspath(f"problem/{pro_id}"), 0o755)
            os.symlink(
                os.path.abspath(f"problem/{pro_id}/http"),
                f"{config.WEB_PROBLEM_STATIC_FILE_DIRECTORY}/{pro_id}",
            )

        except FileExistsError:
            pass

        try:
            with open(f"problem/{pro_id}/conf.json") as conf_f:
                conf = json.load(conf_f)
        except json.decoder.JSONDecodeError:
            return ("Econf", "Problem config json syntax error"), None

        is_makefile = False
        if 'compile' in conf:
            is_makefile = conf["compile"] == 'makefile'
        elif 'is_makefile' in conf:
            is_makefile = conf["is_makefile"]

        check_type = ProConst.STR_2_CHECKER_TYPE[conf["check"]]

        ALLOW_COMPILERS = set(list(ChalConst.ALLOW_COMPILERS) + ['default'])
        if is_makefile:
            ALLOW_COMPILERS = {'default', 'gcc', 'g++', 'clang', 'clang++'}

        if "limit" in conf:
            limits = {}
            for comp_type, limit in conf["limit"].items():
                if comp_type not in ALLOW_COMPILERS:
                    continue

                try:
                    limit['timelimit'] = max(int(limit['timelimit']), 0)
                    limit['memlimit'] = max(int(limit['memlimit']) * 1024, 0)
                except KeyError as e:
                    limit[e.args[0]] = 0
                except ValueError:
                    continue

                limits[comp_type] = limit

            if 'default' not in limits:
                return ("Econf", "Problem limit config require default value"), None

        elif 'timelimit' in conf and 'memlimit' in conf:
            try:
                limits = {
                    'default': {
                        'timelimit': int(conf["timelimit"]),
                        'memlimit': int(conf["memlimit"]) * 1024
                    }
                }
            except ValueError:
                return ("Econf", "Problem limit config have invalid value"), None
        else:
                return ("Econf", "Problem config require limit or timelimit/memlimit"), None

        chalmeta = {}
        if 'metadata' in conf:
            chalmeta = conf["metadata"]  # INFO: ioredir data

        async with self.db.acquire() as con:
            await con.execute('DELETE FROM "test_config" WHERE "pro_id" = $1;', int(pro_id))
            await con.execute(
                'UPDATE "problem" SET is_makefile = $1, check_type = $2, chalmeta = $3, "limit" = $4 WHERE pro_id = $5',
                is_makefile, check_type, json.dumps(chalmeta), json.dumps(limits), pro_id
            )

            insert_values = []

            for test_idx, test_conf in enumerate(conf["test"]):
                for i in range(len(test_conf["data"])):
                    test_conf["data"][i] = str(test_conf["data"][i])

                metadata = {"data": test_conf["data"]}
                insert_values.append((pro_id, test_idx, test_conf['weight'], json.dumps(metadata)))

            await con.executemany(
                '''INSERT INTO "test_config"
                    ("pro_id", "test_idx", "weight", "metadata")
                    VALUES ($1, $2, $3, $4);''',
                insert_values
            )
            await con.execute("REFRESH MATERIALIZED VIEW test_valid_rate;")

        await self.rs.delete("prolist")

        return None, None

class ProClassConst:
    OFFICIAL_PUBLIC = 0
    OFFICIAL_HIDDEN = 1
    USER_PUBLIC = 2
    USER_HIDDEN = 3
    NAME_MIN = 1
    NAME_MAX = 50
    DESC_MIN = 0
    DESC_MAX = 2048

class ProClassService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        ProClassService.inst = self

    async def get_proclass(self, proclass_id: int):
        async with self.db.acquire() as con:
            res = await con.fetch(
                'SELECT "proclass_id", "name", "desc", "list", "acct_id", "type" FROM "proclass" WHERE "proclass_id" = $1;',
                int(proclass_id),
            )

            if len(res) != 1:
                return ("Enoext", "Problem class not found"), None

        return None, res[0]

    async def get_proclass_list(self):
        async with self.db.acquire() as con:
            res = await con.fetch('SELECT "proclass_id", "name", "acct_id", "type" FROM "proclass" ORDER BY "proclass_id" ASC;')

        return None, res

    async def add_proclass(self, name: str, p_list: list[int], desc: str, acct_id: int, proclass_type: int):
        async with self.db.acquire() as con:
            res = await con.fetchrow(
                """
                    INSERT INTO "proclass" ("name", "list", "desc", "acct_id", "type")
                    VALUES ($1, $2, $3, $4, $5) RETURNING "proclass_id";
                """,
                name,
                p_list,
                desc,
                acct_id,
                proclass_type,
            )

        return None, res[0]

    async def remove_proclass(self, proclass_id: int):
        async with self.db.acquire() as con:
            result: str = await con.execute('DELETE FROM "proclass" WHERE "proclass_id" = $1', int(proclass_id))
            affected_row_cnt = int(result.split(" ")[1]) # NOTE: DELETE \d+
            if affected_row_cnt == 0:
                return ('Enoext', 'Bulletin not found'), None

    async def update_proclass(self, proclass_id, name, p_list, desc, proclass_type):
        proclass_id = int(proclass_id)
        async with self.db.acquire() as con:
            await con.execute(
                'UPDATE "proclass" SET "name" = $1, "list" = $2, "desc" = $3, "type" = $4 WHERE "proclass_id" = $5',
                name,
                p_list,
                desc,
                proclass_type,
                proclass_id,
            )
