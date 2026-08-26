import decimal
import logging
import os
from dataclasses import dataclass

from services.pro import BaseConfig, CheckerType, Limit, ProblemConfig, SummaryType

logger = logging.getLogger("tornado.application")


@dataclass(slots=True)
class ProgramConfig(BaseConfig):
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


def build_program_limits(
    raw_limits: dict, allow_compilers: set[int]
) -> dict[str, Limit]:
    """Validate compiler limits shared by Batch and Communication problems."""
    from services.chal import Compiler

    if not isinstance(raw_limits, dict):
        raise ValueError("Invalid limit config")
    allowed = allow_compilers.copy()
    allowed.add("default")
    limits: dict[str, Limit] = {}
    for compiler_type, raw_limit in raw_limits.items():
        limit_key = "default"
        if compiler_type != "default":
            try:
                compiler_type = Compiler(int(compiler_type))
            except (TypeError, ValueError):
                continue
            limit_key = str(int(compiler_type))
        if compiler_type not in allowed:
            continue
        try:
            limits[limit_key] = Limit(
                max(int(raw_limit["time"]), 0),
                max(int(raw_limit["memory"]), 0),
                max(int(raw_limit["output"]), 0),
            )
        except (TypeError, ValueError, KeyError):
            continue

    if "default" not in limits:
        raise ValueError("Missing default limit config")
    return limits


def get_submission_filenames(spec, spec_config, source_ext: str) -> list[str]:
    resolver = getattr(spec, "get_submission_filenames", None)
    if resolver is None:
        return [f"main.{source_ext}"]
    filenames = resolver(spec_config, source_ext)
    if not filenames or len(filenames) != len(set(filenames)):
        raise ValueError("Invalid submission filenames")
    return filenames


def get_submission_files(code, filenames: list[str]) -> list[tuple[str, str]]:
    if isinstance(code, str) and len(filenames) == 1:
        return [(filenames[0], code)]
    if not isinstance(code, dict) or set(code) != set(filenames):
        raise ValueError("Submitted source files do not match submission_format")
    if any(not isinstance(content, str) for content in code.values()):
        raise ValueError("Submitted source files must contain text")
    return [(filename, code[filename]) for filename in filenames]


def rename_submission_files(
    chal_id: int,
    old_filenames: list[str],
    new_filenames: list[str],
) -> None:
    """Rename existing submitted sources to match the current problem setting."""
    requested_renames = [
        (old_name, new_name)
        for old_name, new_name in zip(old_filenames, new_filenames)
        if old_name != new_name
    ]
    renames = [
        (old_name, new_name)
        for old_name, new_name in requested_renames
        if os.path.isfile(f"code/{chal_id}/{old_name}")
    ]
    if not renames:
        return

    sources = {old_name for old_name, _ in renames}
    for _, new_name in renames:
        target = f"code/{chal_id}/{new_name}"
        if os.path.exists(target) and new_name not in sources:
            raise FileExistsError(f"Submitted source already exists: {new_name}")

    rename_plan = [
        (
            old_name,
            new_name,
            f"code/{chal_id}/.submission-{index}.rename",
        )
        for index, (old_name, new_name) in enumerate(renames)
    ]
    if any(os.path.exists(temporary) for _, _, temporary in rename_plan):
        raise FileExistsError("Submission rename temporary file already exists")

    staged = []
    finalized = []
    try:
        for old_name, new_name, temporary in rename_plan:
            source = f"code/{chal_id}/{old_name}"
            os.rename(source, temporary)
            staged.append((old_name, new_name, temporary))

        for item in staged:
            _, new_name, temporary = item
            os.rename(temporary, f"code/{chal_id}/{new_name}")
            finalized.append(item)
    except OSError:
        for old_name, new_name, temporary in finalized:
            target = f"code/{chal_id}/{new_name}"
            if os.path.exists(target):
                os.rename(target, temporary)
        for old_name, _, temporary in staged:
            if os.path.exists(temporary):
                os.rename(temporary, f"code/{chal_id}/{old_name}")
        raise


