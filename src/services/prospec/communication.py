import enum
import os
from dataclasses import dataclass
from typing import Any

from services.pro import (
    BaseTestdata,
    CheckerType,
    ProblemConfig,
    SummaryType,
)
from services.prospec.base import ProSpec
from services.prospec.program import ProgramConfig


class CommunicationIOType(enum.IntEnum):
    STDIO = 0
    FIFO = 1


DEFAULT_SUBMISSION_FORMAT = ("main.%l",)


def normalize_submission_format(value: Any) -> tuple[str, ...]:
    """Validate CMS-style source filenames used by Communication tasks."""
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("submission_format must contain at least one filename")

    result = []
    for filename in value:
        if not isinstance(filename, str):
            raise ValueError("submission_format filenames must be strings")
        filename = filename.strip()
        if (
            not filename
            or filename.startswith(("-", "@"))
            or "\\" in filename
            or "\x00" in filename
            or filename != os.path.basename(filename)
            or filename in (".", "..")
            or filename.count("%l") != 1
            or not filename.endswith(".%l")
        ):
            raise ValueError(
                "Each submission filename must be a plain filename ending in .%l"
            )
        if filename in result:
            raise ValueError("submission_format contains duplicate filenames")
        result.append(filename)

    return tuple(result)


@dataclass(slots=True)
class CommunicationConfig(ProgramConfig):
    submission_format: tuple[str, ...]
    communication_io_type: CommunicationIOType
    num_processes: int
    manager_compiler: int
    manager_compile_args: str

    def __post_init__(self):
        self.submission_format = normalize_submission_format(self.submission_format)
        if self.num_processes < 1:
            raise ValueError("num_processes must be at least 1")


@dataclass(slots=True)
class CommunicationTestdata(BaseTestdata):
    inputfile: str = ""


