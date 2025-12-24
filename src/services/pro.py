import enum
import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Sequence

from msgpack import packb, unpackb

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

class ProType(enum.IntEnum):
    BATCH = 1
    COMMUNICATION = 2
    TWOSTEP = 3
    OUTPUTONLY = 4

class ProConst:
    """
    Constants used in problem management for status codes, checker types,
    name/code length constraints, and allowed user problem status sets.
    """

    NAME_MIN = 1
    NAME_MAX = 64
    CODE_MAX = 65536

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
    PRO_STATUS_NORMAL_USER = (STATUS_ONLINE, )
    PRO_STATUS_KERNEL_USER = (STATUS_ONLINE, STATUS_HIDDEN)
    PRO_STATUS_CONTEST_USER = (STATUS_ONLINE, STATUS_CONTEST)
    PRO_STATUS_FULL = (STATUS_ONLINE, STATUS_CONTEST, STATUS_HIDDEN)

# TODO: Move this to prospec
@dataclass(slots=True)
class BaseTestdata:
    """Base class for all problem type testdata, used for type checking only."""
    testdata_id: int
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def has_tag(self, tag: str) -> bool:
        """Check if testdata has a specific tag."""
        return tag in self.metadata.get('tags', [])

    def is_system_test(self) -> bool:
        """Check if testdata is marked as system test."""
        return self.has_tag('system-test')


@dataclass(slots=True)
class SubtaskConfig:
    subtask_id: int
    testdatas: list[BaseTestdata]
    dependency_subtasks: set[int]
    rate: int
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def has_tag(self, tag: str) -> bool:
        """Check if subtask has a specific tag."""
        return tag in self.metadata.get('tags', [])

    def is_system_test(self) -> bool:
        """Check if subtask is marked as system test."""
        return self.has_tag('system-test')


@dataclass(slots=True)
class Limit:
    time: int # NOTE: ms
    memory: int # NOTE: kib
    output: int # NOTE: kib

    def __post_init__(self):
        assert self.time >= 0
        assert self.memory >= 0
        assert self.output >= 0

# TODO: Move this to prospec
@dataclass(slots=True)
class BaseConfig:
    """Base class for all problem type configs, used for type checking only."""
    pass


@dataclass(slots=True)
class ProblemConfig:
    """
    Common problem configuration shared across all problem types.

    - limits (dict[str, Limit]): Per-language time and memory limits.
        - Keys are compiler types (e.g., "gcc", "clang", "default").
            Allowed compilers can be found in `ChalConst.ALLOW_COMPILERS`.
        - Must include a "default" configuration.

    - rate_precision (int): Precision of the score (e.g., 0 for integers, 2 for 2 decimal places).

    - subtask_configs (dict[int, SubtaskConfig]): Configuration for each subtask. Each key is
    a subtask id.

    - testdatas (dict[int, Testdata]): Configuration for each testdata. Each key is
    a testdata id.

    - spec_config (BaseConfig): Problem type-specific configuration (BatchConfig, etc.)
    """
    limits: dict[str, Limit]
    subtask_configs: dict[int, SubtaskConfig]
    testdatas: dict[int, BaseTestdata]
    rate_precision: int
    spec_config: BaseConfig

    def __post_init__(self):
        # Only validate if limits is populated (allows empty dict during construction)
        if self.limits:
            assert 'default' in self.limits
        if self.rate_precision != 0:  # Allow 0 as placeholder during construction
            assert ProConst.RATE_PRECISION_MIN <= self.rate_precision <= ProConst.RATE_PRECISION_MAX

    def get_effective_testdatas(self) -> list[BaseTestdata]:
        s = set()
        for cfg in self.subtask_configs.values():
            for t in cfg.testdatas:
                s.add(t.testdata_id)

        return [self.testdatas[t_id] for t_id in s]

    def get_pretest_subtasks(self) -> dict[int, SubtaskConfig]:
        """Get subtasks without system-test tag (for contest pretest)."""
        return {
            subtask_id: subtask
            for subtask_id, subtask in self.subtask_configs.items()
            if not subtask.is_system_test()
        }

    def get_system_test_subtasks(self) -> dict[int, SubtaskConfig]:
        """Get subtasks with system-test tag."""
        return {
            subtask_id: subtask
            for subtask_id, subtask in self.subtask_configs.items()
            if subtask.is_system_test()
        }


