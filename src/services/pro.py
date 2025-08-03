import enum
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass

import config
from msgpack import packb, unpackb

from services.pack import PackService

ErrorType = tuple[tuple[str, str], None]

class CheckerType(enum.IntEnum):
    DIFF = 1
    DIFF_STRICT = 2
    DIFF_FLOAT4 = 3
    DIFF_FLOAT6 = 4
    DIFF_FLOAT9 = 5
    CMS_TPS_TESTLIB = 6
    STD_TESTLIB = 7
    IOREDIR = 8
    TOJ = 9

    @classmethod
    def need_build_checkers(cls):
        return [cls.CMS_TPS_TESTLIB, cls.STD_TESTLIB, cls.IOREDIR, cls.TOJ]

class SummaryType(enum.IntEnum):
    GROUPMIN = 1
    OVERWRITE = 2
    CUSTOM = 3

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

    PACKTYPE_FULL = 1
    PACKTYPE_CONTHTML = 2
    PACKTYPE_CONTPDF = 3

    OLD_STR_2_CHECKER_TYPE = {
        "diff": CheckerType.DIFF,
        "diff-strict": CheckerType.DIFF_STRICT,
        "diff-float": CheckerType.DIFF_FLOAT6,
        "ioredir": CheckerType.IOREDIR,
        "cms": CheckerType.CMS_TPS_TESTLIB,
    }


    CHECKER_TYPE_2_STR = {
        CheckerType.DIFF: "diff",
        CheckerType.DIFF_STRICT: "diff-strict",
        CheckerType.DIFF_FLOAT4: "diff-float, max error 1e-4",
        CheckerType.DIFF_FLOAT6: "diff-float, max error 1e-6",
        CheckerType.DIFF_FLOAT9: "diff-float, max error 1e-9",
        CheckerType.CMS_TPS_TESTLIB: "CMS/TPS Testlib",
        CheckerType.STD_TESTLIB: "Standard Testlib (Polygon)",
        CheckerType.IOREDIR: "IORedir (WIP)",
        CheckerType.TOJ: "TOJ (WIP)",
    }

    SUMMARY_TYPE_2_STR = {
        SummaryType.CUSTOM: "Custom",
        SummaryType.GROUPMIN: "GroupMin",
        SummaryType.OVERWRITE: "Overwrite",
    }

    # NOTE: collection for problem status
    PRO_STATUS_NORMAL_USER = [STATUS_ONLINE]
    PRO_STATUS_KERNEL_USER = [STATUS_ONLINE, STATUS_HIDDEN]
    PRO_STATUS_CONTEST_USER = [STATUS_ONLINE, STATUS_CONTEST]
    PRO_STATUS_FULL = [STATUS_ONLINE, STATUS_CONTEST, STATUS_HIDDEN]



@dataclass(slots=True)
class Testdata:
    testdata_id: int
    inputfile: str
    outputfile: str


@dataclass(slots=True)
class SubtaskConfig:
    subtask_id: int
    testdatas: list[Testdata]
    rate: int


@dataclass(slots=True)
class Limit:
    time: int # NOTE: ms
    memory: int # NOTE: kib
    output: int # NOTE: kib

    def __post_init__(self):
        assert self.time >= 0
        assert self.memory >= 0
        assert self.output >= 0

