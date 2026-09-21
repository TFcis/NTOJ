import io
import json
import tarfile
from decimal import Decimal
from pathlib import Path

from services.chal import ChalConst, ChalService, Compiler
from services.pro import Limit, ProConst, ProService, ProType, SummaryType
from services.prospec.communication import (
    CommunicationConfig,
    CommunicationIOType,
    CommunicationTestdata,
)
from tests.integrated.util import AccountContext, AsyncTest

FIXTURE_ROOT = Path("tests/static_file/communication")
PROBLEM_ROOT = FIXTURE_ROOT / "problem"
CODE_ROOT = FIXTURE_ROOT / "code"


class CommunicationTest(AsyncTest):
    PRO_ID = 12

    @staticmethod
    def _problem_package(submission_format=None):
        package = io.BytesIO()
        with tarfile.open(fileobj=package, mode="w:xz") as archive:
            for path in sorted(PROBLEM_ROOT.rglob("*")):
                if path.is_file():
                    if path.name == 'conf.json' and submission_format is not None:
                        config = json.loads(path.read_text())
                        config['submission_format'] = submission_format
                        data = json.dumps(config).encode()
                        entry = tarfile.TarInfo('conf.json')
                        entry.size = len(data)
                        archive.addfile(entry, io.BytesIO(data))
                    else:
                        archive.add(path, arcname=path.relative_to(PROBLEM_ROOT))
        package.seek(0)
        return package

    async def _upload_problem(self, session):
        package = self._problem_package()
        pack_token = self.get_upload_token(session)
        await self.upload_file(package, len(package.getbuffer()), pack_token, session)
        res = session.post(
            "manage/pro/add",
            data={
                "reqtype": "addpro",
                "name": "Communication integration test",
                "status": ProConst.STATUS_ONLINE,
                "pack_token": pack_token,
                "mode": "upload",
            },
        )
        self.assertAPIReturnValue(res.text, ("S", self.PRO_ID))

    async def _assert_uploaded_problem(self):
        err, pro = await ProService.inst.get_pro(self.PRO_ID, ProConst.PRO_STATUS_FULL)
        self.assertIsNone(err)
        self.assertIsNotNone(pro)
        self.assertEqual(pro.name, "Communication integration test")
        self.assertEqual(pro.status, ProConst.STATUS_ONLINE)
        self.assertTrue(pro.allow_submit)
        self.assertEqual(pro.problem_type, ProType.COMMUNICATION)

        config = pro.config
        self.assertEqual(config.rate_precision, 2)
        self.assertEqual(config.limits["default"], Limit(time=200, memory=262144, output=65536))

        communication = config.spec_config
        self.assertIsInstance(communication, CommunicationConfig)
        self.assertEqual(communication.communication_io_type, CommunicationIOType.FIFO)
        self.assertEqual(communication.num_processes, 1)
        self.assertEqual(communication.manager_compiler, Compiler.GPP)
        self.assertEqual(communication.submission_format, ("main.%l",))

        self.assertEqual(set(config.testdatas), {0})
        testdata = config.testdatas[0]
        self.assertIsInstance(testdata, CommunicationTestdata)
        self.assertEqual(testdata.inputfile, "1.in")

        self.assertEqual(set(config.subtask_configs), {0})
        subtask = config.subtask_configs[0]
        self.assertEqual(subtask.rate, 100)
        self.assertEqual(subtask.dependency_subtasks, set())
        self.assertEqual([item.testdata_id for item in subtask.testdatas], [0])

        extracted_root = Path(f"problem/{self.PRO_ID}")
        for relative_path in (
            "conf.json",
            "res/grader/manager.cpp",
            "res/testdata/1.in",
        ):
            self.assertEqual(
                (extracted_root / relative_path).read_bytes(),
                (PROBLEM_ROOT / relative_path).read_bytes(),
            )
        self.assertFalse((extracted_root / "res/testdata/1.out").exists())
        self.assertFalse((extracted_root / "res/checker").exists())

    def _submit(self, session, source_name):
        res = session.post(
            "submit",
            data={
                "reqtype": "submit",
                "pro_id": self.PRO_ID,
                "codes": json.dumps({"main.%l": (CODE_ROOT / source_name).read_text()}),
                "compiler_type": Compiler.GPP,
            },
        )
        res = json.loads(res.text)
        self.assertEqual(res["status"], "S")
        return int(res["data"])

    async def _assert_state(self, chal_id, state):
        err, chal = await ChalService.inst.get_chal(chal_id, with_result=True)
        self.assertIsNone(err)
        self.assertEqual(chal.total_result.state, state)
        return chal

    async def _replace_manager(self, session, fixture_path):
        path = FIXTURE_ROOT / fixture_path
        pack_token = self.get_upload_token(session)
        with path.open("rb") as source:
            await self.upload_file(source, path.stat().st_size, pack_token, session)
        res = session.post(
            "manage/pro/filemanager",
            data={
                "reqtype": "updatesinglefile",
                "pro_id": self.PRO_ID,
                "filename": "manager.cpp",
                "path": "res/grader",
                "pack_token": pack_token,
            },
        )
        self.assertAPIReturnSuccess(res.text)

    async def _rejudge(self, session, chal_id):
        def callback():
            res = session.post("submit", data={"reqtype": "rechal", "chal_id": chal_id})
            self.assertAPIReturnValue(res.text, ("S", chal_id))

        await self.wait_for_judge_finish(callback)

    async def _test_package_source_rename(self, session, smoke_id, partial_id):
        async def upload(filename):
            package = self._problem_package([filename])
            token = self.get_upload_token(session)
            await self.upload_file(package, len(package.getbuffer()), token, session)
            return session.post('manage/pro/update', data={
                'reqtype': 'uploadpackage', 'pro_id': self.PRO_ID, 'pack_token': token,
            })

        original = Path(f'code/{smoke_id}/main.cpp').read_bytes()
        res = await upload('solution.%l')
        self.assertAPIReturnSuccess(res.text)
        self.assertEqual(Path(f'code/{smoke_id}/solution.cpp').read_bytes(), original)
        self.assertFalse(Path(f'code/{smoke_id}/main.cpp').exists())
        await self._rejudge(session, smoke_id)
        await self._assert_state(smoke_id, ChalConst.STATE_AC)

        conflict = Path(f'code/{partial_id}/other.cpp')
        conflict.write_text('existing challenge source')
        try:
            res = await upload('other.%l')
            self.assertEqual(json.loads(res.text)['status'], 'Econf')
            self.assertEqual(Path(f'code/{smoke_id}/solution.cpp').read_bytes(), original)
            self.assertFalse(Path(f'code/{smoke_id}/other.cpp').exists())
            self.assertEqual(conflict.read_text(), 'existing challenge source')
            err, pro = await ProService.inst.get_pro(self.PRO_ID, ProConst.PRO_STATUS_FULL)
            self.assertIsNone(err)
            self.assertEqual(pro.config.spec_config.submission_format, ('solution.%l',))
            self.assertEqual(
                Path(f'problem/{self.PRO_ID}/res/grader/manager.cpp').read_bytes(),
                (PROBLEM_ROOT / 'res/grader/manager.cpp').read_bytes(),
            )
            await self._rejudge(session, smoke_id)
            await self._assert_state(smoke_id, ChalConst.STATE_AC)
        finally:
            conflict.unlink()

    async def _test_custom_summary_upload(self, session):
        res = session.post('manage/pro/updatejudge', data={
            'pro_id': self.PRO_ID, 'rate_precision': 2, 'checker_type': 1,
            'has_grader': 'false', 'userprog_compile_args': '',
            'summary_type': SummaryType.CUSTOM, 'summary_compiler': Compiler.GPP,
            'summary_compile_args': '', 'allow_compilers[]': [Compiler.GPP],
            'communication_io_type': CommunicationIOType.FIFO, 'num_processes': 1,
            'manager_compiler': Compiler.GPP, 'submission_format': 'answer.%l',
        })
        self.assertAPIReturnSuccess(res.text)
        source = (CODE_ROOT / 'smoke.cpp').read_bytes()
        err, pro = await ProService.inst.get_pro(self.PRO_ID, ProConst.PRO_STATUS_FULL)
        self.assertIsNone(err)
        self.assertEqual(pro.config.spec_config.submission_format, ('answer.%l',))
        token = self.get_upload_token(session)
        await self.upload_file(io.BytesIO(source), len(source), token, session)
        res = session.post('manage/pro/filemanager', data={
            'reqtype': 'addsinglefile', 'pro_id': self.PRO_ID,
            'filename': 'summary.cpp', 'path': 'res/summary', 'pack_token': token,
        })
        self.assertAPIReturnSuccess(res.text)
        self.assertEqual(Path(f'problem/{self.PRO_ID}/res/summary/summary.cpp').read_bytes(), source)
        self.assertIn('res/summary', session.get(f'manage/pro/filemanager?pro_id={self.PRO_ID}').text)

    async def main(self):
        with AccountContext("admin@test", "testtest") as admin_session:
            await self._upload_problem(admin_session)
            await self._assert_uploaded_problem()

            smoke_id = None

            def submit_smoke():
                nonlocal smoke_id
                smoke_id = self._submit(admin_session, "smoke.cpp")

            await self.wait_for_judge_finish(submit_smoke)
            await self._assert_state(smoke_id, ChalConst.STATE_AC)

            challenge_ids = {}

            def submit_failures():
                challenge_ids["tle"] = self._submit(admin_session, "tle.cpp")
                challenge_ids["re"] = self._submit(admin_session, "re.cpp")
                challenge_ids["ce"] = self._submit(admin_session, "ce.cpp")

            await self.wait_for_judge_finish(submit_failures)
            await self._assert_state(challenge_ids["tle"], ChalConst.STATE_TLE)
            await self._assert_state(challenge_ids["re"], ChalConst.STATE_RE)
            await self._assert_state(challenge_ids["ce"], ChalConst.STATE_CE)

            for broken_manager in ("manager/re.cpp", "manager/tle.cpp"):
                await self._replace_manager(admin_session, broken_manager)
                await self._rejudge(admin_session, smoke_id)
                await self._assert_state(smoke_id, ChalConst.STATE_JE)

            await self._replace_manager(admin_session, "problem/res/grader/manager.cpp")
            await self._rejudge(admin_session, smoke_id)
            await self._assert_state(smoke_id, ChalConst.STATE_AC)

            partial_id = None

            def submit_partial():
                nonlocal partial_id
                partial_id = self._submit(admin_session, "partial.cpp")

            await self.wait_for_judge_finish(submit_partial)
            chal = await self._assert_state(partial_id, ChalConst.STATE_PC)
            self.assertEqual(chal.total_result.rate, Decimal("37.50"))
            await self._test_package_source_rename(admin_session, smoke_id, partial_id)
            await self._test_custom_summary_upload(admin_session)
