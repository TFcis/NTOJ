import datetime
import os
import platform
import sys
import time
import logging

import psutil

import config
from handlers.base import ActionDispatcher, RequestHandler, UnifiedWebSocketHandler, reqenv, require_permission
from services.user import UserConst, UserService
from services.log import LogService

info_dispatcher = ActionDispatcher()
server_start_time = time.time()

logger = logging.getLogger("tornado.application")

class ManageInfoHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        info = await self._get_system_info()
        await self.render("manage/info", "System Information", page="info", info=info)

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await info_dispatcher.dispatch(self, reqtype)

    async def _get_system_info(self):
        info = {}

        async with UnifiedWebSocketHandler._connections_lock:
            info['active_websocket_connections'] = len(UnifiedWebSocketHandler.active_connections)

        try:
            with open("./version.txt", "r") as f:
                git_hash = f.readline().strip()
                git_branch = f.readline().strip()
            info["git"] = {
                "hash": git_hash[:8],
                "full_hash": git_hash,
                "branch": git_branch,
            }
        except Exception:
            info["git"] = {"error": "Git Info Not Available"}

        try:
            async with self.db.acquire() as con:
                version = await con.fetchval("SELECT version()")
                info["db"] = {"version": version}

                db_size = await con.fetchval(
                    "SELECT pg_size_pretty(pg_database_size($1))", config.DBNAME_OJ
                )
                info["db"]["size"] = db_size

                conn_count = await con.fetchval(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = $1",
                    config.DBNAME_OJ,
                )
                info["db"]["connections"] = conn_count
        except Exception as e:
            info["db"] = {"error": str(e)}

        info["path"] = {
            "installation": os.getcwd(),
            "code": os.path.abspath("code"),
            "problem": os.path.abspath("problem"),
        }

        info["config"] = {
            "timezone": str(getattr(config, "TIMEZONE", "N/A")),
            "base_url": getattr(config, "BASE_URL", "/"),
            "port": getattr(config, "PORT", "N/A"),
            "site_title": getattr(config, "SITE_TITLE", "N/A"),
        }

        can_see_code_user = []
        for acct_id in getattr(config, "can_see_code_user", []):
            err, acct = await UserService.inst.info_acct(acct_id)
            if err:
                continue
            can_see_code_user.append(acct)
        info["config"]["can_see_code_user"] = can_see_code_user

        try:
            redis_info = await self.rs.info()
            info["redis"] = {
                "version": redis_info.get("redis_version", "N/A"),
                "connected_clients": redis_info.get("connected_clients", 0),
            }
        except Exception as e:
            info["redis"] = {"error": str(e)}

        info["python"] = {"version": sys.version, "executable": sys.executable}

        try:
            import tomllib

            with open("./pyproject.toml", "rb") as f:
                pyproject = tomllib.load(f)
                deps = (
                    pyproject.get("tool", {}).get("poetry", {}).get("dependencies", {})
                )
                info["python"]["dependencies"] = {
                    k: str(v) for k, v in deps.items() if k != "python"
                }
        except Exception:
            info["python"]["dependencies"] = "N/A"

        info["os"] = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        }

        try:
            uptime_seconds = int(time.time() - psutil.boot_time())
            uptime = str(datetime.timedelta(seconds=int(float(uptime_seconds))))
            info["os"]["uptime"] = uptime
        except Exception:
            info["os"]["uptime"] = "N/A"

        # System running time (server process uptime)
        running_seconds = int(time.time() - server_start_time)
        info["os"]["running_time"] = str(datetime.timedelta(seconds=running_seconds))

        if os.path.exists("./docker-dev"):
            info["env"] = "docker-dev"
        elif os.path.exists("./docker-release"):
            info["env"] = "docker-release"
        elif os.path.exists("./installation-script"):
            info["env"] = "installation-script"
        else:
            info["env"] = "unknown"

        try:
            disk = psutil.disk_usage("/")
            info["disk"] = {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent,
            }
        except Exception:
            info["disk"] = "N/A"

        try:
            info["resources"] = {
                "cpu_percent": psutil.cpu_percent(interval=None),
                "cpu_count": psutil.cpu_count(),
                "memory": {
                    "total": psutil.virtual_memory().total,
                    "available": psutil.virtual_memory().available,
                    "percent": psutil.virtual_memory().percent,
                    "used": psutil.virtual_memory().used,
                },
            }
        except Exception as e:
            info["resources"] = {"error": str(e)}

        return info

    @info_dispatcher.action("vacuum")
    async def vacuum_database(self):
        try:
            async with self.db.acquire() as con:
                await con.execute("VACUUM ANALYZE")

            await self.add_log(
                f"{self.acct.name} performed a VACUUM ANALYZE on the database.",
                "manage.info.vacuum",
            )
            return self.error(("S", ""))
        except Exception as e:
            logger.error(f"Failed to perform VACUUM ANALYZE: {e}", exc_info=True)
            return self.error(("E", "VACUUM Failed"))
