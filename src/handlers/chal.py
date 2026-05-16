import zipfile
import os
import decimal
import json
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from typing import IO

import structlog
import tornado.escape

from handlers.base import (
    ActionDispatcher,
    RequestHandler,
    UnifiedWebSocketHandler,
    reqenv,
    require_permission,
)
from handlers.contests.base import contest_require_permission
from services.chal import (
    ChalService,
    ChalSearchingParamBuilder,
    ChalConst,
    Compiler,
    COMPILER_INFOS,
    MessageType,
    Challenge,
)
from services.pro import ProService, ProConst
from services.user import UserService, UserConst
from services.contests import UserStatus, ContestService
from services.rate import RateService
from services.log import LogService
from utils.numeric import parse_str_to_list

chal_dispatcher = ActionDispatcher()


class ChalListCallback:
    """Callback for new challenge list notifications - simple message forwarding"""

    async def register(self, conn):
        """Registering does not require special handling"""
        pass

    async def message(self, conn, data):
        """Directly forward the notification"""
        return data

    async def unregister(self, conn):
        """Unsubscribing does not require special handling"""
        pass


# Register callback
_challist_callback = ChalListCallback()
UnifiedWebSocketHandler.register_channel_callback("challist_sub", _challist_callback)

class _Encoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return str(o)
        elif is_dataclass(o):
            return asdict(o)
        return super().default(o)

class ChalListStateCallback:
    """Callback for challenge list state updates

    Manages per-connection state for filtering challenge updates by chalids
    and user permissions.
    """

    def __init__(self):
        self.conn_state = {}

    async def register(self, conn):
        """Called when a connection subscribes to challiststatesub"""
        self.conn_state[conn] = {
            'chals': {},
        }

    async def message(self, conn, data):
        """Called when a message is received on challiststatesub channel

        Args:
            conn: WebSocket connection
            data: Challenge ID from Redis

        Returns:
            Formatted challenge data JSON string, or None to skip

        Normal
        full data

        Contest
        Not Started
            If viewer is admin: full data
            Else: deny

        Running
            If viewer is admin: full data
            If owner equals viewer: full data
            Else: deny

        Ended
            If viewer is admin: full data
            If owner equals viewer: full data
            If owner not equal to viewer and owner is not admin: remove response message, CE/IE details
            Else: deny
        """
        chal_id = int(data)
        if chal_id not in self.conn_state.get(conn, {}).get('chals', {}):
            return None  # Skip this connection

        chal: Challenge = self.conn_state[conn]['chals'][chal_id]
        err, viewer = await UserService.inst.info_acct(conn.acct_id)
        if err:
            return None

        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        if viewer.is_kernel():
            allow_statuses = ProConst.PRO_STATUS_FULL
        if chal.contest_id != 0:
            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER
        err, _ = await ProService.inst.get_pro(chal.pro_id, allow_statuses)
        if err:
            return None

        async def gen():
            _, total_result = await ChalService.inst.get_total_result(chal_id)
            return json.dumps({"chal_id": chal_id, **asdict(total_result)}, cls=_Encoder)

        if chal.contest_id != 0:
            err, contest = await ContestService.inst.get_contest(chal.contest_id)
            if err:
                return None

            if contest.is_admin(acct_id=viewer.acct_id):
                return await gen()

            if contest.is_running():
                if viewer.acct_id == chal.acct_id:
                    return await gen()

            elif contest.is_end():
                if viewer.acct_id == chal.acct_id:
                    return await gen()
                if not contest.is_admin(acct_id=chal.acct_id) and contest.is_public_scoreboard:
                    return await gen()
                return None

            return None

        return await gen()


    async def unregister(self, conn):
        """Called when a connection unsubscribes from challiststatesub"""
        self.conn_state.pop(conn, None)

    async def init(self, conn, chalids: list[int]):
        """Initialize connection state with chalids and user permissions

        This should be called from the challiststatesub_init message handler.
        """
        if conn not in self.conn_state:
            self.conn_state[conn] = {
                'chals': {},
            }

        state = self.conn_state[conn]
        for chal_id in chalids:
            err, chal = await ChalService.inst.get_chal(chal_id, with_result=False)
            if err:
                state['chals'][chal_id] = None
                continue

            state['chals'][chal_id] = chal

    async def handle_custom_message(self, conn, msg_type, msg_data):
        """Handle custom message types for this channel

        Args:
            conn: WebSocket connection
            msg_type: Message type
            msg_data: Message data

        Returns:
            True if handled, False if not handled by this callback
        """

        if msg_type == "challiststatesub_init":
            try:
                init_data = json.loads(msg_data)
                chalids = init_data.get("chalids", [])

                await self.init(conn, chalids)
                return True  # Handled
            except Exception as e:
                return True  # Handled (but failed)

        return False  # Not handled by this callback


