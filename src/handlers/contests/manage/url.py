from handlers.contests.manage.acct import ContestManageAcctHandler
from handlers.contests.manage.general import (
    ContestManageGeneralHandler,
    ContestManageAddHandler,
    ContestManageDashHandler,
)
from handlers.contests.manage.pro import ContestManageProHandler


def get_contests_manage_url(db, rs, pool):
    args = {
        'db': db,
        'rs': rs,
    }

    return [
        (r'/contests/manage/add', ContestManageAddHandler, args),
        (r'/contests/\d+/manage', ContestManageDashHandler, args),
        (r'/contests/\d+/manage/dash', ContestManageDashHandler, args),
        (r'/contests/\d+/manage/general', ContestManageGeneralHandler, args),
        (r'/contests/\d+/manage/acct', ContestManageAcctHandler, args),
        (r'/contests/\d+/manage/pro', ContestManageProHandler, args),
    ]