@dataclass(slots=True)
class ProblemConfig:
    """
    - has_grader (bool): Whether the problem uses a Makefile-based compilation.
    See: https://wiki.tfcis.org/TOJ#Makefile%E9%A1%8C%E7%9B%AE_(%E7%B7%A8%E8%AD%AF%E4%BA%92%E5%8B%95%E9%A1%8C)

    - chalmeta (str): For IORedir Problem
    See: https://wiki.tfcis.org/TOJ#IORedir

    - checker_type (int): One of the values defined in ProConst.CHECKER_TYPE, indicating
    the type of checker (e.g., diff, float-diff, ioredir).

    - limits (dict[str, Limit]): Per-language time and memory limits.
        - Keys are compiler types (e.g., "gcc", "clang", "default").
            Allowed compilers can be found in `ChalConst.ALLOW_COMPILERS`.
        - Must include a "default" configuration.

    - rate_precision (int): Precision of the score (e.g., 0 for integers, 2 for 2 decimal places).

    - subtask_configs (dict[int, SubtaskConfig]): Configuration for each subtask. Each key is
    a subtask id.

    - testdatas (dict[int, Testdata]): Configuration for each testdata. Each key is
    a testdata id.
    """
    chalmeta: str
    limits: dict[str, Limit]
    userprog_compile_args: str
    checker_type: CheckerType
    checker_compiler: int | None
    checker_compile_args: str
    summary_type: SummaryType
    summary_compiler: int | None
    summary_compile_args: str
    has_grader: bool
    allow_compilers: set[int]
    subtask_configs: dict[int, SubtaskConfig]
    testdatas: dict[int, Testdata]
    rate_precision: int

    def __post_init__(self):
        assert 'default' in self.limits
        assert ProConst.RATE_PRECISION_MIN <= self.rate_precision <= ProConst.RATE_PRECISION_MAX


@dataclass(slots=True)
class Problem:
    pro_id: int
    name: str
    status: int
    tags: str
    allow_submit: bool
    config: ProblemConfig | None

    def __post_init__(self):
        assert ProConst.STATUS_ONLINE <= self.status <= ProConst.STATUS_HIDDEN

