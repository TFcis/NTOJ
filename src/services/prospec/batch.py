import decimal
import os
from dataclasses import dataclass
from typing import Any

from services.pro import BaseConfig, CheckerType, SummaryType, ProblemConfig
from services.prospec.base import ProSpec


@dataclass(slots=True)
class BatchConfig(BaseConfig):
    """
    Batch problem type specific configuration.

    - has_grader (bool): Whether the problem uses a Makefile-based compilation.
    See: https://wiki.tfcis.org/TOJ#Makefile%E9%A1%8C%E7%9B%AE_(%E7%B7%A8%E8%AD%AF%E4%BA%92%E5%8B%95%E9%A1%8C)

    - chalmeta (str): For IORedir Problem
    See: https://wiki.tfcis.org/TOJ#IORedir

    - checker_type (int): One of the values defined in ProConst.CHECKER_TYPE, indicating
    the type of checker (e.g., diff, float-diff, ioredir).
    """
    chalmeta: str
    userprog_compile_args: str
    checker_type: CheckerType
    checker_compiler: int | None
    checker_compile_args: str
    summary_type: SummaryType
    summary_compiler: int | None
    summary_compile_args: str
    has_grader: bool
    allow_compilers: set[int]


class BatchProblemSpec(ProSpec):
    """Specification for Batch-type problems."""

    def from_json(self, data: dict[str, Any]) -> BatchConfig:
        """Parse JSON data into BatchConfig."""
        from services.chal import Compiler

        # Parse compiler references
        checker_compiler = data.get('checker_compiler')
        if checker_compiler is not None:
            checker_compiler = Compiler(checker_compiler)

        summary_compiler = data.get('summary_compiler')
        if summary_compiler is not None:
            summary_compiler = Compiler(summary_compiler)

        # Note: limits, subtask_configs, testdatas are stored separately in DB
        # This only handles Batch-specific config
        return BatchConfig(
            chalmeta=data.get('chalmeta', ''),
            userprog_compile_args=data.get('userprog_compile_args', ''),
            checker_type=CheckerType(data['checker_type']),
            checker_compiler=checker_compiler,
            checker_compile_args=data.get('checker_compile_args', ''),
            summary_type=SummaryType(data['summary_type']),
            summary_compiler=summary_compiler,
            summary_compile_args=data.get('summary_compile_args', ''),
            has_grader=data.get('has_grader', False),
            allow_compilers=set(data.get('allow_compilers', [])),
        )

    def to_json(self, config: BatchConfig) -> dict[str, Any]:
        """Convert BatchConfig to JSON."""
        return {
            'chalmeta': config.chalmeta,
            'userprog_compile_args': config.userprog_compile_args,
            'checker_type': int(config.checker_type),
            'checker_compiler': int(config.checker_compiler) if config.checker_compiler else None,
            'checker_compile_args': config.checker_compile_args,
            'summary_type': int(config.summary_type),
            'summary_compiler': int(config.summary_compiler) if config.summary_compiler else None,
            'summary_compile_args': config.summary_compile_args,
            'has_grader': config.has_grader,
            'allow_compilers': list(config.allow_compilers),
        }

    async def emit_chal(
        self,
        db,
        rs,
        chal_id: int,
        pro_id: int,
        acct_id: int,
        contest_id: int,
        compiler_type: int,
        config: ProblemConfig,
        priority: int,
        skip_nonac: bool = False,
    ) -> tuple[None, None] | tuple[tuple[str, str], None]:
        """Emit Batch challenge to judge server."""
        from services.chal import ChalConst, COMPILER_INFOS
        from services.judge import JudgeServerClusterService

        assert ChalConst.NORMAL_PRI <= priority <= ChalConst.NORMAL_REJUDGE_PRI
        assert isinstance(config.spec_config, BatchConfig)

        chal_id = int(chal_id)
        pro_id = int(pro_id)
        batch_config = config.spec_config

        limits = config.limits
        limit = limits.get(str(compiler_type), limits['default'])

        await db.execute('UPDATE total_result SET state = $1 WHERE chal_id = $2;', ChalConst.STATE_JUDGE, chal_id)
        await db.execute('UPDATE subtask_result SET state = $1 WHERE chal_id = $2;', ChalConst.STATE_JUDGE, chal_id)

        need_judge_testdatas: set[int] = set()
        subtasks = []
        for subtask_id, subtask_config in config.subtask_configs.items():
            t = [testdata.testdata_id for testdata in subtask_config.testdatas]
            need_judge_testdatas.update(t)
            subtasks.append({
                "id": subtask_id,
                "score": subtask_config.rate,
                "testdatas": t,
                "dependency_subtasks": list(subtask_config.dependency_subtasks),
            })

        await db.execute('UPDATE testdata_result SET state = $1 WHERE chal_id = $2 AND id = ANY($3);',
                        ChalConst.STATE_JUDGE, chal_id, list(need_judge_testdatas))

        testdatas = []
        for testdata_id in need_judge_testdatas:
            testdata = config.testdatas[testdata_id]
            testdatas.append({
                "id": testdata.testdata_id,
                "input": testdata.inputfile,
                "output": testdata.outputfile,
            })

        source_ext = COMPILER_INFOS[compiler_type].source_ext

        if not os.path.isfile(f"code/{chal_id}/main.{source_ext}"):
            from services.chal import TotalResult, SubtaskResult, TestdataResult, ChalService, MessageType

            await ChalService.inst.update_total_result(
                chal_id,
                TotalResult(ChalConst.STATE_ERR, 0, 0, decimal.Decimal(), "", MessageType.NONE)
            )

            for subtask_id in config.subtask_configs:
                await ChalService.inst.update_subtask_result(
                    chal_id,
                    SubtaskResult(subtask_id, ChalConst.STATE_ERR, 0, 0, decimal.Decimal())
                )

            for testdata_id in need_judge_testdatas:
                await ChalService.inst.update_testdata_result(
                    chal_id,
                    TestdataResult(testdata_id, ChalConst.STATE_ERR, 0, 0, "", MessageType.NONE)
                )

            return None, None

        await JudgeServerClusterService.inst.send(
            {
                'acct_id': acct_id,
                'pro_id': pro_id,
                'contest_id': contest_id,
                'chal_id': chal_id,

                'res_path': f'{pro_id}/res',
                'code_path': f'{chal_id}/main.{source_ext}',

                'subtasks': subtasks,
                'testdatas': testdatas,

                'limit': {
                    'output': limit.output * 1024,  # kib to bytes
                    'time': limit.time * 10 ** 6,  # ms to ns
                    'memory': limit.memory * 1024,  # kib to bytes
                },

                'has_grader': batch_config.has_grader,
                'userprog_compiler': compiler_type,
                'userprog_compile_args': batch_config.userprog_compile_args,

                'checker_type': batch_config.checker_type,
                'checker_compiler': batch_config.checker_compiler,
                'checker_compile_args': batch_config.checker_compile_args,

                'summary_type': batch_config.summary_type,
                'summary_compiler': batch_config.summary_compiler,
                'summary_compile_args': batch_config.summary_compile_args,

                'priority': priority,
                'skip_nonac': skip_nonac,
            },
            pro_id,
            contest_id,
        )

        return None, None

    async def add_chal(
        self,
        db,
        rs,
        pro_id: int,
        acct_id: int,
        contest_id: int,
        compiler_type: int,
        code: str,
        config: ProblemConfig,
    ) -> tuple[None, int] | tuple[tuple[str, str], None]:
        """Add a Batch challenge."""
        from services.chal import COMPILER_INFOS

        pro_id = int(pro_id)
        acct_id = int(acct_id)

        async with db.acquire() as con:
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

            need_judge_testdatas = set()
            insert_subtask_values = []
            for subtask_id, subtask in config.subtask_configs.items():
                insert_subtask_values.append((chal_id, pro_id, subtask_id))
                need_judge_testdatas.update(testdata.testdata_id for testdata in subtask.testdatas)

            insert_testdata_values = []
            for testdata_id in need_judge_testdatas:
                insert_testdata_values.append((chal_id, pro_id, testdata_id))

            await con.execute('INSERT INTO total_result (chal_id) VALUES ($1)', chal_id)
            await con.executemany('INSERT INTO subtask_result (chal_id, pro_id, subtask_id) VALUES ($1, $2, $3);', insert_subtask_values)
            await con.executemany('INSERT INTO testdata_result (chal_id, pro_id, id) VALUES ($1, $2, $3);', insert_testdata_values)

        source_ext = COMPILER_INFOS[compiler_type].source_ext

        os.mkdir(f'code/{chal_id}')
        with open(f"code/{chal_id}/main.{source_ext}", 'wb') as code_f:
            code_f.write(code.encode('utf-8'))

        return None, chal_id

    def parse_testdata_files(self, files_json: dict[str, Any]) -> dict[str, str]:
        """Parse Batch testdata files JSON."""
        return {
            'input': files_json.get('input', ''),
            'output': files_json.get('output', ''),
        }

    def build_testdata_files(self, **files) -> dict[str, Any]:
        """Build Batch testdata files JSON."""
        return {
            'input': files.get('input', ''),
            'output': files.get('output', ''),
        }

    async def unpack_pro(
        self,
        db,
        rs,
        pro_id: int,
        pack_token: str,
    ) -> tuple[None, None] | tuple[tuple[str, str], None]:
        """
        Unpack and apply a Batch problem package.

        Args:
            db: Database connection pool
            rs: Redis connection
            pro_id: The ID of the problem to unpack into
            pack_token: Token for identifying the uploaded archive

        Returns:
            (None, None) on success, or (error_tuple, None) on failure
        """
        from services.chal import Compiler, ChalConst
        from services.pack import PackService
        from services.pro import Limit, SubtaskConfig, ProblemConfig, ProType, ProConst, ProService
        import json
        import os
        import shutil

        failed = True
        try:
            err, _ = await PackService.inst.unpack(pack_token, f"problem/{pro_id}", True)
            if err:
                return err, None

            try:
                os.chmod(os.path.abspath(f"problem/{pro_id}"), 0o755)
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
                    if "timelimit" in conf_limit and "memlimit" in conf_limit:
                        try:
                            limit.time = max(int(conf_limit["timelimit"]), 0)
                            limit.memory = max(int(conf_limit["memlimit"]), 0)
                            limit.output = 65536
                        except ValueError:
                            continue

                    elif "time" in conf_limit and "memory" in conf_limit and "output" in conf_limit:
                        try:
                            limit.time = max(int(conf_limit["time"]), 0)
                            limit.memory = max(int(conf_limit["memory"]), 0)
                            limit.output = max(int(conf_limit["output"]), 0)
                        except ValueError:
                            continue
                    else:
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
            testdatas: dict[int, BaseTestdata] = {}
            testdata_name_2_id: dict[str, int] = {}
            testdata_id_counter = 0
            for test_idx, test_conf in enumerate(conf["test"]):
                for t in test_conf["data"]:
                    if t not in testdata_name_2_id:
                        t = os.path.basename(str(t))
                        testdata_name_2_id[t] = testdata_id_counter
                        testdatas[testdata_id_counter] = BatchTestdata(testdata_id_counter, f"{t}.in", f"{t}.out")
                        testdata_id_counter += 1

                subtask_configs[test_idx] = SubtaskConfig(test_idx, [], set(), int(test_conf["weight"]))

            for test_idx, test_conf in enumerate(conf["test"]):
                for t in test_conf["data"]:
                    t = os.path.basename(str(t))
                    subtask_configs[test_idx].testdatas.append(testdatas[testdata_name_2_id[t]])

            if has_grader:
                allow_compilers = {int(Compiler.CLANGPP), int(Compiler.GPP)}
            else:
                allow_compilers = {int(v) for v in Compiler}
            checker_type = ProConst.OLD_STR_2_CHECKER_TYPE[conf["check"]]

            batch_config = BatchConfig(
                chalmeta=chalmeta,
                userprog_compile_args="",
                checker_type=checker_type,
                checker_compiler=int(Compiler.GPP),
                checker_compile_args="",
                summary_type=SummaryType.GROUPMIN,
                summary_compiler=int(Compiler.GPP),
                summary_compile_args="",
                has_grader=has_grader,
                allow_compilers=allow_compilers,
            )

            proconfig = ProblemConfig(
                limits=limits,
                subtask_configs=subtask_configs,
                testdatas=testdatas,
                rate_precision=0,
                spec_config=batch_config,
            )
            failed = False

        finally:
            # NOTE: Like golang defer
            if failed and os.path.exists(f"problem/{pro_id}"):
                shutil.rmtree(f"problem/{pro_id}")
            await PackService.inst.clear(pack_token)

        await ProService.inst.update_pro_config(pro_id, ProType.BATCH, proconfig)
        await rs.delete("prolist")

        return None, None


# Singleton instance
batch_spec = BatchProblemSpec()