@dataclass(slots=True)
class Problem:
    pro_id: int
    name: str
    status: int
    tags: str
    allow_submit: bool
    problem_type: int  # ProType enum value
    config: ProblemConfig | None

    def __post_init__(self):
        assert ProConst.STATUS_ONLINE <= self.status <= ProConst.STATUS_HIDDEN

class ProService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        ProService.inst = self

    async def get_pro(self, pro_id: int, allow_statuses: Sequence[int]) -> tuple[None, Problem] | ErrorType:
        from services.prospec.batch import batch_spec
        """
        Fetch problem configuration and metadata by ID, ensuring it's in the allowed status.

        Args:
            pro_id (int): The ID of the problem to fetch.
            allow_statuses (Sequence[int]): Allowed problem statuses for access.

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
                    "problem_type", "config", "limits", "rate_precision"
                    FROM "problem" WHERE "pro_id" = $1;
                """,
                pro_id,
            )
            if len(result) != 1:
                return ("Enoext", "Problem not found"), None
            result = result[0]

            name = result["name"]
            status = result["status"]
            tags = result["tags"]
            allow_submit = result["allow_submit"]
            problem_type = result["problem_type"]
            config_json = json.loads(result["config"])
            limits = json.loads(result["limits"])
            rate_precision = result["rate_precision"]

            if tags is None:
                tags = ""

            if status not in allow_statuses:
                return ("Eacces", "Permission denied"), None

            # Get testdata with new files structure
            result = await con.fetch(
                """
                    SELECT "id", "files", "metadata"
                    FROM "testdata" WHERE "pro_id" = $1;
                """,
                pro_id,
            )
            testdatas: dict[int, BaseTestdata] = {}

            # TODO: Support different problem types, for now only Batch
            if problem_type == ProType.BATCH:
                spec = batch_spec
                for id, files_json, metadata_json in result:
                    testdata = spec.parse_testdata_files(id, json.loads(files_json))
                    testdata.metadata = json.loads(metadata_json) if metadata_json else {}
                    testdatas[id] = testdata

            result = await con.fetch(
                """
                    SELECT "subtask_id", "rate", "testdatas", "dep_subtasks", "metadata"
                    FROM "subtask_config" WHERE "pro_id" = $1 ORDER BY "subtask_id" ASC;
                """,
                pro_id,
            )
            subtask_configs: dict[int, SubtaskConfig] = {}
            for subtask_id, rate, testdata_ids, dep_subtasks, metadata_json in result:
                subtask_configs[subtask_id] = SubtaskConfig(
                    subtask_id,
                    [testdatas[testdata_id] for testdata_id in testdata_ids],
                    set(dep_subtasks),
                    rate,
                    json.loads(metadata_json) if metadata_json else {},
                )

        # Parse config using ProSpec
        # TODO: Support different problem types, for now only Batch
        proconfig: ProblemConfig | None = None
        if problem_type == ProType.BATCH:
            spec = batch_spec
            spec_config = spec.from_json(config_json)

            # Build common ProblemConfig
            proconfig = ProblemConfig(
                limits={
                    compiler: Limit(**limit)
                    for compiler, limit in limits.items()
                },
                subtask_configs=subtask_configs,
                testdatas=testdatas,
                rate_precision=rate_precision,
                spec_config=spec_config,
            )

        return None, Problem(pro_id, name, status, tags, allow_submit, problem_type, proconfig)

    async def get_pro_config(self, pro_id: int):
        # TODO: get_pro_config
        pass

    async def list_pro(self, allow_pro_statuses: Sequence[int]) -> tuple[None, list[Problem]]:
        """
        List problems with statuses in `allow_pro_statuses`, with Redis caching.

        Args:
            allow_pro_statuses (Sequence[int]): List of allowed statuses.

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
                        SELECT p.pro_id, p.name, p.status, p.tags, p.allow_submit, p.problem_type
                        FROM "problem" p
                        WHERE p."status" IN ({",".join(map(str, allow_pro_statuses))})
                        ORDER BY pro_id ASC;
                    """
                )

            prolist = []
            for pro_id, name, status, tags, allow_submit, problem_type in result:
                if tags is None:
                    tags = ""

                prolist.append(
                    {
                        "pro_id": pro_id,
                        "name": name,
                        "status": status,
                        "tags": tags,
                        "allow_submit": allow_submit,
                        "problem_type": problem_type,
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

    async def update_pro_config(self, pro_id: int, problem_type: ProType, config: ProblemConfig):
        """
        Update the test configuration for a given problem.

        Args:
            pro_id (int): The ID of the problem to update.
            problem_type (ProType): The type of the problem.
            config (ProblemConfig): The problem configuration.

        Returns:
            Tuple[None, None]: Always returns (None, None) on success.

        Side Effects:
            - All existing `Challenge` records associated with this problem will be reset to
            the `NotStart` state, due to test configuration changes.
            - Related Redis cache (`rate`, `pro_rate`) will be invalidated.
        """
        from services.prospec.batch import batch_spec

        insert_subtask_config_values = []
        insert_testdatas_values = []
        for subtask_id, subtask_config in config.subtask_configs.items():
            rate = subtask_config.rate
            metadata_json = json.dumps(subtask_config.metadata if subtask_config.metadata else {})
            insert_subtask_config_values.append(
                (
                    pro_id, subtask_id, rate,
                    [testdata.testdata_id for testdata in subtask_config.testdatas],
                    subtask_config.dependency_subtasks,
                    metadata_json
                )
            )

        # TODO: Support different problem types, for now only Batch
        if problem_type == ProType.BATCH:
            spec = batch_spec
            for testdata in config.testdatas.values():
                files_json = spec.build_testdata_files(testdata)
                metadata_json = json.dumps(testdata.metadata if testdata.metadata else {})
                insert_testdatas_values.append(
                    (pro_id, testdata.testdata_id, json.dumps(files_json), metadata_json)
                )

        async with self.db.acquire() as con:
            await con.execute(
                'DELETE FROM "subtask_config" WHERE "pro_id" = $1;', int(pro_id)
            )
            await con.execute(
                'DELETE FROM "testdata" WHERE "pro_id" = $1;', int(pro_id)
            )

            # Update problem config using ProSpec
            # TODO: Support different problem types, for now only Batch
            if problem_type == ProType.BATCH:
                from services.prospec.batch import BatchConfig
                spec = batch_spec
                # Type assertion: we know spec_config is BatchConfig for BATCH type
                assert isinstance(config.spec_config, BatchConfig)
                config_json = spec.to_json(config.spec_config)

                await con.execute(
                    '''
                    UPDATE problem SET config = $1, limits = $2, rate_precision = $3
                    WHERE pro_id = $4;
                    ''',
                    json.dumps(config_json),
                    json.dumps({
                        comp: asdict(limit)
                        for comp, limit in config.limits.items()
                    }),
                    config.rate_precision,
                    pro_id,
                )

            await con.executemany(
                """INSERT INTO "subtask_config"
                    ("pro_id", "subtask_id", "rate", "testdatas", "dep_subtasks", "metadata")
                    VALUES ($1, $2, $3, $4, $5, $6);""",
                insert_subtask_config_values,
            )

            await con.executemany(
                """
                    INSERT INTO "testdata" ("pro_id", "id", "files", "metadata")
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

            # NOTE: Remove cache
            res = await con.fetch("SELECT contest_id FROM contest_problem_joints WHERE pro_id = $1;", pro_id)
            for r in res:
                contest_id = r['contest_id']

                key2 = f"pro_id_{pro_id}_contest_id_{contest_id}"
                await self.rs.hdel("pro_rate", key2)
            await self.rs.delete("rate")
            await self.rs.hdel("pro_topcoder", str(pro_id))

        return None, None

    async def unpack_pro(self, pro_id: int, pack_token: str, problem_type: ProType = ProType.BATCH):
        """
        Unpack and apply a packed problem archive by delegating to ProSpec.

        Args:
            pro_id (int): The ID of the problem to unpack into.
            pack_token (str): Token for identifying the uploaded archive.
            problem_type (ProType): Type of the problem (default: BATCH).

        Returns:
            Tuple[Optional[Tuple[str, str]], None]:
                - Error code and message if unpacking or config fails.
                - None if successful.
        """
        from services.prospec.batch import batch_spec

        # TODO: Support different problem types
        if problem_type == ProType.BATCH:
            spec = batch_spec
        else:
            return ('Enotsupport', 'Problem type not yet supported'), None

        # Delegate to ProSpec implementation
        return await spec.unpack_pro(self.db, self.rs, pro_id, pack_token)


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
