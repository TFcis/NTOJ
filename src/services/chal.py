from dataclasses import dataclass
import datetime
import enum
import decimal
from typing import Sequence
import logging

from services.pro import ProService, ProConst, ProblemConfig

logger = logging.getLogger("tornado.application")

class Compiler(enum.IntEnum):
    GCC = 1
    CLANG = 2
    GPP = 3
    CLANGPP = 4
    RUST = 5
    PYTHON3 = 6
    JAVA = 7
    ASMC = 8
    ASMCPP = 9

@dataclass(slots=True, frozen=True)
class CompilerInfo:
    compiler: Compiler
    grader_name: str
    version_name: str
    short_name: str
    source_ext: str

COMPILER_INFOS: list[CompilerInfo] = [None] * (max(v for v in Compiler) + 1)
COMPILER_INFOS[Compiler.GCC] = CompilerInfo(Compiler.GCC, "c", "GCC 14.2.0 GNU11", "gcc", "c")
COMPILER_INFOS[Compiler.CLANG] = CompilerInfo(Compiler.CLANG, "c", "Clang 19.1.7 C11", "clang", "c")
COMPILER_INFOS[Compiler.GPP] = CompilerInfo(Compiler.GPP, "cpp", "G++ 14.2.0 GNU++17", "g++", "cpp")
COMPILER_INFOS[Compiler.CLANGPP] = CompilerInfo(Compiler.CLANGPP, "cpp", "Clang++ 19.1.7 C++17", "clang++", "cpp")
COMPILER_INFOS[Compiler.RUST] = CompilerInfo(Compiler.RUST, "rust", "Rustc 1.85", "rust", "rs")
COMPILER_INFOS[Compiler.PYTHON3] = CompilerInfo(Compiler.PYTHON3, "python", "CPython 3.13.5", "python3", "py")
COMPILER_INFOS[Compiler.JAVA] = CompilerInfo(Compiler.JAVA, "java", "OpenJDK 21.0.11", "java", "java")
COMPILER_INFOS[Compiler.ASMC] = CompilerInfo(Compiler.ASMC, "asm", "Gas x86_64 Linux 2.44 w/ libc", "asmc", "s")
COMPILER_INFOS[Compiler.ASMCPP] = CompilerInfo(Compiler.ASMCPP, "asm", "Gas x86_64 Linux 2.44 w/ libstdc++", "asmcpp", "s")

class ChalConst:
    STATE_AC = 1
    STATE_PC = 2
    STATE_WA = 3
    STATE_RE = 4
    STATE_RESIG = 5
    STATE_TLE = 6
    STATE_MLE = 7
    STATE_OLE = 8
    STATE_CE = 9
    STATE_CLE = 10
    STATE_ERR = 11
    STATE_JE = 12
    STATE_JUDGE = 100
    STATE_NOTSTARTED = 101
    STATE_SKIPPED = 102
    STATE_REJECTED = 103

    STATE_STR = {
        STATE_AC: 'AC',
        STATE_PC: 'PC',
        STATE_WA: 'WA',
        STATE_RE: 'RE',
        STATE_RESIG: 'RE(SIG)',
        STATE_TLE: 'TLE',
        STATE_MLE: 'MLE',
        STATE_CE: 'CE',
        STATE_CLE: 'CLE',
        STATE_OLE: 'OLE',
        STATE_JE: 'JE',
        STATE_ERR: 'IE',
        STATE_JUDGE: 'Challenging',
        STATE_NOTSTARTED: 'Not Started',
        STATE_SKIPPED: 'SP',
        STATE_REJECTED: 'RJ'
    }

    STATE_LONG_STR = {
        STATE_AC: 'Accepted',
        STATE_PC: 'Partial Correct',
        STATE_WA: 'Wrong Answer',
        STATE_RE: 'Runtime Error',
        STATE_RESIG: 'Runtime Error (Killed by signal)',
        STATE_TLE: 'Time Limit Exceed',
        STATE_MLE: 'Memory Limit Exceed',
        STATE_OLE: 'Output Limit Exceed',
        STATE_CE: 'Compile Error',
        STATE_CLE: 'Compilation Limit Exceed',
        STATE_ERR: 'Internal Error',
        STATE_JE: 'Judge Error',
        STATE_JUDGE: 'Challenging',
        STATE_NOTSTARTED: 'Not Started',
        STATE_SKIPPED: 'Skipped',
        STATE_REJECTED: 'Rejected'
    }

    OLD_STR_2_COMPILER = {
        "g++": Compiler.GPP,
        "clang++": Compiler.CLANGPP,
        "gcc": Compiler.GCC,
        "clang": Compiler.CLANG,
        "rustc": Compiler.RUST,
        "python3": Compiler.PYTHON3,
        "java": Compiler.JAVA,
        "asmc": Compiler.ASMC,
        "asmcpp": Compiler.ASMCPP,
    }

    NORMAL_PRI = 0
    CONTEST_PRI = 1
    CONTEST_REJUDGE_PRI = 2
    NORMAL_REJUDGE_PRI = 3