_challist_state_callback = ChalListStateCallback()
UnifiedWebSocketHandler.register_channel_callback("challiststatesub", _challist_state_callback)


class ChalStateCallback:
    """Callback for single challenge state updates

    Manages per-connection state for filtering single challenge updates.
    """

    def __init__(self):
        self.conn_state = {}

    async def register(self, conn: UnifiedWebSocketHandler):
        """Called when a connection subscribes to chalstatesub"""
        self.conn_state[conn] = {
            'chal': None,
        }

    async def message(self, conn: UnifiedWebSocketHandler, data):
        """Called when a message is received on chalstatesub channel

        Args:
            conn: WebSocket connection instance
            data: JSON string containing {'chal_id': int, ...}

        Returns:
            str: Message data if chal_id matches
            None: Skip this connection if chal_id doesn't match

        Normal
        Viewer as owner or admin: full data
        If problem status equal to hideen: deny
        Viewer not equal to owner and viewer is not admin: remove response message, CE/IE details

        Contest
        Not Started
            If viewer is admin: full data
            Else: deny

        Running
            If viewer is admin: full data
            If owner equals viewer: full data
            Else: deny

        Ended
            If viewer is admin: full data
            If owner equals viewer: full data
            If owner not equal to viewer and owner is not admin: remove response message, CE/IE details
            Else: deny
        """

        state = self.conn_state.get(conn)
        if not state or state['chal'] is None:
            return None
        chal: Challenge = state['chal']

        msg_data = json.loads(data)
        if msg_data.get('chal_id') != chal.chal_id:
            return None  # Skip this connection


        err, viewer = await UserService.inst.info_acct(conn.acct_id)
        if err:
            return None

        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        if viewer.is_kernel():
            allow_statuses = ProConst.PRO_STATUS_FULL
        if chal.contest_id != 0:
            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER
        err, _ = await ProService.inst.get_pro(chal.pro_id, allow_statuses)
        if err:
            return None

        def sanitize():
            nonlocal msg_data
            try:
                if 'total_result' in msg_data and isinstance(msg_data['total_result'], dict):
                    total_result = msg_data['total_result']
                    total_result['ce_message'] = ''
                    total_result['ie_message'] = ''
                    total_result['message_type'] = MessageType.NONE.value

                if 'testdata_results' in msg_data and isinstance(msg_data['testdata_results'], dict):
                    for td in msg_data['testdata_results'].values():
                        if isinstance(td, dict):
                            td['message'] = ''
                            td['message_type'] = MessageType.NONE.value

                if 'message' in msg_data:
                    msg_data['message'] = ''
                    if 'message_type' in msg_data:
                        msg_data['message_type'] = MessageType.NONE.value
            except Exception:
                # In case of any unexpected data structure, fail-safe to not reveal data
                if 'message' in msg_data:
                    msg_data['message'] = ''
                if 'total_result' in msg_data and isinstance(msg_data['total_result'], dict):
                    msg_data['total_result']['ce_message'] = ''
                    msg_data['total_result']['ie_message'] = ''
                    msg_data['total_result']['message_type'] = MessageType.NONE.value
            return json.dumps(msg_data)


        if chal.contest_id != 0:
            err, contest = await ContestService.inst.get_contest(chal.contest_id)
            if err:
                return None

            if contest.is_admin(acct_id=viewer.acct_id):
                return data

            if contest.is_running():
                if viewer.acct_id == chal.acct_id:
                    return data
                return None

            if contest.is_end():
                if viewer.acct_id == chal.acct_id:
                    return data
                if not contest.is_admin(acct_id=chal.acct_id) and contest.is_public_scoreboard:
                    return sanitize()
                return None

            return None

        # NOTE: normal
        if viewer.is_kernel():
            return data

        if viewer.acct_id == chal.acct_id:
            return data

        return sanitize()

    async def unregister(self, conn: UnifiedWebSocketHandler):
        """Called when a connection unsubscribes or closes"""
        self.conn_state.pop(conn, None)

    async def handle_custom_message(self, conn: UnifiedWebSocketHandler, msg_type, msg_data):
        """Handle custom initialization message

        Expects a plain integer string as the chal_id
        """
        if msg_type == 'chalstatesub_init':
            try:
                chal_id = int(msg_data)
                state = self.conn_state.get(conn)
                if state is None:
                    self.conn_state[conn] = {'chal': None}
                    state = self.conn_state[conn]

                err, chal = await ChalService.inst.get_chal(chal_id, with_result=False)
                if err:
                    return True  # Handled (but we won't set chal)

                state['chal'] = chal
                return True  # Handled
            except Exception:
                return True  # Handled (but failed)

        return False  # Not handled by this callback


