from services.contests import UserStatus


def contest_require_permission(acct_type: str):
    def decorator(func):
        async def wrap(self, *args, **kwargs):
            if self.contest is not None:
                if acct_type == 'admin':
                    if not self.contest.is_admin(acct=self.acct):
                        self.finish('Eacces')
                        return

                elif acct_type == 'normal':
                    if not self.contest.member_is_status(self.acct, UserStatus.APPROVED):
                        self.finish('Eacces')
                        return

                elif acct_type == 'all':
                    if not self.contest.is_member(acct=self.acct):
                        self.finish('Eacces')
                        return

            ret = await func(self, *args, **kwargs)
            return ret

        return wrap

    return decorator
