import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from services.chal import ChalConst, Compiler
from services.pro import (
    CheckerType,
    Limit,
    ProblemConfig,
    ProConst,
    ProService,
    ProType,
    SubtaskConfig,
)
from services.prospec.communication import (
    CommunicationConfig,
    CommunicationIOType,
    CommunicationProblemSpec,
    CommunicationTestdata,
    normalize_submission_format,
)
from services.prospec.program import (
    build_program_limits,
    get_submission_files,
    rename_submission_files,
)


class TestCommunicationConfig(unittest.TestCase):
    def setUp(self):
        self.spec = CommunicationProblemSpec()

    def test_json_round_trip(self):
        config = self.spec.get_default_config()
        config.communication_io_type = CommunicationIOType.FIFO
        config.num_processes = 3
        config.manager_compiler = Compiler.GPP
        config.manager_compile_args = "-O2"
        config.submission_format = ("alice.%l", "bob.%l")

        restored = self.spec.from_json(self.spec.to_json(config))

        self.assertEqual(restored, config)

    def test_fifo_is_the_default_io_type(self):
        config = self.spec.get_default_config()
        self.assertEqual(config.communication_io_type, CommunicationIOType.FIFO)

        serialized = self.spec.to_json(config)
        del serialized["communication_io_type"]
        restored = self.spec.from_json(serialized)
        self.assertEqual(restored.communication_io_type, CommunicationIOType.FIFO)

    def test_submission_format_validation_and_resolution(self):
        config = self.spec.get_default_config()
        config.submission_format = normalize_submission_format(
            ["alice.%l", "bob.%l"]
        )
        self.assertEqual(
            self.spec.get_submission_filenames(config, "cpp"),
            ["alice.cpp", "bob.cpp"],
        )
        self.assertEqual(
            get_submission_files(
                {"bob.cpp": "B", "alice.cpp": "A"},
                ["alice.cpp", "bob.cpp"],
            ),
            [("alice.cpp", "A"), ("bob.cpp", "B")],
        )
        with self.assertRaises(ValueError):
            normalize_submission_format(["../alice.%l"])

    def test_testdata_has_input_only(self):
        testdata = CommunicationTestdata(7, inputfile="sample.in")

        files = self.spec.build_testdata_files(testdata)

        self.assertEqual(files, {"input": "sample.in"})
        self.assertFalse(hasattr(testdata, "outputfile"))

    def test_num_processes_must_be_positive(self):
        config = self.spec.to_json(self.spec.get_default_config())
        config["num_processes"] = 0
        with self.assertRaises(ValueError):
            self.spec.from_json(config)

    def test_existing_submission_files_are_renamed(self):
        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tempdir:
            try:
                os.chdir(tempdir)
                os.makedirs("code/10")
                with open("code/10/a.cpp", "w", encoding="utf-8") as source:
                    source.write("alice")

                rename_submission_files(10, ["a.cpp"], ["b.cpp"])

                self.assertFalse(os.path.exists("code/10/a.cpp"))
                with open("code/10/b.cpp", encoding="utf-8") as source:
                    self.assertEqual(source.read(), "alice")

                with open("code/10/c.cpp", "w", encoding="utf-8") as source:
                    source.write("charlie")
                rename_submission_files(
                    10,
                    ["b.cpp", "c.cpp"],
                    ["c.cpp", "b.cpp"],
                )
                with open("code/10/b.cpp", encoding="utf-8") as source:
                    self.assertEqual(source.read(), "charlie")
                with open("code/10/c.cpp", encoding="utf-8") as source:
                    self.assertEqual(source.read(), "alice")
            finally:
                os.chdir(original_cwd)