_chal_state_callback = ChalStateCallback()
UnifiedWebSocketHandler.register_channel_callback("chalstatesub", _chal_state_callback)


class ChalListHandler(RequestHandler):
    @reqenv
    async def get(self):
        try:
            pageoff = int(self.get_argument("pageoff", default="0"))
            if pageoff < 0:
                pageoff = 0
        except ValueError:
            return self.error(("Eparam", "Invalid page offset"))
        try:
            state = int(self.get_argument("state", default="0"))
            if state != 0 and state not in ChalConst.STATE_STR: # NOTE: 0 stands for all states
                raise ValueError()
        except ValueError:
            return self.error(("Eparam", "Invalid state"))

        try:
            compiler_type = int(self.get_argument("compiler_type", default="-1"))
            if compiler_type != -1:
                Compiler(compiler_type)
        except ValueError:
            return self.error(("Eparam", "Invalid compiler type"))

        ppro_id = self.get_argument("proid", default="")
        pacct_id = self.get_argument("acctid", default="")


        query_pros = self._parse_problem_filter(ppro_id)
        query_accts = self._parse_account_filter(pacct_id)

        flt_builder = ChalSearchingParamBuilder()
        flt_builder.state(state).compiler(compiler_type)

        isadmin = self._setup_permissions(flt_builder)
        query_accts = self._apply_contest_filters(flt_builder, query_accts, isadmin)

        flt = flt_builder.pro(query_pros).acct(query_accts).build()
        _, chal_cnt = await ChalService.inst.get_chals_count(flt)
        _, challist = await ChalService.inst.list_chal(pageoff, 20, flt)

        for chal in challist:
            chal.compiler_type = COMPILER_INFOS[chal.compiler_type].version_name

        await self.render(
            "challist",
            chal_cnt=chal_cnt,
            challist=challist,
            flt=flt,
            pageoff=pageoff,
            ppro_id=ppro_id,
            pacct_id=pacct_id,
            isadmin=isadmin,
            contest=self.contest,
        )

    def _parse_problem_filter(self, ppro_id: str) -> list[int] | None:
        query_pros = parse_str_to_list(ppro_id)
        return None if len(query_pros) == 0 else query_pros

    def _parse_account_filter(self, pacct_id: str) -> list[int] | None:
        query_accts = parse_str_to_list(pacct_id)
        return None if len(query_accts) == 0 else query_accts

    def _setup_permissions(self, flt_builder: ChalSearchingParamBuilder) -> bool:
        isadmin = self.acct.is_kernel()
        if isadmin:
            flt_builder.pro_statuses(ProConst.PRO_STATUS_KERNEL_USER)
        return isadmin

    def _apply_contest_filters(
        self,
        flt_builder: ChalSearchingParamBuilder,
        query_accts: list[int] | None,
        isadmin: bool,
    ) -> list[int] | None:
        if not self.contest:
            return query_accts

        isadmin = self.contest.is_admin(self.acct)
        flt_builder.contest(self.contest.contest_id)
        flt_builder.pro_statuses(ProConst.PRO_STATUS_CONTEST_USER)

        if isadmin:
            return query_accts

        return self._get_non_admin_contest_accounts(query_accts)

    def _get_non_admin_contest_accounts(
        self, query_accts: list[int] | None
    ) -> list[int]:
        if not self.contest.is_start():
            return []

        if self.contest.is_running():
            return [self.acct.acct_id]

        return self._get_post_contest_accounts(query_accts)

    def _get_post_contest_accounts(self, query_accts: list[int] | None) -> list[int]:
        if not self.contest.is_public_scoreboard:
            return [self.acct.acct_id]

        if query_accts is None:
            approved_accts = [
                acct_id
                for acct_id, v in self.contest.user_list.items()
                if v["status"] == UserStatus.APPROVED
            ]
            return approved_accts if approved_accts else []
        else:
            return [
                acct_id
                for acct_id in query_accts
                if not self.contest.is_admin(acct_id=acct_id)
            ]


