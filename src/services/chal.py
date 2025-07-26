from dataclasses import dataclass
import datetime
import os
import decimal

from services.judge import JudgeServerClusterService
from services.pro import ProConst, ProblemConfig

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
    STATE_SJE = 12
    STATE_JUDGE = 100
    STATE_NOTSTARTED = 101

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
        STATE_SJE: 'SJE',
        STATE_ERR: 'IE',
        STATE_JUDGE: 'Challenging',
        STATE_NOTSTARTED: 'Not Started'
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
        STATE_SJE: 'Special Judge Error',
        STATE_JUDGE: 'Challenging',
        STATE_NOTSTARTED: 'Not Started',
    }

    FILE_EXTENSION = {
        'gcc': 'c',
        'clang': 'c',
        'g++': 'cpp',
        'clang++': 'cpp',
        'rustc': 'rs',
        'python3': 'py',
        'java': 'java',
    }

    ALLOW_COMPILERS = FILE_EXTENSION.keys()

    COMPILER_NAME = {
        'gcc': 'GCC 12.2.0 GNU11',
        'g++': 'G++ 12.2.0 GNU++17',
        'clang': 'Clang++ 15.0.6 C11',
        'clang++': 'Clang++ 15.0.6 C++17',
        'rustc': 'Rustc 1.63',
        'python3': 'CPython 3.11.2',
        'java': 'OpenJDK 17.0.8',
    }

    assert len(FILE_EXTENSION) == len(COMPILER_NAME)
    assert sorted(FILE_EXTENSION.keys()) == sorted(COMPILER_NAME.keys())

    NORMAL_PRI = 0
    CONTEST_PRI = 1
    CONTEST_REJUDGE_PRI = 2
    NORMAL_REJUDGE_PRI = 3

@dataclass(slots=True)
class SubtaskResult:
    """
    - 'subtask_id' (int): Subtask result id.
    - 'state' (int): Challenge state, between ChalConst.STATE_AC and ChalConst.STATE_NOTSTARTED.
    - 'time' (int): Total time in milliseconds.
    - 'memory' (int): Memory usage in kilobytes.
    - 'response' (str): Compiler or checker message.
    - 'rate' (decimal.Decimal), rounded by problem.rate_precision
    """
    subtask_id: int
    state: int
    time: int
    memory: int
    response: str
    rate: decimal.Decimal

    def __post_init__(self):
        assert ChalConst.STATE_AC <= self.state <= ChalConst.STATE_NOTSTARTED
        assert self.time >= 0
        assert self.memory >= 0

@dataclass(slots=True)
class TotalResult:
    state: int
    time: int
    memory: int
    rate: decimal.Decimal

    def __post_init__(self):
        assert ChalConst.STATE_AC <= self.state <= ChalConst.STATE_NOTSTARTED
        assert self.time >= 0
        assert self.memory >= 0

