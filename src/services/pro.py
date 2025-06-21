import json
import os
import re

from msgpack import packb, unpackb

import config
from services.pack import PackService
from services.user import Account


class ProConst:
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

    PACKTYPE_FULL = 1
    PACKTYPE_CONTHTML = 2
    PACKTYPE_CONTPDF = 3


class ProService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        ProService.inst = self

    async def get_pro(self, pro_id, acct: Account | None = None, is_contest: bool = False):
        """
        Parameter `is_contest` should be set to true if you want to get contest problems and your account type is not kernel.

        :param pro_id:
        :param acct:
        :param is_contest:
        :return:
        """
        pro_id = int(pro_id)
        max_status = self.get_acct_limit(acct, is_contest)

        async with self.db.acquire() as con:
            result = await con.fetch(
                """
                    SELECT "name", "status", "tags", "allow_submit",
                    "check_type", "is_makefile", "chalmeta", "limit", "rate_precision"
                    FROM "problem" WHERE "pro_id" = $1 AND "status" <= $2;
                """,
                pro_id,
                max_status,
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

    async def list_pro(self, acct: Account | None = None, is_contest=False):
        if acct is None:
            max_status = ProConst.STATUS_ONLINE

        else:
            max_status = self.get_acct_limit(acct, contest=is_contest)

        field = f"{max_status}|{[1, 2]}"  # TODO: Remove class column on db
        if (prolist := (await self.rs.hget("prolist", field))) is not None:
            prolist = unpackb(prolist)

        else:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    """
                        SELECT "problem"."pro_id", "problem"."name", "problem"."status", "problem"."tags"
                        FROM "problem"
                        WHERE "problem"."status" <= $1
                        ORDER BY "pro_id" ASC;
                    """,
                    max_status,
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

    async def add_pro(self, name, status, pack_token):
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

            if pack_token:
                err, _ = await self.unpack_pro(pro_id, ProConst.PACKTYPE_FULL, pack_token)
                if err:
                    return err, None

                await con.execute("REFRESH MATERIALIZED VIEW test_valid_rate;")

            else:
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

    # TODO: Too many args
    async def update_pro(self, pro_id, name, status, pack_type, pack_token=None, tags="", allow_submit=True):
        name_len = len(name)
        if name_len < ProConst.NAME_MIN:
            return ("Enamemin", "Problem name too short"), None
        if name_len > ProConst.NAME_MAX:
            return ("Enamemax", "Problem name too long"), None
        del name_len
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

            if pack_token is not None:
                err, _ = await self.unpack_pro(pro_id, pack_type, pack_token)
                if err:
                    return err, None

                await con.execute("REFRESH MATERIALIZED VIEW test_valid_rate;")

        await self.rs.delete("prolist")

        return None, None

    async def update_test_config(self, pro_id, testm_conf: dict):
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

    # TODO: 把這破函數命名改一下
    def get_acct_limit(self, acct: Account | None = None, contest=False):
        if contest:
            return ProConst.STATUS_CONTEST

        elif acct is None:
            return ProConst.STATUS_ONLINE

        elif acct.is_kernel():
            return ProConst.STATUS_HIDDEN

        else:
            return ProConst.STATUS_ONLINE

    async def unpack_pro(self, pro_id, pack_type, pack_token):
        from services.chal import ChalConst
        if pack_type == ProConst.PACKTYPE_FULL:
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

            check_type = self._get_check_type(conf["check"])

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
                    except (ValueError, KeyError):
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


        return None, None

    def _get_check_type(self, s: str):
        if s == "diff":
            return ProConst.CHECKER_DIFF
        elif s == "diff-strict":
            return ProConst.CHECKER_DIFF_STRICT
        elif s == "diff-float":
            return ProConst.CHECKER_DIFF_FLOAT
        elif s == "ioredir":
            return ProConst.CHECKER_IOREDIR
        elif s == "cms":
            return ProConst.CHECKER_CMS

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
            affected_row_cnt = int(result.split(" ")[1]) # DELETE \d+
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