class CommunicationProblemSpec(ProSpec):
    """Independent specification for Communication problems."""

    def get_initial_directories(self) -> tuple[str, ...]:
        return ("res/grader",)

    @staticmethod
    def _parse_io_type(value: Any) -> CommunicationIOType:
        if isinstance(value, str):
            value = value.strip().lower()
            if value == "stdio":
                return CommunicationIOType.STDIO
            if value == "fifo":
                return CommunicationIOType.FIFO
        return CommunicationIOType(int(value))

    @staticmethod
    def _parse_compiler(value: Any) -> int:
        from services.chal import ChalConst, Compiler

        if isinstance(value, str) and value in ChalConst.OLD_STR_2_COMPILER:
            return int(ChalConst.OLD_STR_2_COMPILER[value])
        return int(Compiler(int(value)))

    def get_default_config(self) -> CommunicationConfig:
        from services.chal import Compiler

        return CommunicationConfig(
            chalmeta="",
            userprog_compile_args="",
            checker_type=CheckerType.DIFF,
            checker_compiler=None,
            checker_compile_args="",
            summary_type=SummaryType.GROUPMIN,
            summary_compiler=None,
            summary_compile_args="",
            has_grader=False,
            allow_compilers={int(compiler) for compiler in Compiler},
            submission_format=DEFAULT_SUBMISSION_FORMAT,
            communication_io_type=CommunicationIOType.FIFO,
            num_processes=1,
            manager_compiler=int(Compiler.GPP),
            manager_compile_args="",
        )

    def from_json(self, data: dict[str, Any]) -> CommunicationConfig:
        from services.chal import Compiler

        checker_compiler = data.get("checker_compiler")
        summary_compiler = data.get("summary_compiler")
        return CommunicationConfig(
            chalmeta=data.get("chalmeta", ""),
            userprog_compile_args=data.get("userprog_compile_args", ""),
            checker_type=CheckerType(data["checker_type"]),
            checker_compiler=(
                Compiler(checker_compiler) if checker_compiler is not None else None
            ),
            checker_compile_args=data.get("checker_compile_args", ""),
            summary_type=SummaryType(data["summary_type"]),
            summary_compiler=(
                Compiler(summary_compiler) if summary_compiler is not None else None
            ),
            summary_compile_args=data.get("summary_compile_args", ""),
            has_grader=data.get("has_grader", False),
            allow_compilers=set(data.get("allow_compilers", [])),
            submission_format=normalize_submission_format(
                data.get("submission_format", DEFAULT_SUBMISSION_FORMAT)
            ),
            communication_io_type=self._parse_io_type(
                data.get("communication_io_type", CommunicationIOType.FIFO)
            ),
            num_processes=int(data.get("num_processes", 1)),
            manager_compiler=self._parse_compiler(data.get("manager_compiler", 3)),
            manager_compile_args=data.get("manager_compile_args", ""),
        )

    def to_json(self, config: CommunicationConfig) -> dict[str, Any]:
        return {
            "chalmeta": config.chalmeta,
            "userprog_compile_args": config.userprog_compile_args,
            "checker_type": int(config.checker_type),
            "checker_compiler": (
                int(config.checker_compiler) if config.checker_compiler else None
            ),
            "checker_compile_args": config.checker_compile_args,
            "summary_type": int(config.summary_type),
            "summary_compiler": (
                int(config.summary_compiler) if config.summary_compiler else None
            ),
            "summary_compile_args": config.summary_compile_args,
            "has_grader": config.has_grader,
            "allow_compilers": list(config.allow_compilers),
            "submission_format": list(config.submission_format),
            "communication_io_type": int(config.communication_io_type),
            "num_processes": config.num_processes,
            "manager_compiler": int(config.manager_compiler),
            "manager_compile_args": config.manager_compile_args,
        }

    config_type = CommunicationConfig

    def build_judge_testdata(self, testdata: BaseTestdata) -> dict[str, Any]:
        assert isinstance(testdata, CommunicationTestdata)
        return {"id": testdata.testdata_id, "input": testdata.inputfile}

    def build_judge_type_config(
        self, config: CommunicationConfig
    ) -> dict[str, Any]:
        return {
            "problem_type": "communication",
            "communication_io_type": config.communication_io_type,
            "num_processes": config.num_processes,
            "manager_compiler": config.manager_compiler,
            "manager_compile_args": config.manager_compile_args,
        }

    def get_submission_filenames(
        self, config: CommunicationConfig, source_ext: str
    ) -> list[str]:
        return [filename.replace("%l", source_ext) for filename in config.submission_format]

    async def emit_chal(self, *args, **kwargs):
        from services.prospec.program import emit_program_chal

        return await emit_program_chal(self, *args, **kwargs)

    async def add_chal(self, *args, **kwargs):
        from services.prospec.program import add_program_chal

        return await add_program_chal(self, *args, **kwargs)

    def parse_testdata_files(
        self, testdata_id: int, files_json: dict[str, Any]
    ) -> CommunicationTestdata:
        return CommunicationTestdata(
            testdata_id=testdata_id, inputfile=files_json.get("input", "")
        )

    def build_testdata_files(self, testdata: BaseTestdata) -> dict[str, Any]:
        assert isinstance(testdata, CommunicationTestdata)
        return {"input": testdata.inputfile}

    async def unpack_pro(self, db, rs, pro_id: int, pack_token: str):
        from services.pro import ProType
        from services.prospec.package import unpack_program_package

        return await unpack_program_package(
            self, db, rs, pro_id, pack_token, ProType.COMMUNICATION
        )

    def parse_package_config(self, conf: dict[str, Any]) -> ProblemConfig:
        from services.chal import Compiler
        from services.prospec.package import parse_program_package

        common = parse_program_package(
            conf,
            lambda testdata_id, name: CommunicationTestdata(
                testdata_id=testdata_id, inputfile=f"{name}.in"
            ),
        )
        return ProblemConfig(
            limits=common.limits,
            subtask_configs=common.subtask_configs,
            testdatas=common.testdatas,
            rate_precision=common.rate_precision,
            spec_config=CommunicationConfig(
                chalmeta=common.chalmeta,
                userprog_compile_args=common.userprog_compile_args,
                checker_type=common.checker_type,
                checker_compiler=int(Compiler.GPP),
                checker_compile_args="",
                summary_type=SummaryType.GROUPMIN,
                summary_compiler=int(Compiler.GPP),
                summary_compile_args="",
                has_grader=common.has_grader,
                allow_compilers=common.allow_compilers,
                submission_format=normalize_submission_format(
                    conf.get("submission_format", DEFAULT_SUBMISSION_FORMAT)
                ),
                communication_io_type=self._parse_io_type(
                    conf.get("communication_io_type", CommunicationIOType.FIFO)
                ),
                num_processes=int(conf.get("num_processes", 1)),
                manager_compiler=self._parse_compiler(
                    conf.get("manager_compiler", int(Compiler.GPP))
                ),
                manager_compile_args=conf.get("manager_compile_args", ""),
            ),
        )

    def get_allowed_file_paths(
        self, config: CommunicationConfig, pro_id: int
    ) -> list[str]:
        from services.chal import COMPILER_INFOS

        paths = ["http", "res/grader"]
        if config.has_grader:
            for grader_name in {
                COMPILER_INFOS[compiler].grader_name
                for compiler in config.allow_compilers
            }:
                grader_path = f"problem/{pro_id}/res/grader/{grader_name}"
                if os.path.isdir(grader_path):
                    paths.append(f"res/grader/{grader_name}")
        return paths

    def get_file_structure(
        self, config: CommunicationConfig, pro_id: int
    ) -> list[dict[str, Any]]:
        from natsort import natsorted
        from services.filemanager import FileManager

        return [
            {
                "path": path,
                "files": list(
                    natsorted(
                        FileManager(f"problem/{pro_id}/{path}").listdir(
                            only_files=True
                        )
                    )
                ),
            }
            for path in self.get_allowed_file_paths(config, pro_id)
        ]


communication_spec = CommunicationProblemSpec()