@dataclass(slots=True)
class Challenge:
    chal_id: int
    pro_id: int
    acct_id: int
    contest_id: int
    acct_name: str
    compiler_type: str
    timestamp: datetime.datetime
    subtask_results: dict[int, SubtaskResult] | None
    total_result: TotalResult | None

    def __post_init__(self):
        assert self.compiler_type in ChalConst.ALLOW_COMPILERS


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
            - If `ChalConst.STATE_NOTSTARTED`: adds `state IS NULL` to the filter.
            - Other values: exact match (e.g., `ChalConst.STATE_AC`, `ChalConst.STATE_WA`, etc.).
            - See `ChalConst.STATE_*` for available state constants.

        compiler (str | None): Compiler type to filter.
            - If "all": no filtering is applied.
            - Otherwise, matches the exact compiler string.
            - Valid values are defined in `ChalConst.COMPILER_NAME`.

        allow_pro_statuses (list[int] | None): A list of allowed problem statuses to include.
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
    compiler: str | None
    allow_pro_statuses: list[int] | None
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
            if self.state == ChalConst.STATE_NOTSTARTED:
                query.append(' AND "total_result"."state" IS NULL ')
            else:
                query.append(f' AND "total_result"."state" = {self.state} ')

        if self.compiler != 'all':
            query.append(f' AND "challenge"."compiler_type"=\'{self.compiler}\' ')

        if self.contest != 0:
            query.append(f' AND "challenge"."contest_id"={self.contest} ')
        else:
            query.append(' AND "challenge"."contest_id"=0 ')

        if not self.allow_pro_statuses:
            query.append(f' AND "problem"."status" IN ({",".join(map(str, [ProConst.STATUS_ONLINE]))}) ')
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
                   .compiler("gcc")
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
        self.param = ChalSearchingParam([], [], 0, "all", [ProConst.STATUS_ONLINE], 0)

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

    def compiler(self, compiler: str | None):
        """Sets the compiler type to filter."""
        self.param.compiler = compiler
        return self

    def contest(self, contest: int | None):
        """Sets the contest ID to filter."""
        if contest is not None:
            self.param.contest = contest
        return self

    def pro_statuses(self, pro_statuses: list[int]):
        """
        Sets the allowed problem statuses for filtering.

        Args:
            pro_statuses (list[int]): List of `ProConst.STATUS_*` values to include.

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

    async def add_chal(self, pro_id: int, acct_id: int, contest_id: int, compiler_type: str, code: str) -> tuple[None, int] | ErrorType:
        """
        Add a new challenge entry and save the submitted source code.

        Args:
            pro_id (int): Problem ID.
            acct_id (int): Account ID (user submitting the challenge).
            contest_id (int): Contest ID.
            compiler_type (str): Compiler type (must be in ChalConst.ALLOW_COMPILERS).
            code (str): Source code content as string.

        Returns:
            tuple[Optional[tuple[str, str]], Optional[int]]:
                On success, (None, chal_id).
                On failure, (error_code, None).
        """

        assert compiler_type in ChalConst.ALLOW_COMPILERS

        pro_id = int(pro_id)
        acct_id = int(acct_id)

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    INSERT INTO "challenge" ("pro_id", "acct_id", "compiler_type", "contest_id")
                    VALUES ($1, $2, $3, $4) RETURNING "chal_id";
                ''',
                pro_id,
                acct_id,
                compiler_type,
                contest_id,
            )
        if len(result) != 1:
            return ('Eunk', 'Unknown error'), None
        result = result[0]

        chal_id = result['chal_id']

        file_ext = ChalConst.FILE_EXTENSION[compiler_type]

        os.mkdir(f'code/{chal_id}')
        with open(f"code/{chal_id}/main.{file_ext}", 'wb') as code_f:
            code_f.write(code.encode('utf-8'))

        return None, chal_id

    async def reset_chal(self, chal_id: int) -> tuple[None, None]:
        """
        Reset a challenge by deleting all its associated tests and updating its state.

        Args:
            chal_id (int): Challenge ID to reset.

        Returns:
            tuple[None, None]: Always returns (None, None).
        """

        chal_id = int(chal_id)
        async with self.db.acquire() as con:
            await con.execute('DELETE FROM "subtask_result" WHERE "chal_id" = $1;', chal_id)

        await self.update_total_result(chal_id)
        return None, None

    async def get_subtask_results(self, chal_id: int) -> tuple[None, dict[int, SubtaskResult]]:
        """
        Retrieve detailed test results of a challenge.

        Args:
            chal_id (int): Challenge ID.

        Returns:
            tuple[Optional[tuple[str, str]], Optional[dict[int, SubtaskResult]]:
                On success, (None, dict[int, SubtaskResult]) where each dict represents a subtask.
                On failure, (error_code, None).
        """
        chal_id = int(chal_id)
        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT subtask_result.subtask_id, state, time, memory, response,
                    ROUND(COALESCE(subtask_result.rate, tvr.rate), problem.rate_precision)
                    FROM subtask_result
                    INNER JOIN test_valid_rate AS tvr
                    ON subtask_result.pro_id = tvr.pro_id AND subtask_result.subtask_id = tvr.test_idx
                    INNER JOIN problem
                    ON subtask_result.pro_id = problem.pro_id
                    WHERE "chal_id" = $1 ORDER BY "subtask_id" ASC;
                ''',
                chal_id,
            )

        results: dict[int, SubtaskResult] = {}
        for subtask_id, state, time, memory, response, rate in result:
            r = 0
            if state in [ChalConst.STATE_AC, ChalConst.STATE_PC]:
                r = rate

            results[subtask_id] = SubtaskResult(subtask_id, state, int(time), int(memory), response, decimal.Decimal(r))

        return None, results

    async def get_chal(self, chal_id: int, with_result=False) -> tuple[None, Challenge] | ErrorType:
        """
        Retrieve challenge info with optional test details.

        Args:
            chal_id (int): Challenge ID.
            with_test (bool): Whether to include detailed test results.

        Returns:
            tuple[Optional[tuple[str, str]], Optional[Challenge]]:
                On success, (None, Challenge)
                On failure, (error_code, None).
        """

        chal_id = int(chal_id)
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

        subtask_results = {}
        if with_result:
            _, subtask_results = await self.get_subtask_results(chal_id)

        return None, Challenge(chal_id, pro_id, acct_id, contest_id, acct_name, compiler_type,
                               timestamp, subtask_results, total_result=None)

    async def emit_chal(self, chal_id: int, pro_id: int, conf: ProblemConfig, compiler_type: str, pri: int) -> tuple[None, None] | ErrorType:
        """
        Create and submit tests for a challenge based on the test metadata configuration,
        then send the challenge to the judging cluster.

        Args:
            chal_id (int): Challenge ID.
            pro_id (int): Problem ID.
            testm_conf (dict): Test metadata configuration.
            compiler_type (str): Compiler type (must be in ChalConst.ALLOW_COMPILERS).
            pri (int): Priority level (within ChalConst.NORMAL_PRI and ChalConst.NORMAL_REJUDGE_PRI).

        Returns:
            tuple[None, None]: Always returns (None, None) on completion.
        """

        assert compiler_type in ChalConst.ALLOW_COMPILERS
        assert ChalConst.NORMAL_PRI <= pri <= ChalConst.NORMAL_REJUDGE_PRI

        chal_id = int(chal_id)
        pro_id = int(pro_id)

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "acct_id", "contest_id", "timestamp" FROM "challenge"
                    WHERE "chal_id" = $1;
                ''',
                chal_id,
            )
        if len(result) != 1:
            return ('Enoext', 'Challenge not found'), None
        result = result[0]

        acct_id, contest_id, timestamp = int(result['acct_id']), int(result['contest_id']), result['timestamp']
        limits = conf.limits
        timelimit = limits.get(compiler_type, limits['default']).time
        memlimit = limits.get(compiler_type, limits['default']).memory

        async with self.db.acquire() as con:
            testl = []
            insert_values = []
            for subtask_id, subtask_conf in conf.subtask_configs.items():
                testl.append(
                    {
                        'test_idx': subtask_id,
                        'timelimit': timelimit,
                        'memlimit': memlimit,
                        'metadata': {'data': [conf.testdatas[testdata.testdata_id].inputfile.removesuffix('.in') for testdata in subtask_conf.testdatas]},
                    }
                )
                insert_values.append((chal_id, acct_id, pro_id, subtask_id, ChalConst.STATE_JUDGE, timestamp))

            await con.executemany(
            '''INSERT INTO "subtask_result"
                ("chal_id", "acct_id", "pro_id", "subtask_id", "state", "timestamp")
                VALUES ($1, $2, $3, $4, $5, $6);''',
                insert_values
            )

        await self.update_total_result(chal_id)

        file_ext = ChalConst.FILE_EXTENSION[compiler_type]

        if not os.path.isfile(f"code/{chal_id}/main.{file_ext}"):
            for subtask_conf in testl:
                await self.update_subtask_result(chal_id,
                                                 SubtaskResult(subtask_conf['test_idx'], ChalConst.STATE_ERR, time=0, memory=0, response='', rate=decimal.Decimal(0)),
                                                 rate_is_cms_type=False, refresh_db=False)
            await self.update_total_result(chal_id)
            return None, None

        if conf.is_makefile:
            compiler_type = 'makefile'

        await JudgeServerClusterService.inst.send(
            {
                'pri': pri,
                'chal_id': chal_id,
                'test': testl,
                'code_path': f'{chal_id}/main.{file_ext}',
                'res_path': f'{pro_id}/res',
                'metadata': conf.chalmeta,
                'comp_type': compiler_type,
                'check_type': ProConst.CHECKER_TYPE[conf.checker_type],
            },
            pro_id,
            contest_id,
        )

        await self.rs.hdel('rate', str(acct_id))

        return None, None

    async def list_chal(self, off: int, num: int, flt: ChalSearchingParam) -> tuple[None, list[Challenge]]:
        # TODO: docstirng without challenge.subtask_result
        """
        List challenges with filtering, pagination, and joined related info.

        Args:
            off (int): Offset for pagination.
            num (int): Number of challenges to return.
            flt (ChalSearchingParam): Filter parameters.

        Returns:
            tuple[None, list[Challenge]]: On success, returns (None, list[Challenge]) but Challenge without subtask_results:
        """
        fltquery = flt.get_sql_query_str()

        async with self.db.acquire() as con:
            result = await con.fetch(
                f'''
                    SELECT "challenge"."chal_id", "challenge"."pro_id", "challenge"."acct_id", "challenge"."contest_id",
                    "challenge"."compiler_type", "challenge"."timestamp", "account"."name" AS "acct_name",
                    "total_result"."state", "total_result"."time", "total_result"."memory",
                    ROUND("total_result"."rate", problem.rate_precision)
                    FROM "challenge"
                    INNER JOIN "account"
                    ON "challenge"."acct_id" = "account"."acct_id"
                    INNER JOIN "problem"
                    ON "challenge"."pro_id" = "problem"."pro_id"
                    LEFT JOIN "total_result"
                    ON "challenge"."chal_id" = "total_result"."chal_id"
                    WHERE 1=1 {fltquery}
                    ORDER BY "challenge"."chal_id" DESC OFFSET {off} LIMIT {num};
                '''
            )

        challist: list[Challenge] = []
        for chal_id, pro_id, acct_id, contest_id, compiler_type, timestamp, acct_name, state, time, memory, rate in result:
            if state is None:
                state = ChalConst.STATE_NOTSTARTED

            if time is None:
                time = 0
            else:
                time = int(time)

            if memory is None:
                memory = 0
            else:
                memory = int(memory)

            challist.append(Challenge(chal_id, pro_id, acct_id, contest_id, acct_name,
                                      compiler_type, timestamp, subtask_results=None,
                                      total_result=TotalResult(state, time, memory, rate)))
        return None, challist

    async def get_total_result(self, chal_id: int, allow_pro_statuses: list[int]) -> tuple[None, TotalResult] | tuple[tuple[str, str], None]:
        """
        Retrieve the aggregated state of a challenge filtered by allowed problem statuses.

        This method queries the `total_result` table joined with `problem` to ensure
        that only challenges related to problems with statuses in `allow_pro_statuses` are considered.

        Args:
            chal_id (int): The ID of the challenge to retrieve.
            allow_pro_statuses (list[int]): List of allowed problem status codes to filter by.
                Each status should be between `ProConst.STATUS_ONLINE` and `ProConst.STATUS_HIDDEN`.

        Returns:
            tuple[Optional[tuple[str, str]], Optional[Challenge]]:
                On success, returns (None, Challenge) but without subtask_results:
                On failure (e.g., challenge not found), returns (error_code, None).
        """

        assert len(allow_pro_statuses)
        for status in allow_pro_statuses:
            assert ProConst.STATUS_ONLINE <= status <= ProConst.STATUS_HIDDEN

        chal_id = int(chal_id)

        async with self.db.acquire() as con:
            result = await con.fetch(
                f'''
                    SELECT
                        cs.state,
                        cs.time,
                        cs.memory,
                        ROUND(cs.rate, p.rate_precision) AS rate
                    FROM
                        challenge c
                    INNER JOIN
                        problem p ON c.pro_id = p.pro_id
                    INNER JOIN
                        total_result cs ON c.chal_id = cs.chal_id
                    WHERE
                        p.status IN ({",".join(map(str, allow_pro_statuses))})
                        AND cs.chal_id = $1;
                ''',
                chal_id,
            )

        if len(result) != 1:
            return ('Enoext', 'Challenge not found'), None
        result = result[0]

        return None, TotalResult(result['state'], result['time'], result['memory'], result['rate'])


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

        async with self.db.acquire() as con:
            result = await con.fetch(
                (
                    f'''
                        SELECT COUNT(1) FROM "challenge"
                        INNER JOIN "account"
                        ON "challenge"."acct_id" = "account"."acct_id"
                        INNER JOIN "problem"
                        ON "challenge"."pro_id" = "problem"."pro_id"
                        LEFT JOIN "total_result"
                        ON "challenge"."chal_id"="total_result"."chal_id"
                        WHERE 1=1 {fltquery};
                    '''
                )
            )

        if len(result) != 1:
            return ('Eunk', 'Unknown error'), None

        total_chal = result[0]['count']
        return None, total_chal

    async def update_subtask_result(self, chal_id: int, subtask: SubtaskResult, rate_is_cms_type=False, refresh_db=True) -> tuple[None, None]:
        chal_id = int(chal_id)
        async with self.db.acquire() as con:
            await con.execute(
                '''
                    UPDATE "subtask_result"
                    SET "state" = $1, "time" = $2, "memory" = $3, "response" = $4, "rate" = $5
                    WHERE "chal_id" = $6 AND "subtask_id" = $7;
                ''',
                subtask.state,
                subtask.time,
                subtask.memory,
                subtask.response,
                None if subtask.rate.is_infinite() else subtask.rate,
                chal_id,
                subtask.subtask_id,
            )

            if rate_is_cms_type:
                await con.execute(
                    '''
                        UPDATE "subtask_result"
                        SET "rate" = $1::decimal * "subtask_config"."rate"::decimal
                        FROM "subtask_config"
                        WHERE "subtask_result"."chal_id" = $2 AND
                              "subtask_config"."pro_id" = "subtask_result"."pro_id" AND
                              "subtask_config"."subtask_id" = $3 AND
                              "subtask_result"."subtask_id" = $3;
                    ''',
                    subtask.rate, chal_id, subtask.subtask_id
                )

        if refresh_db:
            await self.update_total_result(chal_id)

        return None, None

    async def update_total_result(self, chal_id: int):
        """
        Trigger the database function to aggregate and update the overall state of a challenge.

        This function calls the PostgreSQL stored procedure `update_total_result(p_chal_id INTEGER)`
        which calculates the following aggregates from all tests belonging to the challenge:
        - The maximum test state (indicating the overall challenge status).
        - The sum of time across tests.
        - The sum of memory usage across tests.
        - The sum of rates/scores, considering special scores or default rates.

        The aggregated results are then upserted into the `total_result` table,
        updating only when values have changed to avoid unnecessary writes.

        Args:
            chal_id (int): The challenge ID to update.

        Returns:
            None
        """

        await self.db.execute(f'SELECT update_total_result({chal_id});')
