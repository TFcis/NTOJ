import os
from dataclasses import dataclass
from typing import Any

from services.pro import BaseTestdata, CheckerType, SummaryType, ProblemConfig
from services.prospec.base import ProSpec
from services.prospec.program import ProgramConfig

@dataclass(slots=True)
class BatchConfig(ProgramConfig):
    """
    Batch problem type specific configuration.

    - has_grader (bool): Whether the problem uses a Makefile-based compilation.
    See: https://wiki.tfcis.org/TOJ#Makefile%E9%A1%8C%E7%9B%AE_(%E7%B7%A8%E8%AD%AF%E4%BA%92%E5%8B%95%E9%A1%8C)

    - chalmeta (str): For IORedir Problem
    See: https://wiki.tfcis.org/TOJ#IORedir

    - checker_type (int): One of the values defined in ProConst.CHECKER_TYPE, indicating
    the type of checker (e.g., diff, float-diff, ioredir).
    """
    pass

@dataclass(slots=True)
class BatchTestdata(BaseTestdata):
    inputfile: str = ''
    outputfile: str = ''


class BatchProblemSpec(ProSpec):
    """Specification for Batch-type problems."""

    requires_checker = True

    def get_default_config(self) -> BatchConfig:
        from services.chal import Compiler
        return BatchConfig(
            chalmeta='',
            userprog_compile_args='',
            checker_type=CheckerType.DIFF,
            checker_compiler=None,
            checker_compile_args='',
            summary_type=SummaryType.GROUPMIN,
            summary_compiler=None,
            summary_compile_args='',
            has_grader=False,
            allow_compilers=set(compiler for compiler in Compiler),
        )

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

    config_type = BatchConfig

    def build_judge_testdata(self, testdata: BaseTestdata) -> dict[str, Any]:
        assert isinstance(testdata, BatchTestdata)
        return {
            "id": testdata.testdata_id,
            "input": testdata.inputfile,
            "output": testdata.outputfile,
        }

    def build_judge_type_config(self, config: BatchConfig) -> dict[str, Any]:
        return {}

    async def emit_chal(self, *args, **kwargs):
        from services.prospec.program import emit_program_chal
        return await emit_program_chal(self, *args, **kwargs)

    async def add_chal(self, *args, **kwargs):
        from services.prospec.program import add_program_chal
        return await add_program_chal(self, *args, **kwargs)

    def parse_testdata_files(self, testdata_id: int, files_json: dict[str, Any]) -> BatchTestdata:
        """Parse Batch testdata files JSON."""
        return BatchTestdata(
            testdata_id=testdata_id,
            inputfile=files_json.get('input', ''),
            outputfile=files_json.get('output', ''),
        )

    def build_testdata_files(self, testdata: BaseTestdata) -> dict[str, Any]:
        assert isinstance(testdata, BatchTestdata)
        """Build Batch testdata files JSON."""
        return {
            'input': testdata.inputfile,
            'output': testdata.outputfile,
        }

    async def unpack_pro(self, db, rs, pro_id: int, pack_token: str):
        from services.pro import ProType
        from services.prospec.package import unpack_program_package

        return await unpack_program_package(
            self, db, rs, pro_id, pack_token, ProType.BATCH
        )

    def parse_package_config(self, conf: dict[str, Any]) -> ProblemConfig:
        from services.chal import Compiler
        from services.prospec.package import parse_program_package

        common = parse_program_package(
            conf,
            lambda testdata_id, name: BatchTestdata(
                testdata_id=testdata_id,
                inputfile=f"{name}.in",
                outputfile=f"{name}.out",
            ),
        )
        return ProblemConfig(
            limits=common.limits,
            subtask_configs=common.subtask_configs,
            testdatas=common.testdatas,
            rate_precision=common.rate_precision,
            spec_config=BatchConfig(
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
            ),
        )

    def get_allowed_file_paths(self, config: BatchConfig, pro_id: int) -> list[str]:
        """Get allowed file paths for Batch problem type."""
        from services.chal import COMPILER_INFOS

        allowed_paths = ['http', 'res/checker', 'res/grader']

        if config.has_grader:
            used_grader = set()
            for compiler in config.allow_compilers:
                grader_name = COMPILER_INFOS[compiler].grader_name
                if grader_name in used_grader:
                    continue
                grader_path = os.path.join("problem", str(pro_id), "res", "grader", grader_name)
                if not os.path.exists(grader_path):
                    continue
                allowed_paths.append(f'res/grader/{grader_name}')
                used_grader.add(grader_name)

        return allowed_paths

    def get_file_structure(self, config: BatchConfig, pro_id: int) -> list[dict[str, Any]]:
        """Get the file structure for Batch problem type."""
        from services.chal import COMPILER_INFOS
        from services.filemanager import FileManager
        from natsort import natsorted
        from services.pro import CheckerType

        dirs = []

        if config.has_grader:
            used_grader = set()

            for compiler in config.allow_compilers:
                grader_name = COMPILER_INFOS[compiler].grader_name
                if grader_name in used_grader:
                    continue

                grader_path = os.path.join("problem", str(pro_id), "res", "grader", grader_name)
                if not os.path.exists(grader_path):
                    continue

                grader_file_mgr = FileManager(grader_path)
                files = list(natsorted(grader_file_mgr.listdir(only_files=True)))
                dirs.append({
                    'path': f'res/grader/{grader_name}',
                    'files': files,
                })
                used_grader.add(grader_name)

            grader_base_mgr = FileManager(f"problem/{pro_id}/res/grader")
            files = list(natsorted(grader_base_mgr.listdir(only_files=True)))
            dirs.append({
                'path': 'res/grader',
                'files': files,
            })

        if config.checker_type in CheckerType.need_build_checkers():
            checker_file_mgr = FileManager(f'problem/{pro_id}/res/checker')
            files = list(natsorted(checker_file_mgr.listdir(only_files=True)))
            dirs.append({
                'path': 'res/checker',
                'files': files,
            })

        http_file_mgr = FileManager(f'problem/{pro_id}/http')
        files = list(natsorted(http_file_mgr.listdir(only_files=True)))
        dirs.append({
            'path': 'http',
            'files': files,
        })

        return dirs


# Singleton instance
batch_spec = BatchProblemSpec()
