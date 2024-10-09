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
    STATUS_ONLINE = 0
    STATUS_CONTEST = 1
    STATUS_HIDDEN = 2
    STATUS_OFFLINE = 3

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


class ProService:
    NAME_MIN = 1
    NAME_MAX = 64
    CODE_MAX = 16384
    STATUS_ONLINE = 0
    STATUS_CONTEST = 1
    STATUS_HIDDEN = 2
    STATUS_OFFLINE = 3

    PACKTYPE_FULL = 1
    PACKTYPE_CONTHTML = 2
    PACKTYPE_CONTPDF = 3

    CHECKER_DIFF = 0
    CHECKER_DIFF_STRICT = 1
    CHECKER_DIFF_FLOAT = 2
    CHECKER_IOREDIR = 3
    CHECKER_CMS = 4

    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        ProService.inst = self

    async def get_pro(self, pro_id, acct: Account = None, is_contest: bool = False):
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
                    "check_type", "is_makefile", "chalmeta", "limit"
                    FROM "problem" WHERE "pro_id" = $1 AND "status" <= $2;
                """,
                pro_id,
                max_status,
            )
            if len(result) != 1:
                return "Enoext", None
            result = result[0]

            name, status, tags, allow_submit, check_type, is_makefile, limit, chalmeta = (
                result["name"],
                result["status"],
                result["tags"],
                result["allow_submit"],
                result["check_type"],
                result["is_makefile"],
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

    async def list_pro(self, acct: Account = None, is_contest=False):
        if acct is None:
            max_status = ProService.STATUS_ONLINE

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
        if name_len < ProService.NAME_MIN:
            return "Enamemin", None
        if name_len > ProService.NAME_MAX:
            return "Enamemax", None
        if status < ProService.STATUS_ONLINE or status > ProService.STATUS_OFFLINE:
            return "Eparam", None

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
                return "Eunk", None

            pro_id = int(result[0]["pro_id"])

            if pack_token:
                _, _ = await self.unpack_pro(pro_id, ProService.PACKTYPE_FULL, pack_token)
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
        if name_len < ProService.NAME_MIN:
            return "Enamemin", None
        if name_len > ProService.NAME_MAX:
            return "Enamemax", None
        del name_len
        if status < ProService.STATUS_ONLINE or status > ProService.STATUS_OFFLINE:
            return "Eparam", None
        if tags and not re.match(r"^[a-zA-Z0-9-_, ]+$", tags):
            return "Etags", None

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
                return "Enoext", None

            if pack_token is not None:
                err, _ = await self.unpack_pro(pro_id, pack_type, pack_token)
                if err:
                    return err, None

                await con.execute("REFRESH MATERIALIZED VIEW test_valid_rate;")

        await self.rs.delete("prolist")

        return None, None

    async def update_test_config(self, pro_id, testm_conf: dict):
        insert_sql = []
        is_makefile = testm_conf['is_makefile']
        check_type = testm_conf['check_type']
        chalmeta = testm_conf['chalmeta']
        limit = testm_conf['limit']
        for test_group_idx, test_group_conf in testm_conf['test_group'].items():
            weight = test_group_conf['weight']

            sql = '({}, {}, {}, \'{}\')'.format(pro_id, test_group_idx, weight, json.dumps(test_group_conf['metadata']))
            insert_sql.append(sql)

        async with self.db.acquire() as con:
            await con.execute('DELETE FROM "test_config" WHERE "pro_id" = $1;', int(pro_id))
            await con.execute(
                'UPDATE "problem" SET is_makefile = $1, check_type = $2, chalmeta = $3, "limit" = $4 WHERE pro_id = $5',
                is_makefile, check_type, json.dumps(chalmeta), json.dumps(limit), pro_id
            )

            if insert_sql:
                await con.execute(
                    f"""
                        INSERT INTO "test_config"
                        ("pro_id", "test_idx", "weight", "metadata")
                        VALUES {','.join(insert_sql)};
                    """
                )

        await self.db.execute("REFRESH MATERIALIZED VIEW test_valid_rate;")
        await self.rs.delete('rate')
        await self.rs.hdel('pro_rate', pro_id)
        await self.rs.publish('materialized_view_req', (await self.rs.get('materialized_view_counter')))

        return None, None

    # TODO: 把這破函數命名改一下
    def get_acct_limit(self, acct: Account = None, contest=False):
        if contest:
            return ProService.STATUS_CONTEST

        elif acct is None:
            return ProService.STATUS_ONLINE

        elif acct.is_kernel():
            return ProService.STATUS_OFFLINE

        else:
            return ProService.STATUS_ONLINE

    async def unpack_pro(self, pro_id, pack_type, pack_token):
        from services.chal import ChalConst
        def _clean_cont(prefix):
            try:
                os.remove(f"{prefix}cont.html")

            except OSError:
                pass

            try:
                os.remove(f"{prefix}cont.pdf")

            except OSError:
                pass

        if (
                pack_type != ProService.PACKTYPE_FULL
                and pack_type != ProService.PACKTYPE_CONTHTML
                and pack_type != ProService.PACKTYPE_CONTPDF
        ):
            return "Eparam", None

        if pack_type == ProService.PACKTYPE_CONTHTML:
            prefix = f"problem/{pro_id}/http/"
            _clean_cont(prefix)
            await PackService.inst.direct_copy(pack_token, f"{prefix}cont.html")

        elif pack_type == ProService.PACKTYPE_CONTPDF:
            prefix = f"problem/{pro_id}/http/"
            _clean_cont(prefix)
            await PackService.inst.direct_copy(pack_token, f"{prefix}cont.pdf")

        elif pack_type == ProService.PACKTYPE_FULL:
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
                return "Econf", None

            is_makefile = conf["compile"] == 'makefile'
            check_type = self._get_check_type(conf["check"])
            chalmeta = conf["metadata"]  # INFO: ioredir data

            ALLOW_COMPILERS = list(ChalConst.ALLOW_COMPILERS) + ['default']
            if is_makefile:
                ALLOW_COMPILERS = ['default', 'gcc', 'g++', 'clang', 'clang++']

            if "limit" in conf:
                limit = {lang: lim for lang, lim in conf["limit"].items() if lang in ALLOW_COMPILERS}
            else:
                limit = {
                    'default': {
                        'timelimit': conf["timelimit"],
                        'memlimit': conf["memlimit"] * 1024
                    }
                }

            async with self.db.acquire() as con:
                await con.execute('DELETE FROM "test_config" WHERE "pro_id" = $1;', int(pro_id))
                await con.execute(
                    'UPDATE "problem" SET is_makefile = $1, check_type = $2, chalmeta = $3, "limit" = $4 WHERE pro_id = $5',
                    is_makefile, check_type, json.dumps(chalmeta), json.dumps(limit), pro_id
                )

                insert_sql = []

                for test_idx, test_conf in enumerate(conf["test"]):
                    for i in range(len(test_conf["data"])):
                        test_conf["data"][i] = str(test_conf["data"][i])

                    metadata = {"data": test_conf["data"]}
                    insert_sql.append(f"({pro_id}, {test_idx}, {test_conf['weight']}, \'{json.dumps(metadata)}\')")

                await con.execute(
                    f"""
                        INSERT INTO "test_config"
                        ("pro_id", "test_idx", "weight", "metadata")
                        VALUES {",".join(insert_sql)}
                    """
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


class ProClassService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        ProClassService.inst = self

    async def get_pubclass(self, pubclass_id):
        async with self.db.acquire() as con:
            res = await con.fetch(
                'SELECT "pubclass_id", "name", "list" FROM "pubclass" WHERE "pubclass_id" = $1;',
                int(pubclass_id),
            )

            if len(res) != 1:
                return "Enoext", None

        return None, res[0]

    async def get_pubclass_list(self):
        async with self.db.acquire() as con:
            res = await con.fetch('SELECT "pubclass_id", "name" FROM "pubclass";')

        return None, res

    async def add_pubclass(self, pubclass_name, p_list):
        async with self.db.acquire() as con:
            res = await con.fetchrow(
                """
                    INSERT INTO "pubclass" ("name", "list")
                    VALUES ($1, $2) RETURNING "pubclass_id";
                """,
                pubclass_name,
                p_list,
            )

        return None, res[0]

    async def remove_pubclass(self, pubclass_id):
        async with self.db.acquire() as con:
            await con.execute('DELETE FROM "pubclass" WHERE "pubclass_id" = $1', int(pubclass_id))

    async def update_pubclass(self, pubclass_id, pubclass_name, p_list):
        pubclass_id = int(pubclass_id)
        async with self.db.acquire() as con:
            await con.execute(
                'UPDATE "pubclass" SET "name" = $1, "list" = $2 WHERE "pubclass_id" = $3',
                pubclass_name,
                p_list,
                pubclass_id,
            )

    async def get_priclass(self, acct_id):
        pass

    async def get_priclass_list(self, acct_id):
        pass