class MessageType(enum.IntEnum):
    NONE = 1
    TEXT = 2
    HTML = 3

@dataclass(slots=True)
class TestdataResult:
    """
    - 'testdata_id' (int): Testdata result id.
    - 'state' (int): Challenge state, between ChalConst.STATE_AC and ChalConst.STATE_NOTSTARTED.
    - 'time' (int): Total time in milliseconds.
    - 'memory' (int): Memory usage in kilobytes.
    - 'message' (str): Message from checker
    - 'message_type' (MessageType): Message type

    """
    testdata_id: int
    state: int
    time: int
    memory: int
    message: str
    message_type: MessageType

    def reset(self):
        self.state = ChalConst.STATE_NOTSTARTED
        self.time = 0
        self.memory = 0
        self.message = ""
        self.message_type = MessageType.NONE

@dataclass(slots=True)
class SubtaskResult:
    """
    - 'subtask_id' (int): Subtask result id.
    - 'state' (int): State, between ChalConst.STATE_AC and ChalConst.STATE_NOTSTARTED.
    - 'time' (int): Time in milliseconds.
    - 'memory' (int): Memory usage in kilobytes.
    - 'rate' (decimal.Decimal), rounded by problem.rate_precision
    """
    subtask_id: int
    state: int
    time: int
    memory: int
    rate: decimal.Decimal

    def __post_init__(self):
        assert ChalConst.STATE_AC <= self.state <= ChalConst.STATE_REJECTED
        assert self.time >= 0
        assert self.memory >= 0

    def reset(self):
        self.state = ChalConst.STATE_NOTSTARTED
        self.time = 0
        self.memory = 0
        self.rate = decimal.Decimal()

@dataclass(slots=True)
class TotalResult:
    """
    - 'state' (int): Challenge state, between ChalConst.STATE_AC and ChalConst.STATE_NOTSTARTED.
    - 'time' (int): Max time in milliseconds.
    - 'memory' (int): Total Memory usage in kilobytes.
    - 'rate' (decimal.Decimal): rounded by problem.rate_precision
    - 'message' (str): Message from compiler, judge or custom summary
    - 'message_type' (MessageType): Message type
    """
    state: int
    time: int
    memory: int
    rate: decimal.Decimal
    message: str
    message_type: MessageType

    def __post_init__(self):
        assert ChalConst.STATE_AC <= self.state <= ChalConst.STATE_REJECTED
        assert self.time >= 0
        assert self.memory >= 0

    def reset(self):
        self.state = ChalConst.STATE_NOTSTARTED
        self.time = 0
        self.memory = 0
        self.rate = decimal.Decimal()
        self.message = ""
        self.message_type = MessageType.NONE

@dataclass(slots=True)
class Challenge:
    chal_id: int
    pro_id: int
    acct_id: int
    contest_id: int
    acct_name: str
    compiler_type: Compiler
    timestamp: datetime.datetime
    total_result: TotalResult | None
    subtask_results: dict[int, SubtaskResult] | None
    testdata_results: dict[int, TestdataResult] | None

