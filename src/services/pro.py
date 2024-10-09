import datetime
import json
import os
import re
from collections import OrderedDict

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
                    SELECT "name", "status", "tags", "allow_submit"
                    FROM "problem" WHERE "pro_id" = $1 AND "status" <= $2;
                """,
                pro_id,
                max_status,
            )
            if len(result) != 1:
                return "Enoext", None
            result = result[0]

            name, status, tags, allow_submit = (
                result["name"],
                result["status"],
                result["tags"],
                result["allow_submit"],
            )

            result = await con.fetch(
                """
                    SELECT "test_idx", "compile_type", "score_type",
                    "check_type", "timelimit", "memlimit", "weight", "metadata", "chalmeta"
                    FROM "test_config" WHERE "pro_id" = $1 ORDER BY "test_idx" ASC;
                """,
                pro_id,
            )
            if len(result) == 0:
                return "Econf", None

        testm_conf = OrderedDict()
        for (
                test_idx,
                comp_type,
                score_type,
                check_type,
                timelimit,
                memlimit,
                weight,
                metadata,
                chalmeta,
        ) in result:
            testm_conf[test_idx] = {
                "comp_type": comp_type,
                "score_type": score_type,
                "check_type": check_type,
                "timelimit": timelimit,
                "memlimit": memlimit,
                "weight": weight,
                "chalmeta": json.loads(chalmeta),
                "metadata": json.loads(metadata),
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

    # TODO: Too many branch
    # TODO: Too many local var
    # TODO: Too many statement
    async def list_pro(self, acct: Account = None, is_contest=False, state=False):
        from services.chal import ChalConst

        if acct is None:
            max_status = ProService.STATUS_ONLINE
            isguest = True
            isadmin = False

        else:
            max_status = self.get_acct_limit(acct, contest=is_contest)
            isguest = acct.is_guest()
            isadmin = acct.is_kernel()

        statemap = {}
        if state is True and isguest is False:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    """
                        SELECT "problem"."pro_id",
                        MIN("challenge_state"."state") AS "state"
                        FROM "challenge"
                        INNER JOIN "challenge_state"
                        ON "challenge"."chal_id" = "challenge_state"."chal_id" AND "challenge"."acct_id" = $1
                        INNER JOIN "problem"
                        ON "challenge"."pro_id" = "problem"."pro_id"
                        WHERE "problem"."status" <= $2
                        GROUP BY "problem"."pro_id"
                        ORDER BY "pro_id" ASC;
                    """,
                    int(acct.acct_id),
                    max_status,
                )

            statemap = {pro_id: state for pro_id, state in result}

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

        for pro in prolist:
            pro_id = pro["pro_id"]
            pro["state"] = statemap.get(pro_id)

            if isguest:
                pro["tags"] = ""

            elif not isadmin:
                if pro["state"] != ChalConst.STATE_AC:
                    pro["tags"] = ""

        return None, prolist

    # TODO: Too many args
    async def add_pro(self, name, status, pack_token):
        name_len = len(name)
        if name_len < ProService.NAME_MIN:
            return "Enamemin", None
        if name_len > ProService.NAME_MAX:
            return "Enamemax", None
        del name_len
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

            _, _ = await self.unpack_pro(pro_id, ProService.PACKTYPE_FULL, pack_token)

            await con.execute("REFRESH MATERIALIZED VIEW test_valid_rate;")

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

    async def update_testcases(self, pro_id, testm_conf):
        with open(f'problem/{pro_id}/conf.json', 'r') as f:
            conf_json = json.load(f)

        for test_idx, test_conf in testm_conf.items():
            async with self.db.acquire() as con:
                result = await con.fetch(
                    """
                        UPDATE "test_config"
                        SET "metadata" = $1
                        WHERE "pro_id" = $2 AND "test_idx" = $3 RETURNING "pro_id";
                    """,
                    json.dumps(test_conf['metadata']),
                    int(pro_id),
                    test_idx
                )
                if len(result) == 0:
                    return "Enoext", None

                conf_json['test'][test_idx]['data'] = test_conf['metadata']['data']

        with open(f'problem/{pro_id}/conf.json', 'w') as f:
            f.write(json.dumps(conf_json))

        return None, None

    async def update_limit(self, pro_id, timelimit, memlimit):
        if timelimit <= 0:
            return "Etimelimitmin", None
        if memlimit <= 0:
            return "Ememlimitmin", None

        memlimit = memlimit * 1024

        async with self.db.acquire() as con:
            result = await con.fetch(
                """
                    UPDATE "test_config"
                    SET "timelimit" = $1, "memlimit" = $2
                    WHERE "pro_id" = $3 RETURNING "pro_id";
                """,
                int(timelimit),
                int(memlimit),
                int(pro_id),
            )
        if len(result) == 0:
            return "Enoext", None

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
                # INFO: 正式上線請到config.py修改成正確路徑
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

            comp_type = conf["compile"]
            score_type = conf["score"]
            check_type = conf["check"]
            timelimit = conf["timelimit"]
            memlimit = conf["memlimit"] * 1024
            chalmeta = conf["metadata"]  # INFO: ioredir data

            async with self.db.acquire() as con:
                await con.execute('DELETE FROM "test_config" WHERE "pro_id" = $1;', int(pro_id))

                for test_idx, test_conf in enumerate(conf["test"]):
                    metadata = {"data": test_conf["data"]}

                    await con.execute(
                        """
                            INSERT INTO "test_config"
                            ("pro_id", "test_idx", "compile_type", "score_type", "check_type",
                            "timelimit", "memlimit", "weight", "metadata", "chalmeta")
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10);
                        """,
                        int(pro_id),
                        int(test_idx),
                        comp_type,
                        score_type,
                        check_type,
                        int(timelimit),
                        int(memlimit),
                        int(test_conf["weight"]),
                        json.dumps(metadata),
                        json.dumps(chalmeta),
                    )

        return None, None


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