async def emit_program_chal(
    spec,
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
    include_system_test: bool = True,
) -> tuple[None, None] | tuple[tuple[str, str], None]:
    """Emit a compiled-program challenge to the judge server."""
    from services.chal import ChalConst, COMPILER_INFOS
    from services.judge import JudgeServerClusterService

    assert ChalConst.NORMAL_PRI <= priority <= ChalConst.NORMAL_REJUDGE_PRI
    assert isinstance(config.spec_config, spec.config_type)

    chal_id = int(chal_id)
    pro_id = int(pro_id)
    spec_config = config.spec_config

    limits = config.limits
    limit = limits.get(str(compiler_type), limits['default'])

    try:
        async with db.acquire() as con:
            async with con.transaction():
                await con.execute('UPDATE total_result SET state = $1 WHERE chal_id = $2;', ChalConst.STATE_JUDGE, chal_id)
                await con.execute('UPDATE subtask_result SET state = $1 WHERE chal_id = $2;', ChalConst.STATE_JUDGE, chal_id)

                need_judge_testdatas: set[int] = set()
                subtasks = []

                if include_system_test:
                    # Include all subtasks and testdatas
                    for subtask_id, subtask_config in config.subtask_configs.items():
                        t = [testdata.testdata_id for testdata in subtask_config.testdatas]
                        need_judge_testdatas.update(t)
                        subtasks.append({
                            "id": subtask_id,
                            "score": subtask_config.rate,
                            "testdatas": t,
                            "dependency_subtasks": list(subtask_config.dependency_subtasks),
                        })
                else:
                    # Pretest mode: exclude system-test tagged subtasks and testdatas
                    from services.chal import SubtaskResult, TestdataResult, ChalService, MessageType

                    system_test_subtasks = config.get_system_test_subtasks()

                    # Mark entire system-test subtasks as SKIPPED
                    for subtask_id, subtask_config in system_test_subtasks.items():
                        await ChalService.inst.update_subtask_result(
                            chal_id,
                            SubtaskResult(subtask_id, ChalConst.STATE_SKIPPED, 0, 0, decimal.Decimal())
                        )
                        # Mark all testdatas in this system-test subtask as SKIPPED
                        for testdata in subtask_config.testdatas:
                            await ChalService.inst.update_testdata_result(
                                chal_id,
                                TestdataResult(testdata.testdata_id, ChalConst.STATE_SKIPPED, 0, 0, "", MessageType.NONE)
                            )

                    # Process pretest subtasks (non-system-test subtasks)
                    pretest_subtasks = config.get_pretest_subtasks()
                    for subtask_id, subtask_config in pretest_subtasks.items():
                        # Filter out system-test tagged testdatas within this subtask
                        pretest_testdatas = []
                        for testdata in subtask_config.testdatas:
                            if testdata.is_system_test():
                                # Mark individual system-test testdata as SKIPPED
                                await ChalService.inst.update_testdata_result(
                                    chal_id,
                                    TestdataResult(testdata.testdata_id, ChalConst.STATE_SKIPPED, 0, 0, "", MessageType.NONE)
                                )
                            else:
                                pretest_testdatas.append(testdata.testdata_id)

                        # Only include subtask if it has at least one pretest testdata
                        if pretest_testdatas:
                            need_judge_testdatas.update(pretest_testdatas)
                            subtasks.append({
                                "id": subtask_id,
                                "score": subtask_config.rate,
                                "testdatas": pretest_testdatas,
                                "dependency_subtasks": list(subtask_config.dependency_subtasks),
                            })
                        else:
                            # Subtask has no pretest testdatas, mark as SKIPPED
                            await ChalService.inst.update_subtask_result(
                                chal_id,
                                SubtaskResult(subtask_id, ChalConst.STATE_SKIPPED, 0, 0, decimal.Decimal())
                            )

                        run_subtasks = {subtask['id'] for subtask in subtasks}
                        while True:
                            newly_invalid = [
                                subtask
                                for subtask in subtasks
                                if subtask['id'] in run_subtasks
                                and any(
                                    dep not in run_subtasks
                                    for dep in subtask['dependency_subtasks']
                                )
                            ]
                            if not newly_invalid:
                                break

                            for subtask in newly_invalid:
                                subtask_id = subtask['id']
                                run_subtasks.remove(subtask_id)
                                need_judge_testdatas.difference_update(subtask['testdatas'])
                                await ChalService.inst.update_subtask_result(
                                    chal_id,
                                    SubtaskResult(subtask['id'], ChalConst.STATE_JE, 0, 0, decimal.Decimal())
                                )
                                for testdata_id in subtask['testdatas']:
                                    await ChalService.inst.update_testdata_result(
                                        chal_id,
                                        TestdataResult(testdata_id, ChalConst.STATE_SKIPPED, 0, 0, "", MessageType.NONE)
                                    )

                        subtasks = [
                            subtask
                            for subtask in subtasks
                            if subtask['id'] in run_subtasks
                        ]


                await con.execute('UPDATE testdata_result SET state = $1 WHERE chal_id = $2 AND id = ANY($3);',
                                ChalConst.STATE_JUDGE, chal_id, list(need_judge_testdatas))
    except Exception as e:
        logger.error(f"Failed to update results for chal {chal_id}: {e} when emit_chal", exc_info=True)
        return ('Eunk', 'Unknown error'), None

    assert isinstance(config.spec_config, spec.config_type)
    testdatas = []
    for testdata_id in need_judge_testdatas:
        testdata = config.testdatas[testdata_id]
        testdatas.append(spec.build_judge_testdata(testdata))

    source_ext = COMPILER_INFOS[compiler_type].source_ext
    filenames = get_submission_filenames(spec, spec_config, source_ext)

    if any(not os.path.isfile(f"code/{chal_id}/{filename}") for filename in filenames):
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

    code_paths = [
        {"path": f"{chal_id}/{filename}", "name": filename}
        for filename in filenames
    ]
    checker_config = {}
    if spec.requires_checker:
        checker_config = {
            'checker_type': spec_config.checker_type,
            'checker_compiler': spec_config.checker_compiler,
            'checker_compile_args': spec_config.checker_compile_args,
        }
    await JudgeServerClusterService.inst.send(
        {
            **spec.build_judge_type_config(spec_config),
            **checker_config,
            'acct_id': acct_id,
            'pro_id': pro_id,
            'contest_id': contest_id,
            'chal_id': chal_id,

            'res_path': f'{pro_id}/res',
            # Keep code_path for compatibility with older judge workers.
            'code_path': code_paths[0]["path"],
            'code_paths': code_paths,

            'subtasks': subtasks,
            'testdatas': testdatas,

            'limit': {
                'output': limit.output * 1024,  # kib to bytes
                'time': limit.time * 10 ** 6,  # ms to ns
                'memory': limit.memory * 1024,  # kib to bytes
            },

            'has_grader': spec_config.has_grader,
            'userprog_compiler': compiler_type,
            'userprog_compile_args': spec_config.userprog_compile_args,

            'summary_type': spec_config.summary_type,
            'summary_compiler': spec_config.summary_compiler,
            'summary_compile_args': spec_config.summary_compile_args,

            'priority': priority,
            'skip_nonac': skip_nonac,
        },
        pro_id,
        contest_id,
    )
    await rs.hdel('rate', str(acct_id))

    return None, None


