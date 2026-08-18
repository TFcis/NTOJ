import json
import os
import shutil
from dataclasses import dataclass
from typing import Callable

from services.pro import BaseTestdata, Limit, SubtaskConfig
from services.prospec.registry import get_problem_spec, normalize_problem_type


@dataclass(slots=True)
class ProgramPackageConfig:
    limits: dict
    subtask_configs: dict[int, SubtaskConfig]
    testdatas: dict[int, BaseTestdata]
    chalmeta: str
    has_grader: bool
    allow_compilers: set[int]
    checker_type: int
    userprog_compile_args: str
    rate_precision: int


def parse_program_package(
    conf: dict, testdata_factory: Callable[[int, str], BaseTestdata]
) -> ProgramPackageConfig:
    """Parse fields shared by Batch and Communication packages."""
    from services.chal import ChalConst, Compiler
    from services.pro import ProConst

    has_grader = conf.get("compile") == "makefile" or bool(
        conf.get("has_grader", False)
    )
    if "limit" in conf:
        limits = {}
        for compiler_name, raw_limit in conf["limit"].items():
            compiler_key = compiler_name
            if compiler_name in ChalConst.OLD_STR_2_COMPILER:
                compiler_key = ChalConst.OLD_STR_2_COMPILER[compiler_name]
            elif compiler_name != "default":
                continue
            try:
                if "timelimit" in raw_limit and "memlimit" in raw_limit:
                    limits[compiler_key] = Limit(
                        max(int(raw_limit["timelimit"]), 0),
                        max(int(raw_limit["memlimit"]), 0),
                        65536,
                    )
                elif all(
                    key in raw_limit for key in ("time", "memory", "output")
                ):
                    limits[compiler_key] = Limit(
                        max(int(raw_limit["time"]), 0),
                        max(int(raw_limit["memory"]), 0),
                        max(int(raw_limit["output"]), 0),
                    )
            except (TypeError, ValueError):
                continue
        if "default" not in limits:
            raise ValueError("Problem limit config require default value")
    elif "timelimit" in conf and "memlimit" in conf:
        limits = {
            "default": Limit(
                int(conf["timelimit"]), int(conf["memlimit"]), 65536
            )
        }
    else:
        raise ValueError("Problem config require limit or timelimit/memlimit")

    testdatas: dict[int, BaseTestdata] = {}
    testdata_name_to_id: dict[str, int] = {}
    subtask_configs: dict[int, SubtaskConfig] = {}
    for subtask_id, test_conf in enumerate(conf["test"]):
        for raw_name in test_conf["data"]:
            name = os.path.basename(str(raw_name))
            if name not in testdata_name_to_id:
                testdata_id = len(testdata_name_to_id)
                testdata_name_to_id[name] = testdata_id
                testdatas[testdata_id] = testdata_factory(testdata_id, name)
        subtask_configs[subtask_id] = SubtaskConfig(
            subtask_id, [], set(), int(test_conf["weight"])
        )
    for subtask_id, test_conf in enumerate(conf["test"]):
        subtask_configs[subtask_id].testdatas = [
            testdatas[testdata_name_to_id[os.path.basename(str(name))]]
            for name in test_conf["data"]
        ]

    return ProgramPackageConfig(
        limits=limits,
        subtask_configs=subtask_configs,
        testdatas=testdatas,
        chalmeta=conf.get("metadata", ""),
        has_grader=has_grader,
        allow_compilers=(
            {int(Compiler.CLANGPP), int(Compiler.GPP)}
            if has_grader
            else {int(compiler) for compiler in Compiler}
        ),
        checker_type=ProConst.OLD_STR_2_CHECKER_TYPE[conf["check"]],
        userprog_compile_args=conf.get("userprog_compile_args", ""),
        rate_precision=int(conf.get("rate_precision", 0)),
    )


async def unpack_program_package(
    spec, db, rs, pro_id: int, pack_token: str, problem_type
):
    """Extract and apply a compiled-program problem package."""
    from services.pack import PackService
    from services.pro import ProService

    problem_dir = f"problem/{pro_id}"
    failed = True
    try:
        err, _ = await PackService.inst.unpack(pack_token, problem_dir, True)
        if err:
            return err, None
        os.chmod(os.path.abspath(problem_dir), 0o755)
        try:
            with open(f"{problem_dir}/conf.json") as conf_f:
                conf = json.load(conf_f)
            config = spec.parse_package_config(conf)
        except (OSError, json.JSONDecodeError):
            return ("Econf", "Problem config json syntax error"), None
        except (KeyError, TypeError, ValueError) as exc:
            return ("Econf", str(exc) or "Invalid problem config"), None

        await ProService.inst.update_pro_config(pro_id, problem_type, config)
        await rs.delete("prolist")
        failed = False
        return None, None
    finally:
        if failed and os.path.exists(problem_dir):
            shutil.rmtree(problem_dir)
        await PackService.inst.clear(pack_token)


async def unpack_problem_package(db, rs, pro_id: int, pack_token: str):
    """Inspect a package and delegate extraction to its independent ProSpec."""
    from services.pack import PackService

    err, conf = await PackService.inst.read_json_from_archive(pack_token, "conf.json")
    if err:
        await PackService.inst.clear(pack_token)
        return err, None
    try:
        spec = get_problem_spec(normalize_problem_type(conf.get("problem_type")))
    except ValueError:
        await PackService.inst.clear(pack_token)
        return ("Econf", "Invalid problem_type"), None
    except NotImplementedError:
        await PackService.inst.clear(pack_token)
        return ("Enotsupport", "Problem type not yet supported"), None
    return await spec.unpack_pro(db, rs, pro_id, pack_token)