class ChalHandler(RequestHandler):
    @reqenv
    @contest_require_permission("all")
    async def get(self, chal_id: int = None):
        try:
            chal_id = int(chal_id)
        except (ValueError, TypeError):
            return self.error(("Eparam", "Invalid challenge id"))

        err, chal = await ChalService.inst.get_chal(chal_id, with_result=True)
        if err:
            return self.error(err)

        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        if chal.contest_id and not self.contest:
            return self.error(("Enoext", "Contest not found"))

        elif self.contest:
            if not self.contest.is_start():
                if self.contest.is_admin(
                    acct_id=chal.acct_id
                ) and not self.contest.is_admin(self.acct):
                    return self.error(("Eacces", "Permission denied"))

            elif self.contest.is_running():
                if (
                    self.contest.hide_admin
                    and self.contest.is_admin(acct_id=chal.acct_id)
                    and not self.contest.is_admin(self.acct)
                ) or (
                    not self.contest.hide_admin
                    and not (self.acct.acct_id == chal.acct_id or self.contest.is_admin(self.acct))
                ):
                    return self.error(("Eacces", "Permission denied"))

            # After contest: if scoreboard not public, only own or admin can view
            if not self.contest.is_running() and not self.contest.is_public_scoreboard:
                if not (self.acct and (self.acct.acct_id == chal.acct_id or self.contest.is_admin(self.acct))):
                    return self.error(("Eacces", "Permission denied"))
            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER

        elif self.acct.is_kernel():
            allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

        err, pro = await ProService.inst.get_pro(chal.pro_id, allow_statuses)
        if err:
            return self.error(err)

        chal.compiler_type = COMPILER_INFOS[chal.compiler_type].version_name

        rechal = self.acct.is_kernel()
        if self.contest:
            rechal = rechal and self.contest.is_admin(self.acct)

        testdata_to_subtasks = defaultdict(list)
        for subtask_config in pro.config.subtask_configs.values():
            for testdata in subtask_config.testdatas:
                testdata_to_subtasks[testdata.testdata_id].append(subtask_config.subtask_id)

        show_history = rechal and self.get_argument("history", default=None) is not None
        history = None
        if show_history:
            _, history = await ChalService.inst.get_challenge_history(chal_id)

        await self.render("chal", pro=pro, chal=chal, rechal=rechal, testdata_to_subtasks=testdata_to_subtasks, history=history, show_history=show_history)
        return

    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    @contest_require_permission("admin")
    async def post(self, chal_id: int = None):
        try:
            chal_id = int(chal_id)
        except (ValueError, TypeError):
            return self.error(("Eparam", "Invalid challenge id"))

        self.path_args = [chal_id]  # Store for action methods
        reqtype = self.get_argument("reqtype")
        return await chal_dispatcher.dispatch(self, reqtype)

    def _download(self, filename: str, filesize: int, content_type: str, reader: IO) -> bool:
        self.set_header("Content-Type", content_type)
        self.set_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.set_header("Content-Length", filesize)
        try:
            while True:
                buffer = reader.read(65536)
                if buffer:
                    self.write(buffer)
                else:
                    return False
        except Exception as e:
            log = structlog.get_logger()
            log.warning("Download interrupted", filename=filename, error=str(e))
            return True

    async def _download_check(self, chal_id: int) -> tuple[str, str] | None:
        if not self.contest and not self.acct.is_kernel():
            await LogService.inst.add_log(f"{self.acct.name}(#{self.acct.acct_id}) attempted to access output zip from chal#{chal_id} without permission.",
                                          "manage.chal.download_output_denied", {"chal_id": chal_id})
            return ("Eacces", "Permission denied")

        output_zip_path = f'code/{chal_id}/output.zip'
        if not os.path.exists(output_zip_path):
            return ("Enoext", "Output file not found")

        return None

    @chal_dispatcher.action("download_output")
    async def download_output(self):
        chal_id = self.path_args[0]

        if err := (await self._download_check(chal_id)):
            return self.error(err)
        output_zip_path = f'code/{chal_id}/output.zip'

        await LogService.inst.add_log(
            f"{self.acct.name}(#{self.acct.acct_id}) download output zip from chal#{chal_id}.",
            "manage.chal.download_output",
        )

        try:
            with open(output_zip_path, 'rb') as f:
                err = self._download('output.zip', os.path.getsize(output_zip_path), "application/zip", f)
                if not err:
                    self.finish()
        except Exception as e:
            log = structlog.get_logger()
            log.error("Failed to open output zip", chal_id=chal_id, error=str(e))
            return self.error(("Eio", "Failed to open output file"))

    @chal_dispatcher.action("download_single_output")
    async def download_single_output(self):
        chal_id = self.path_args[0]
        testdata_id = int(self.get_argument("testdata_id"))
        testdata_id += 1

        if err := (await self._download_check(chal_id)):
            return self.error(err)
        output_zip_path = f'code/{chal_id}/output.zip'

        await LogService.inst.add_log(
            f"{self.acct.name}(#{self.acct.acct_id}) download a single output #{testdata_id-1} from chal#{chal_id}.",
            "manage.chal.download_single_output",
            {"testdata_id": testdata_id-1},
        )

        try:
            with zipfile.ZipFile(output_zip_path, 'r') as zipf:
                try:
                    with zipf.open(f'{testdata_id}.ans', 'r') as ansf:
                        err = self._download(
                            f'{testdata_id}.ans',
                            zipf.getinfo(f'{testdata_id}.ans').file_size,
                            "text/plain",
                            ansf,
                        )
                        if not err:
                            self.finish()
                except KeyError:
                    return self.error(("Enoext", "Specific output file not found"))
        except Exception as e:
            log = structlog.get_logger()
            log.error("Failed to open output zip", chal_id=chal_id, error=str(e))
            return self.error(("Eio", "Failed to open output file"))

    @chal_dispatcher.action("preview_single_output")
    async def preview_single_output(self):
        chal_id = self.path_args[0]
        testdata_id = int(self.get_argument("testdata_id"))
        testdata_id += 1

        if err := (await self._download_check(chal_id)):
            return self.error(err)
        output_zip_path = f'code/{chal_id}/output.zip'

        await LogService.inst.add_log(
            f"{self.acct.name}(#{self.acct.acct_id}) preview a single output #{testdata_id-1} from chal#{chal_id}.",
            "manage.chal.preview_single_output",
            {"testdata_id": testdata_id-1},
        )

        try:
            with zipfile.ZipFile(output_zip_path, 'r') as zipf:
                try:
                    with zipf.open(f'{testdata_id}.ans', 'r') as ansf:
                        size = zipf.getinfo(f'{testdata_id}.ans').file_size
                        if size > 1024 * 1024:
                            return self.error(("Eparam", "Output file too large to preview"))

                        return self.error(("S", tornado.escape.xhtml_escape(ansf.read().decode('utf-8', errors='replace'))))
                except KeyError:
                    return self.error(("Enoext", "Specific output file not found"))
        except Exception as e:
            log = structlog.get_logger()
            log.error("Failed to open output zip", chal_id=chal_id, error=str(e))
            return self.error(("Eio", "Failed to open output file"))

    @chal_dispatcher.action("reject")
    async def reject_challenge(self):
        chal_id = (
            self.path_args[0]
            if hasattr(self, "path_args")
            else int(self.get_argument("chal_id"))
        )
        reason = self.get_argument("reason")
        if err := self.len_check(reason, 0, 1024, "reason"):
            return self.error(err)

        if not self.contest and not self.acct.is_kernel():
            return self.error((("Eacces", "Permission denied")))

        err, chal = await ChalService.inst.get_chal(chal_id, with_result=True)
        if err:
            return self.error(err)

        chal.total_result.reset()
        chal.total_result.message = reason
        chal.total_result.message_type = MessageType.TEXT
        chal.total_result.state = ChalConst.STATE_REJECTED
        await ChalService.inst.update_total_result(chal_id, chal.total_result)

        for r in chal.subtask_results.values():
            r.reset()
            r.state = ChalConst.STATE_REJECTED
            await ChalService.inst.update_subtask_result(chal_id, r)

        for r in chal.testdata_results.values():
            r.reset()
            r.state = ChalConst.STATE_REJECTED
            await ChalService.inst.update_testdata_result(chal_id, r)

        await self.add_log(
            f"{self.acct.name}(#{self.acct.acct_id}) reject chal#{chal_id}.",
            "manage.chal.reject",
            {"reason": reason},
        )

        self.error(("S", ""))