@dataclass
class ChalSearchingParam:
    """
    A parameter container for building SQL WHERE clauses when filtering challenges.

    Attributes:
        pro (list[int] | None): A list of problem IDs to filter.
            - If None: no filter is applied.
            - If empty list: filters with `pro_id IS NULL`, which effectively excludes all challenges.

        acct (list[int] | None): A list of account IDs to filter.
            - If None: no filter is applied.
            - If empty list: filters with `acct_id IS NULL`, which effectively excludes all challenges.

        state (int | None): Challenge state to filter.
            - If 0 or None: no filtering.
            - Other values: exact match (e.g., `ChalConst.STATE_AC`, `ChalConst.STATE_WA`, etc.).
            - See `ChalConst.STATE_*` for available state constants.

        compiler (int | Compiler): Compiler type to filter.
            - If -1: no filtering is applied.
            - Otherwise, matches the exact compiler number.
            - Valid values are defined in `services.chal.Compiler`.

        allow_pro_statuses (Sequence[int] | None): A list of allowed problem statuses to include.
            - If None or empty: defaults to `[ProConst.STATUS_ONLINE]` only.
            - Otherwise: filters by `problem.status IN (...)`.
            - Valid values are defined in the range `ProConst.STATUS_ONLINE` to `ProConst.STATUS_HIDDEN`.

        contest (int): Contest ID to filter. Defaults to 0.
            - If set to 0: matches only non-contest challenges.
            - Otherwise: filters by contest ID.
    """

    pro: list[int] | None
    acct: list[int] | None
    state: int | None
    compiler: int | Compiler
    allow_pro_statuses: Sequence[int] | None
    contest: int = 0

    def get_sql_query_str(self):
        """
        Constructs the SQL query string fragment based on the parameter values.

        Returns:
            str: A SQL condition string suitable for use in a WHERE clause.
        """

        query = [' ']
        if self.pro is not None:
            if len(self.pro):
                query.append(f' AND "challenge"."pro_id" IN ({",".join(map(str, self.pro))}) ')
            else:
                query.append(' AND "challenge"."pro_id" IS NULL ')

        if self.acct is not None:
            if len(self.acct):
                query.append(f' AND "challenge"."acct_id" IN ({",".join(map(str, self.acct))}) ')
            else:
                query.append(' AND "challenge"."acct_id" IS NULL ')

        if self.state != 0:
            query.append(f' AND "total_result"."state" = {self.state} ')

        if self.compiler != -1:
            query.append(f' AND "challenge"."compiler_type"=\'{self.compiler}\' ')

        if self.contest != 0:
            query.append(f' AND "challenge"."contest_id"={self.contest} ')
        else:
            query.append(' AND "challenge"."contest_id"=0 ')

        if not self.allow_pro_statuses:
            query.append(f' AND "problem"."status" IN ({",".join(map(str, (ProConst.PRO_STATUS_NORMAL_USER,)))}) ')
        else:
            query.append(f' AND "problem"."status" IN ({",".join(map(str, self.allow_pro_statuses))}) ')

        return ''.join(query)


class ChalSearchingParamBuilder:
    """
    A builder class for incrementally constructing a `ChalSearchingParam` instance
    using a fluent interface.

    Example:
        builder = ChalSearchingParamBuilder()
        param = (
            builder.pro([756, 1015, 1016, 1017])
                   .acct([3227, 6057, 8199, 9787])
                   .state(ChalConst.STATE_AC)
                   .compiler(Compiler.GPP)
                   .pro_statuses([ProConst.STATUS_ONLINE, ProConst.STATUS_HIDDEN])
                   .contest(0)
                   .build()
        )

    Notes:
        - If `pro([])` or `acct([])` is passed an empty list,
          the resulting SQL will include `IS NULL` filters,
          which will **exclude all challenges**.
        - `compiler` values must match one of `ChalConst.COMPILER_NAME`.
        - `state` values should be selected from `ChalConst.STATE_*`.
        - If `pro_statuses()` is not called, only problems with `ProConst.STATUS_ONLINE` are included by default.
          You can override this to include more statuses (e.g., `ProConst.STATUS_HIDDEN`).
    """

    def __init__(self):
        self.param = ChalSearchingParam(None, None, 0, -1, ProConst.PRO_STATUS_NORMAL_USER, 0)

    def pro(self, pro: list[int] | None):
        """Sets the list of problem IDs to filter."""
        self.param.pro = pro
        return self

    def acct(self, acct: list[int] | None):
        """Sets the list of account IDs to filter."""
        self.param.acct = acct
        return self

    def state(self, state: int | None):
        """Sets the challenge state to filter."""
        if state is None:
            self.param.state = 0
        else:
            self.param.state = state
        return self

    def compiler(self, compiler: int | Compiler):
        """Sets the compiler type to filter."""
        if compiler != -1:
            self.param.compiler = compiler
        return self

    def contest(self, contest: int | None):
        """Sets the contest ID to filter."""
        if contest is not None:
            self.param.contest = contest
        return self

    def pro_statuses(self, pro_statuses: Sequence[int]):
        """
        Sets the allowed problem statuses for filtering.

        Args:
            pro_statuses (Sequence[int]): List of `ProConst.STATUS_*` values to include.

        Raises:
            AssertionError: If any status is outside the valid range
                            `ProConst.STATUS_ONLINE` to `ProConst.STATUS_HIDDEN`.
        """
        for status in pro_statuses:
            assert ProConst.STATUS_ONLINE <= status <= ProConst.STATUS_HIDDEN
        self.param.allow_pro_statuses = pro_statuses

    def build(self) -> ChalSearchingParam:
        """Returns the constructed `ChalSearchingParam` object."""
        return self.param