async def add_program_chal(
    spec,
    db,
    rs,
    pro_id: int,
    acct_id: int,
    contest_id: int,
    compiler_type: int,
    code: str | dict[str, str],
    config: ProblemConfig,
) -> tuple[None, int] | tuple[tuple[str, str], None]:
    """Add a compiled-program challenge."""
    from services.chal import COMPILER_INFOS

    pro_id = int(pro_id)
    acct_id = int(acct_id)

    assert isinstance(config.spec_config, spec.config_type)
    source_ext = COMPILER_INFOS[compiler_type].source_ext
    try:
        filenames = get_submission_filenames(spec, config.spec_config, source_ext)
        submission_files = get_submission_files(code, filenames)
    except (TypeError, ValueError):
        return ('Eparam', 'Invalid submitted source files'), None

    try:
        async with db.acquire() as con:
            async with con.transaction():
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

                try:
                    os.mkdir(f'code/{chal_id}')
                except FileExistsError:
                    logger.error(f"Directory code/{chal_id} already exists when adding chal {chal_id}")
                    raise
                except OSError as e:
                    logger.error(f"Failed to create directory code/{chal_id} for chal {chal_id}: {e}", exc_info=True)
                    raise

                try:
                    for filename, content in submission_files:
                        with open(f"code/{chal_id}/{filename}", 'wb') as code_f:
                            code_f.write(content.encode('utf-8'))
                except OSError as e:
                    try:
                        for filename, _ in submission_files:
                            try:
                                os.unlink(f"code/{chal_id}/{filename}")
                            except FileNotFoundError:
                                pass
                        os.rmdir(f'code/{chal_id}')
                    except OSError:
                        pass
                    logger.error(f"Failed to write code file for chal {chal_id}: {e}", exc_info=True)
                    raise
    except Exception as e:
        logger.error(f"Failed to add chal for pro_id {pro_id}, acct_id {acct_id}, contest_id {contest_id}: {e}", exc_info=True)
        return ('Eunk', 'Unknown error'), None

    return None, chal_id
