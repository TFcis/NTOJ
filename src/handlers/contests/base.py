import json
from services.contest_access import ContestPermission


def contest_require_permission(permission: ContestPermission):
    def decorator(func):
        async def wrap(self, *args, **kwargs):
            if self.contest is not None and (
                self.contest_access is None
                or not self.contest_access.has(permission)
            ):
                await self.finish(
                    json.dumps({"status": "Eacces", "data": "Permission denied"})
                )
                return

            ret = await func(self, *args, **kwargs)
            return ret

        return wrap

    return decorator