class TestCommunicationEmit(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.spec = CommunicationProblemSpec()
        self.connection = AsyncMock()
        transaction = MagicMock()
        transaction.__aenter__ = AsyncMock(return_value=None)
        transaction.__aexit__ = AsyncMock(return_value=None)
        self.connection.transaction = MagicMock(return_value=transaction)
        acquire = MagicMock()
        acquire.__aenter__ = AsyncMock(return_value=self.connection)
        acquire.__aexit__ = AsyncMock(return_value=None)
        self.db = MagicMock()
        self.db.acquire.return_value = acquire
        self.rs = AsyncMock()

        spec_config = self.spec.get_default_config()
        spec_config.communication_io_type = CommunicationIOType.FIFO
        spec_config.num_processes = 2
        spec_config.manager_compiler = Compiler.GPP
        spec_config.manager_compile_args = "-O2"
        spec_config.submission_format = ("alice.%l", "bob.%l")
        testdata = CommunicationTestdata(0, inputfile="sample.in")
        self.config = ProblemConfig(
            limits={"default": Limit(1000, 262144, 65536)},
            subtask_configs={0: SubtaskConfig(0, [testdata], set(), 100)},
            testdatas={0: testdata},
            rate_precision=0,
            spec_config=spec_config,
        )

    @patch("os.path.isfile", return_value=True)
    @patch("services.judge.JudgeServerClusterService")
    async def test_emit_communication_payload(self, judge_service, _isfile):
        judge_service.inst = MagicMock()
        judge_service.inst.send = AsyncMock()

        err, _ = await self.spec.emit_chal(
            self.db,
            self.rs,
            chal_id=10,
            pro_id=20,
            acct_id=30,
            contest_id=0,
            compiler_type=Compiler.GPP,
            config=self.config,
            priority=ChalConst.NORMAL_PRI,
        )

        self.assertIsNone(err)
        payload = judge_service.inst.send.call_args.args[0]
        self.assertEqual(payload["problem_type"], "communication")
        self.assertEqual(payload["communication_io_type"], CommunicationIOType.FIFO)
        self.assertEqual(payload["num_processes"], 2)
        self.assertEqual(payload["manager_compiler"], Compiler.GPP)
        self.assertEqual(payload["manager_compile_args"], "-O2")
        self.assertNotIn("checker_type", payload)
        self.assertNotIn("checker_compiler", payload)
        self.assertNotIn("checker_compile_args", payload)
        self.assertEqual(
            payload["code_paths"],
            [
                {"path": "10/alice.cpp", "name": "alice.cpp"},
                {"path": "10/bob.cpp", "name": "bob.cpp"},
            ],
        )
        self.assertEqual(payload["testdatas"], [{"id": 0, "input": "sample.in"}])
        self.assertNotIn("output", payload["testdatas"][0])


class TestCommunicationLimits(unittest.TestCase):
    def test_build_compiler_limits(self):
        spec_config = CommunicationProblemSpec().get_default_config()
        spec_config.allow_compilers = {Compiler.GPP}
        limits = build_program_limits(
            {
                "default": {
                    "time": 1000,
                    "memory": 262144,
                    "output": 65536,
                },
                str(Compiler.GPP): {
                    "time": 2000,
                    "memory": 524288,
                    "output": 131072,
                },
                str(Compiler.PYTHON3): {
                    "time": 3000,
                    "memory": 524288,
                    "output": 131072,
                },
            },
            spec_config.allow_compilers,
        )

        self.assertEqual(limits["default"], Limit(1000, 262144, 65536))
        self.assertEqual(
            limits[str(Compiler.GPP)], Limit(2000, 524288, 131072)
        )
        self.assertNotIn(str(Compiler.PYTHON3), limits)


class TestCommunicationUnpack(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.spec = CommunicationProblemSpec()
        self.tempdir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.tempdir)
        os.makedirs("problem/1/res/testdata")
        with open("problem/1/conf.json", "w") as conf_f:
            json.dump(
                {
                    "problem_type": "communication",
                    "timelimit": 1000,
                    "memlimit": 262144,
                    "metadata": "",
                    "check": "cms",
                    "communication_io_type": "fifo",
                    "num_processes": 2,
                    "manager_compiler": "g++",
                    "manager_compile_args": "-O2",
                    "submission_format": ["alice.%l", "bob.%l"],
                    "compile": "makefile",
                    "test": [{"data": ["sample-1"], "weight": 100}],
                },
                conf_f,
            )

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.tempdir)

    @patch("services.pro.ProService")
    @patch("services.pack.PackService")
    async def test_unpack_builds_input_only_config(self, pack_service, pro_service):
        pack_service.inst = MagicMock()
        pack_service.inst.unpack = AsyncMock(return_value=(None, None))
        pack_service.inst.clear = AsyncMock()
        pro_service.inst = MagicMock()
        pro_service.inst.update_pro_config = AsyncMock(return_value=(None, None))
        rs = AsyncMock()

        err, _ = await self.spec.unpack_pro(MagicMock(), rs, 1, "token")

        self.assertIsNone(err)
        pro_id, problem_type, config = pro_service.inst.update_pro_config.call_args.args
        self.assertEqual(pro_id, 1)
        self.assertEqual(problem_type, ProType.COMMUNICATION)
        self.assertIsInstance(config.spec_config, CommunicationConfig)
        self.assertEqual(config.spec_config.communication_io_type, CommunicationIOType.FIFO)
        self.assertEqual(config.spec_config.num_processes, 2)
        self.assertEqual(
            config.spec_config.submission_format, ("alice.%l", "bob.%l")
        )
        self.assertEqual(config.testdatas[0].inputfile, "sample-1.in")
        self.assertFalse(hasattr(config.testdatas[0], "outputfile"))


class TestManualCommunicationCreation(unittest.IsolatedAsyncioTestCase):
    async def test_add_problem_uses_communication_defaults(self):
        connection = AsyncMock()
        connection.fetch.return_value = [{"pro_id": 15}]
        transaction = MagicMock()
        transaction.__aenter__ = AsyncMock(return_value=None)
        transaction.__aexit__ = AsyncMock(return_value=None)
        connection.transaction = MagicMock(return_value=transaction)
        acquire = MagicMock()
        acquire.__aenter__ = AsyncMock(return_value=connection)
        acquire.__aexit__ = AsyncMock(return_value=None)
        db = MagicMock()
        db.acquire.return_value = acquire
        redis = AsyncMock()
        service = ProService(db, redis)

        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tempdir:
            try:
                os.chdir(tempdir)
                os.mkdir("problem")
                err, pro_id = await service.add_pro(
                    "communication",
                    ProConst.STATUS_HIDDEN,
                    ProType.COMMUNICATION,
                )
                grader_exists = os.path.isdir("problem/15/res/grader")
            finally:
                os.chdir(original_cwd)

        self.assertIsNone(err)
        self.assertEqual(pro_id, 15)
        insert = connection.fetch.call_args.args
        self.assertEqual(insert[3], int(ProType.COMMUNICATION))
        config = json.loads(insert[4])
        self.assertEqual(config["submission_format"], ["main.%l"])
        self.assertEqual(config["num_processes"], 1)
        self.assertEqual(
            config["communication_io_type"], int(CommunicationIOType.FIFO)
        )
        self.assertTrue(grader_exists)
        redis.delete.assert_awaited_once_with("prolist")


if __name__ == "__main__":
    unittest.main()