ErrorType = tuple[tuple[str, str], None]

class ChalService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs

        ChalService.inst = self

    async def add_chal(self, pro_id: int, acct_id: int, contest_id: int, compiler_type: Compiler, code: str, problem_type: int) -> tuple[None, int] | ErrorType:
        """
        Add a new challenge entry and save the submitted source code.

        Args:
            pro_id (int): Problem ID.
            acct_id (int): Account ID (user submitting the challenge).
            contest_id (int): Contest ID.
            compiler_type (Compiler): Compiler type.
            code (str): Source code content as string.
            problem_type (int): Problem type (from ProType enum).

        Returns:
            tuple[Optional[tuple[str, str]], Optional[int]]:
                On success, (None, chal_id).
                On failure, (error_code, None).
        """
        from services.pro import ProType
        from services.prospec.batch import batch_spec

        pro_id = int(pro_id)
        acct_id = int(acct_id)

        _, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)

        # Dispatch to ProSpec
        # TODO: Support different problem types, for now only Batch
        if problem_type == ProType.BATCH:
            spec = batch_spec
            return await spec.add_chal(
                self.db, self.rs, pro_id, acct_id, contest_id,
                compiler_type, code, pro.config
            )

        return ('Eunk', 'Unsupported problem type'), None

    async def reset_chal(self, chal_id: int) -> tuple[None | str, None | str]:
        # TODO: docstring
        """

        Args:
            chal_id (int): Challenge ID to reset.

        Returns:
            tuple[Optional[str], Optional[str]]:
                On success, (None, None).
                On failure, (error_code, error_message).
        """

        chal_id = int(chal_id)
        try:
            async with self.db.acquire() as con:
                async with con.transaction():
                    await con.execute(
                        '''
                            UPDATE total_result SET state=DEFAULT, time=DEFAULT, memory=DEFAULT, rate=DEFAULT,
                                                    message=DEFAULT, message_type=DEFAULT WHERE chal_id=$1;
                        ''',
                        chal_id
                    )

                    await con.execute(
                        '''
                            UPDATE subtask_result SET state=$1, time=DEFAULT, memory=DEFAULT, rate=DEFAULT WHERE chal_id=$2;
                        ''',
                        ChalConst.STATE_NOTSTARTED, chal_id
                    )

                    await con.execute(
                        '''
                            UPDATE testdata_result SET state=$1, time=DEFAULT, memory=DEFAULT,
                            message=DEFAULT, message_type=DEFAULT WHERE chal_id=$2;
                        ''',
                        ChalConst.STATE_NOTSTARTED, chal_id
                    )
        except Exception as e:
            logger.error(f"Error resetting challenge {chal_id}: {e}", exc_info=True)
            return ('Eunk', 'Unknown error')

        return None, None

    async def get_subtask_results(self, chal_id: int) -> tuple[None | tuple[str, str], dict[int, SubtaskResult] | None]:
        """
        Retrieve detailed subtask results of a challenge.

        Args:
            chal_id (int): Challenge ID.

        Returns:
            tuple[Optional[tuple[str, str]], Optional[dict[int, SubtaskResult]]:
                On success, (None, dict[int, SubtaskResult]) where each dict represents a subtask.
                On failure, (error_code, None).
        """
        chal_id = int(chal_id)
        try:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        SELECT subtask_result.subtask_id, state, time, memory,
                        ROUND(subtask_result.rate, problem.rate_precision)
                        FROM subtask_result
                        INNER JOIN problem
                        ON subtask_result.pro_id = problem.pro_id
                        WHERE "chal_id" = $1 ORDER BY "subtask_id" ASC;
                    ''',
                    chal_id,
                )
        except Exception as e:
            logger.error(f"Error fetching subtask results for challenge {chal_id}: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None

        subtask_results: dict[int, SubtaskResult] = {}
        for subtask_id, state, time, memory, rate in result:
            subtask_results[subtask_id] = SubtaskResult(subtask_id, state, int(time), int(memory), decimal.Decimal(rate))

        return None, subtask_results

    async def get_testdata_results(self, chal_id: int) -> tuple[None | tuple[str, str], dict[int, TestdataResult] | None]:
        """
        Retrieve detailed testdata results of a challenge.

        Args:
            chal_id (int): Challenge ID.

        Returns:
            tuple[Optional[tuple[str, str]], Optional[dict[int, TestdataResult]]:
                On success, (None, dict[int, TestdataResult]) where each dict represents a testdata.
                On failure, (error_code, None).
        """
        chal_id = int(chal_id)
        try:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        SELECT id, state, time, memory, message, message_type
                        FROM testdata_result WHERE chal_id = $1 ORDER BY id;
                    ''',
                    chal_id
                )
        except Exception as e:
            logger.error(f"Error fetching testdata results for challenge {chal_id}: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None

        testdata_results: dict[int, TestdataResult] = {}
        for testdata_id, state, time, memory, message, message_type in result:
            testdata_results[testdata_id] = TestdataResult(testdata_id, state, time, memory, message, MessageType(message_type))

        return None, testdata_results


    async def get_chal(self, chal_id: int, with_result=False) -> tuple[None, Challenge] | ErrorType:
        """
        Retrieve challenge info with optional test details.

        Args:
            chal_id (int): Challenge ID.
            with_test (bool): Whether to include detailed results.

        Returns:
            tuple[Optional[tuple[str, str]], Optional[Challenge]]:
                On success, (None, Challenge)
                On failure, (error_code, None).
        """

        chal_id = int(chal_id)
        try:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        SELECT "challenge"."pro_id", "challenge"."acct_id",
                        "challenge"."timestamp", "challenge"."compiler_type", "challenge"."contest_id", "account"."name" AS "acct_name"
                        FROM "challenge"
                        INNER JOIN "account"
                        ON "challenge"."acct_id" = "account"."acct_id"
                        WHERE "chal_id" = $1;
                    ''',
                    chal_id,
                )
        except Exception as e:
            logger.error(f"Error fetching challenge {chal_id}: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None
        if len(result) != 1:
            return ('Enoext', 'Challenge Not Found'), None
        result = result[0]

        pro_id, acct_id, timestamp, compiler_type, contest_id, acct_name = (
            result['pro_id'],
            result['acct_id'],
            result['timestamp'],
            result['compiler_type'],
            result['contest_id'],
            result['acct_name'],
        )

        subtask_results = None
        testdata_results = None
        total_results = None
        if with_result:
            _, subtask_results = await self.get_subtask_results(chal_id)
            _, testdata_results = await self.get_testdata_results(chal_id)
            _, total_results = await self.get_total_result(chal_id)

        return None, Challenge(chal_id, pro_id, acct_id, contest_id, acct_name, compiler_type,
                               timestamp, total_results, subtask_results, testdata_results)

    async def emit_chal(self, chal_id: int, pro_config: ProblemConfig, compiler_type: Compiler, priority: int, problem_type: int, skip_nonac: bool=False, include_system_test: bool=True) -> tuple[None, None] | ErrorType:
        """
        Create and submit tests for a challenge based on the test metadata configuration,
        then send the challenge to the judging cluster.

        Args:
            chal_id (int): Challenge ID.
            pro_config (ProblemConfig): Problem configuration.
            compiler_type (Compiler): Compiler type.
            priority (int): Priority level (within ChalConst.NORMAL_PRI and ChalConst.NORMAL_REJUDGE_PRI).
            problem_type (int): Problem type (from ProType enum).
            skip_nonac (bool): Skip the remaining testdata in the task if any of the testdata got non-AC or PC
            include_system_test (bool): Whether to include system-test tagged testdatas/subtasks (default True for backward compatibility)

        Returns:
            tuple[None, None]: Always returns (None, None) on completion.
        """
        from services.pro import ProType
        from services.prospec.batch import batch_spec

        assert ChalConst.NORMAL_PRI <= priority <= ChalConst.NORMAL_REJUDGE_PRI

        chal_id = int(chal_id)

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "acct_id", "pro_id", "contest_id" FROM "challenge"
                    WHERE "chal_id" = $1;
                ''',
                chal_id,
            )
        if len(result) != 1:
            return ('Enoext', 'Challenge not found'), None
        result = result[0]

        acct_id, pro_id, contest_id = int(result['acct_id']), int(result['pro_id']), int(result['contest_id'])

        # TODO: Support different problem types, for now only Batch
        if problem_type == ProType.BATCH:
            spec = batch_spec
            return await spec.emit_chal(
                self.db, self.rs, chal_id, pro_id, acct_id, contest_id,
                compiler_type, pro_config, priority, skip_nonac, include_system_test
            )

        return ('Eunk', 'Unsupported problem type'), None

    async def list_chal(self, off: int, num: int, flt: ChalSearchingParam) -> tuple[None | tuple[str, str], list[Challenge] | None]:
        """
        List challenges with filtering, pagination, and joined related info.

        Args:
            off (int): Offset for pagination.
            num (int): Number of challenges to return.
            flt (ChalSearchingParam): Filter parameters.

        Returns:
            tuple[None | tuple[str, str], list[Challenge] | None]:
                On success, returns (None, list[Challenge]) but Challenge without subtask_results and testdata_results:
                On failure, returns (error_code, None).
        """
        fltquery = flt.get_sql_query_str()

        try:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    f'''
                        SELECT "challenge"."chal_id", "challenge"."pro_id", "challenge"."acct_id", "challenge"."contest_id",
                        "challenge"."compiler_type", "challenge"."timestamp", "account"."name" AS "acct_name",
                        "total_result"."state", "total_result"."time", "total_result"."memory",
                        ROUND("total_result"."rate", problem.rate_precision), "total_result"."message", "total_result"."message_type"
                        FROM "challenge"
                        INNER JOIN "account"
                        ON "challenge"."acct_id" = "account"."acct_id"
                        INNER JOIN "problem"
                        ON "challenge"."pro_id" = "problem"."pro_id"
                        INNER JOIN "total_result"
                        ON "challenge"."chal_id" = "total_result"."chal_id"
                        WHERE 1=1 {fltquery}
                        ORDER BY "challenge"."chal_id" DESC OFFSET {off} LIMIT {num};
                    '''
                )
        except Exception as e:
            logger.error(f"Error listing challenges with offset {off}, num {num}, filter {flt}: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None

        challist: list[Challenge] = []
        for chal_id, pro_id, acct_id, contest_id, compiler_type, timestamp, acct_name, state, time, memory, rate, message, message_type in result:
            challist.append(Challenge(chal_id, pro_id, acct_id, contest_id, acct_name,
                                      compiler_type, timestamp, subtask_results=None, testdata_results=None,
                                      total_result=TotalResult(state, time, memory, rate, message, message_type)))
        return None, challist

    async def get_total_result(self, chal_id: int) -> tuple[None, TotalResult] | tuple[tuple[str, str], None]:
        """
        Retrieve the aggregated state of a challenge.

        Args:
            chal_id (int): The ID of the challenge to retrieve.

        Returns:
            tuple[Optional[tuple[str, str]], Optional[Challenge]]:
                On success, returns (None, Challenge) but without subtask_results:
                On failure (e.g., challenge not found), returns (error_code, None).
        """

        chal_id = int(chal_id)

        try:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        SELECT
                            cs.state,
                            cs.time,
                            cs.memory,
                            ROUND(cs.rate, p.rate_precision) AS rate,
                            cs.message,
                            cs.message_type
                        FROM
                            challenge c
                        INNER JOIN
                            total_result cs ON c.chal_id = cs.chal_id
                        INNER JOIN
                            problem p ON p.pro_id = c.pro_id
                        WHERE
                            cs.chal_id = $1;
                    ''',
                    chal_id,
                )
        except Exception as e:
            logger.error(f"Error fetching total result for challenge {chal_id}: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None

        if len(result) != 1:
            return ('Enoext', 'Challenge not found'), None
        result = result[0]

        return None, TotalResult(result['state'], result['time'], result['memory'], result['rate'], result['message'], result['message_type'])


    async def check_acct_pro_state(self, acct_id: int, pro_id: int) -> tuple[None | tuple[str, str], int | None]:
        """Check the best challenge state of a user on a specific problem.

        Args:
            acct_id: User ID
            pro_id: Problem ID

        Returns:
            tuple: (err, state) where err is None on success, and state is the best challenge state or None if no challenge exists.
        """
        try:
            async with self.db.acquire() as con:
                result = await con.fetchrow(
                    '''
                        SELECT MIN("total_result"."state") AS "state"
                        FROM "challenge"
                        INNER JOIN "total_result"
                        ON "challenge"."chal_id" = "total_result"."chal_id"
                        AND "challenge"."acct_id" = $1
                        INNER JOIN "problem"
                        ON "challenge"."pro_id" = $2;
                    ''',
                    acct_id,
                    pro_id
                )
        except Exception as e:
            logger.error(f"Error checking account {acct_id} problem {pro_id} state: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None

        return None, result['state'] if result else None

    async def get_chals_count(self, flt: ChalSearchingParam):
        """
        Get the total count of challenges matching a filter.

        Args:
            flt (ChalSearchingParam): Filter parameters.

        Returns:
            tuple[Optional[tuple[str, str]], Optional[int]]:
                On success, (None, int).
                On failure, (error_code, None).
        """

        fltquery = flt.get_sql_query_str()

        try:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    f'''
                        SELECT COUNT(1) FROM "challenge"
                        INNER JOIN "account"
                        ON "challenge"."acct_id" = "account"."acct_id"
                        INNER JOIN "problem"
                        ON "challenge"."pro_id" = "problem"."pro_id"
                        INNER JOIN "total_result"
                        ON "challenge"."chal_id"="total_result"."chal_id"
                        WHERE 1=1 {fltquery};
                    '''
                )
        except Exception as e:
            logger.error(f"Error counting challenges with filter {flt}: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None

        if len(result) != 1:
            return ('Eunk', 'Unknown error'), None

        total_chal = result[0]['count']
        return None, total_chal

    async def update_testdata_result(self, chal_id: int, testdata_result: TestdataResult) -> tuple[None, None]:
        chal_id = int(chal_id)
        async with self.db.acquire() as con:
            await con.execute(
                '''
                    UPDATE "testdata_result"
                    SET "state" = $1, "time" = $2, "memory" = $3, "message" = $4, "message_type" = $5
                    WHERE "chal_id" = $6 AND "id" = $7;
                ''',
                testdata_result.state,
                testdata_result.time,
                testdata_result.memory,
                testdata_result.message,
                testdata_result.message_type,
                chal_id,
                testdata_result.testdata_id
            )

        return None, None

    async def update_subtask_result(self, chal_id: int, subtask_result: SubtaskResult) -> tuple[None, None]:
        chal_id = int(chal_id)
        async with self.db.acquire() as con:
            await con.execute(
                '''
                    UPDATE "subtask_result"
                    SET "state" = $1, "time" = $2, "memory" = $3, "rate" = $4
                    WHERE "chal_id" = $5 AND "subtask_id" = $6;
                ''',
                subtask_result.state,
                subtask_result.time,
                subtask_result.memory,
                subtask_result.rate,
                chal_id,
                subtask_result.subtask_id,
            )

        return None, None

    async def update_total_result(self, chal_id: int, total_result: TotalResult):
        chal_id = int(chal_id)
        async with self.db.acquire() as con:
            await con.execute(
                '''
                    UPDATE "total_result"
                    SET "state" = $1, "time" = $2, "memory" = $3, "rate" = $4, "message" = $5, "message_type" = $6
                    WHERE "chal_id" = $7;
                ''',
                total_result.state,
                total_result.time,
                total_result.memory,
                total_result.rate,
                total_result.message,
                total_result.message_type,
                chal_id,
            )

        return None, None
