import datetime
import os
import platform
import subprocess
import sys
import time

import psutil

import config
from handlers.base import ActionDispatcher, RequestHandler, UnifiedWebSocketHandler, reqenv, require_permission
from services.user import UserConst, UserService

info_dispatcher = ActionDispatcher()
server_start_time = time.time()


class ManageInfoHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        info = await self._get_system_info()
        await self.render("manage/info", page="info", info=info)

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await info_dispatcher.dispatch(self, reqtype)

    async def _get_system_info(self):
        info = {}

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

        try:
            code_size = (
                subprocess.check_output(
                    ["du", "-sh", "code"], stderr=subprocess.DEVNULL
                )
                .decode()
                .split()[0]
            )
            info["path"]["code_size"] = code_size
        except Exception:
            info["path"]["code_size"] = "N/A"

        try:
            problem_size = (
                subprocess.check_output(
                    ["du", "-sh", "problem"], stderr=subprocess.DEVNULL
                )
                .decode()
                .split()[0]
            )
            info["path"]["problem_size"] = problem_size
        except Exception:
            info["path"]["problem_size"] = "N/A"

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
            import tomli

            with open("/ntoj/pyproject.toml", "rb") as f:
                pyproject = tomli.load(f)
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
            uptime_seconds = (
                subprocess.check_output(
                    ["cat", "/proc/uptime"], stderr=subprocess.DEVNULL
                )
                .decode()
                .split()[0]
            )
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
            df_output = subprocess.check_output(
                ["df", "-h"], stderr=subprocess.DEVNULL
            ).decode()
            info["disk"] = df_output
        except Exception:
            info["disk"] = "N/A"

        try:
            info["resources"] = {
                "cpu_percent": psutil.cpu_percent(interval=1),
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

            return self.error(("S", ""))
        except Exception as e:
            return self.error(("E", f"VACUUM Failed: {str(e)}"))