class ProService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        ProService.inst = self

    async def get_pro(self, pro_id: int, allow_statuses: list[int]) -> tuple[None, Problem] | ErrorType:
        from services.chal import Compiler
        """
        Fetch problem configuration and metadata by ID, ensuring it's in the allowed status.

        Args:
            pro_id (int): The ID of the problem to fetch.
            allow_statuses (list[int]): Allowed problem statuses for access.

        Returns:
            Tuple[Optional[Tuple[str, str]], Optional[Problem]]:
                - Error code and message if any error occurs.
        """

        for status in allow_statuses:
            assert ProConst.STATUS_ONLINE <= status <= ProConst.STATUS_HIDDEN
        pro_id = int(pro_id)

        async with self.db.acquire() as con:
            result = await con.fetch(
                """
                    SELECT "name", "status", "tags", "allow_submit",
                    "allow_compilers", "userprog_compile_args",
                    "checker_type", "checker_compiler", "checker_compile_args",
                    "summary_type", "summary_compiler", "summary_compile_args",
                    "has_grader", "chalmeta", "limits", "rate_precision"
                    FROM "problem" WHERE "pro_id" = $1;
                """,
                pro_id,
            )
            if len(result) != 1:
                return ("Enoext", "Problem not found"), None
            result = result[0]

            (
                name,
                status,
                tags,
                allow_submit,
                allow_compilers,
                userprog_compile_args,
                checker_type,
                checker_compiler,
                checker_compile_args,
                summary_type,
                summary_compiler,
                summary_compile_args,
                has_grader,
                rate_precision,
                limits,
                chalmeta,
            ) = (
                result["name"],
                result["status"],
                result["tags"],
                result["allow_submit"],
                result["allow_compilers"],
                result["userprog_compile_args"],
                result["checker_type"],
                result["checker_compiler"],
                result["checker_compile_args"],
                result["summary_type"],
                result["summary_compiler"],
                result["summary_compile_args"],
                result["has_grader"],
                result["rate_precision"],
                json.loads(result["limits"]),
                json.loads(result["chalmeta"]),
            )
            if tags is None:
                tags = ""

            if checker_compiler:
                checker_compiler = Compiler(checker_compiler)
            if summary_compiler:
                summary_compiler = Compiler(summary_compiler)

            if status not in allow_statuses:
                return ("Eacces", "Permission denied"), None

            result = await con.fetch(
                """
                    SELECT "id", "inputfile", "outputfile"
                    FROM "testdata" WHERE "pro_id" = $1;
                """,
                pro_id,
            )
            testdatas: dict[int, Testdata] = {}
            for id, inputfile, outputfile in result:
                testdatas[id] = Testdata(id, inputfile, outputfile)

            result = await con.fetch(
                """
                    SELECT "subtask_id", "rate", "testdatas"
                    FROM "subtask_config" WHERE "pro_id" = $1 ORDER BY "subtask_id" ASC;
                """,
                pro_id,
            )
            subtask_configs: dict[int, SubtaskConfig] = {}
            for subtask_id, rate, testdata_ids in result:
                subtask_configs[subtask_id] = SubtaskConfig(
                    subtask_id,
                    [testdatas[testdata_id] for testdata_id in testdata_ids],
                    rate,
                )

        proconfig = ProblemConfig(
            chalmeta=chalmeta,
            limits={
                compiler: Limit(**limit)
                for compiler, limit in limits.items()
            },
            userprog_compile_args=userprog_compile_args,
            checker_type=checker_type,
            checker_compiler=checker_compiler,
            checker_compile_args=checker_compile_args,
            summary_type=summary_type,
            summary_compiler=summary_compiler,
            summary_compile_args=summary_compile_args,
            subtask_configs=subtask_configs,
            testdatas=testdatas,
            rate_precision=rate_precision,
            has_grader=has_grader,
            allow_compilers=set(map(Compiler, allow_compilers)),
        )

        return None, Problem(pro_id, name, status, tags, allow_submit, proconfig)

    async def get_pro_config(self, pro_id: int):
        # TODO: get_pro_config
        pass

    async def list_pro(self, allow_pro_statuses: list[int]) -> tuple[None, list[Problem]]:
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
            for i in range(len(prolist)):
                prolist[i] = Problem(**prolist[i], config=None)

        else:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    f"""
                        SELECT p.pro_id, p.name, p.status, p.tags, p.allow_submit
                        FROM "problem" p
                        WHERE p."status" IN ({",".join(map(str, allow_pro_statuses))})
                        ORDER BY pro_id ASC;
                    """
                )

            prolist = []
            for pro_id, name, status, tags, allow_submit in result:
                if tags is None:
                    tags = ""

                prolist.append(
                    {
                        "pro_id": pro_id,
                        "name": name,
                        "status": status,
                        "tags": tags,
                        "allow_submit": allow_submit,
                    }
                )

            await self.rs.hset("prolist", field, packb(prolist))

            for i in range(len(prolist)):
                prolist[i] = Problem(**prolist[i], config=None)


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

    async def update_pro(self, pro: Problem):
        """
        Update problem metadata such as name, status, tags, and submission permission.

        Args:
            pro_id (int): The ID of the problem to update.
            pro (Problem): The problem

        Returns:
            Tuple[Optional[Tuple[str, str]], None]:
                - Error code and message if any error occurs.
                - None if successful.
        """

        name_len = len(pro.name)
        if name_len < ProConst.NAME_MIN:
            return ("Enamemin", "Problem name too short"), None
        if name_len > ProConst.NAME_MAX:
            return ("Enamemax", "Problem name too long"), None
        if pro.status < ProConst.STATUS_ONLINE or pro.status > ProConst.STATUS_HIDDEN:
            return ("Eparam", "Invalid problem status"), None
        if pro.tags and not re.match(r"^[a-zA-Z0-9-_, ]+$", pro.tags):
            return ("Etags", "Invalid problem tag"), None

        async with self.db.acquire() as con:
            result = await con.fetch(
                """
                    UPDATE "problem"
                    SET "name" = $1, "status" = $2, "tags" = $3, "allow_submit" = $4
                    WHERE "pro_id" = $5 RETURNING "pro_id";
                """,
                pro.name, pro.status, pro.tags, pro.allow_submit, pro.pro_id
            )
            if len(result) != 1:
                return ("Enoext", "Problem not found"), None

        await self.rs.delete("prolist")

        return None, None

    async def update_pro_config(self, pro_id: int, config: ProblemConfig):
        """
        Update the test configuration (testm_conf) for a given problem.

        Args:
            pro_id (int): The ID of the problem to update.
            config (ProblemConfig): The problem configuration.

        Returns:
            Tuple[None, None]: Always returns (None, None) on success.

        Side Effects:
            - All existing `Challenge` records associated with this problem will be reset to
            the `NotStart` state, due to test configuration changes.
            - Related Redis cache (`rate`, `pro_rate`) will be invalidated.
        """

        insert_test_config_values = []
        insert_testdatas_values = []
        for subtask_id, subtask_config in config.subtask_configs.items():
            rate = subtask_config.rate
            insert_test_config_values.append(
                (pro_id, subtask_id, rate, [testdata.testdata_id for testdata in subtask_config.testdatas])
            )

        for testdata in config.testdatas.values():
            insert_testdatas_values.append(
                (pro_id, testdata.testdata_id, testdata.inputfile, testdata.outputfile)
            )

        async with self.db.acquire() as con:
            await con.execute(
                'DELETE FROM "subtask_config" WHERE "pro_id" = $1;', int(pro_id)
            )
            await con.execute(
                'DELETE FROM "testdata" WHERE "pro_id" = $1;', int(pro_id)
            )
            await con.execute(
                '''
                UPDATE problem SET allow_compilers = $1, has_grader = $2, chalmeta = $3,
                limits = $4, rate_precision = $5, userprog_compile_args = $6,
                checker_type = $7, checker_compiler = $8, checker_compile_args = $9,
                summary_type = $10, summary_compiler = $11, summary_compile_args = $12
                WHERE pro_id = $13;
                ''',
                config.allow_compilers,
                config.has_grader,
                json.dumps(config.chalmeta),
                json.dumps({
                    comp: asdict(limit)
                    for comp, limit in config.limits.items()
                }),
                config.rate_precision,
                config.userprog_compile_args,
                config.checker_type, config.checker_compiler, config.checker_compile_args,
                config.summary_type, config.summary_compiler, config.summary_compile_args,
                pro_id,
            )

            await con.executemany(
                """INSERT INTO "subtask_config"
                    ("pro_id", "subtask_id", "rate", "testdatas")
                    VALUES ($1, $2, $3, $4);""",
                insert_test_config_values,
            )

            await con.executemany(
                """
                    INSERT INTO "testdata" ("pro_id", "id", "inputfile", "outputfile")
                    VALUES ($1, $2, $3, $4);
                """,
                insert_testdatas_values,
            )

            res = await con.fetch("SELECT chal_id FROM challenge WHERE pro_id=$1;", pro_id)

            insert_testdata_values = []
            for testdata_id in config.testdatas:
                for chal_id in res:
                    insert_testdata_values.append((chal_id['chal_id'], pro_id, testdata_id))

            insert_subtask_values = []
            for subtask_id in config.subtask_configs:
                for chal_id in res:
                    insert_subtask_values.append((chal_id['chal_id'], pro_id, subtask_id))

            for chal_id in res:
                await con.execute('UPDATE total_result SET state=DEFAULT, time=DEFAULT, memory=DEFAULT, rate=DEFAULT WHERE chal_id=$1;',
                                  chal_id['chal_id'])

            await con.executemany('INSERT INTO subtask_result (chal_id, pro_id, subtask_id) VALUES ($1, $2, $3);', insert_subtask_values)
            await con.executemany('INSERT INTO testdata_result (chal_id, pro_id, id) VALUES ($1, $2, $3);', insert_testdata_values)

            await self.rs.delete("rate")

            res = await con.fetch("SELECT contest_id FROM contest_problem_joints WHERE pro_id = $1;", pro_id)
            for r in res:
                contest_id = r['contest_id']

                key2 = f"pro_id_{pro_id}_contest_id_{contest_id}"
                await self.rs.hdel("pro_rate", key2)
            await self.rs.delete("rate")

        return None, None

    async def unpack_pro(self, pro_id: int, pack_token: str):
        """
        Unpack and apply a packed problem archive.
        If failed, this function will call PackService.inst.clear() to clear tmp file and clear problem/{pro_id}.

        Args:
            pro_id (int): The ID of the problem to unpack into.
            pack_token (str): Token for identifying the uploaded archive.

        Returns:
            Tuple[Optional[Tuple[str, str]], None]:
                - Error code and message if unpacking or config fails.
                - None if successful.
        """

        from services.chal import Compiler, ChalConst

        failed = True
        try:
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

            has_grader = False
            if "compile" in conf:
                has_grader = conf["compile"] == "makefile"
            elif "has_grader" in conf:
                has_grader = conf["has_grader"]

            if "limit" in conf:
                limits = {}
                for compiler_type, conf_limit in conf["limit"].items():
                    if compiler_type in ChalConst.OLD_STR_2_COMPILER:
                        compiler_type = ChalConst.OLD_STR_2_COMPILER[compiler_type]
                    elif compiler_type != "default":
                        continue

                    limit = Limit(0, 0, 0)
                    try:
                        limit.time = max(int(conf_limit["timelimit"]), 0)
                        limit.memory = max(int(conf_limit["memlimit"]), 0)
                        limit.output = 65536
                    except ValueError:
                        continue

                    limits[compiler_type] = limit

                if "default" not in limits:
                    return ("Econf", "Problem limit config require default value"), None

            elif "timelimit" in conf and "memlimit" in conf:
                try:
                    limits = {
                        "default": Limit(int(conf["timelimit"]), int(conf["memlimit"]), 65536)
                    }
                except ValueError:
                    return ("Econf", "Problem limit config have invalid value"), None
            else:
                return (
                    "Econf",
                    "Problem config require limit or timelimit/memlimit",
                ), None

            chalmeta = conf["metadata"]  # INFO: ioredir data

            subtask_configs: dict[int, SubtaskConfig] = {}
            testdatas: dict[int, Testdata] = {}
            testdata_name_2_id: dict[str, int] = {}
            testdata_id_counter = 0
            for test_idx, test_conf in enumerate(conf["test"]):
                for t in test_conf["data"]:
                    if t not in testdata_name_2_id:
                        t = os.path.basename(str(t))
                        testdata_name_2_id[t] = testdata_id_counter
                        testdatas[testdata_id_counter] = Testdata(testdata_id_counter, f"{t}.in", f"{t}.out")
                        testdata_id_counter += 1

                subtask_configs[test_idx] = SubtaskConfig(test_idx, [], int(test_conf["weight"]))


            for test_idx, test_conf in enumerate(conf["test"]):
                for t in test_conf["data"]:
                    t = os.path.basename(str(t))
                    subtask_configs[test_idx].testdatas.append(testdatas[testdata_name_2_id[t]])


            if has_grader:
                allow_compilers = {Compiler.CLANGPP, Compiler.GPP}
            else:
                allow_compilers = {v for v in Compiler}
            checker_type = ProConst.OLD_STR_2_CHECKER_TYPE[conf["check"]]
            proconfig = ProblemConfig(chalmeta, limits, "",
                                      checker_type, Compiler.GPP, "",
                                      SummaryType.GROUPMIN, Compiler.GPP, "",
                                      has_grader, allow_compilers, subtask_configs, testdatas, rate_precision=0)
            failed = False

        finally:
            # NOTE: Like golang defer
            if failed and os.path.exists(f"problem/{pro_id}"):
                shutil.rmtree(f"problem/{pro_id}")
            await PackService.inst.clear(pack_token)

        await self.update_pro_config(pro_id, proconfig)
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
            res = res[0]

        return None, res

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
            result: str = await con.execute(
                'DELETE FROM "proclass" WHERE "proclass_id" = $1', int(proclass_id)
            )
            affected_row_cnt = int(result.split(" ")[1])  # NOTE: DELETE \d+
            if affected_row_cnt == 0:
                return ("Enoext", "Bulletin not found"), None

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
