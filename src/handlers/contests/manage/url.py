from handlers.contests.manage.acct import ContestManageAcctHandler
from handlers.contests.manage.general import (
    ContestManageGeneralHandler,
    ContestManageAddHandler,
    ContestManageDashHandler,
    ContestManageDescEditHandler,
)
from handlers.contests.manage.pro import ContestManageProHandler
from handlers.contests.manage.reg import ContestManageRegHandler

def get_contests_manage_url(db, rs, pool):
    args = {
        'db': db,
        'rs': rs,
    }

    return [
        (r'/be/contests/manage/add', ContestManageAddHandler, args),
        (r'/be/contests/\d+/manage', ContestManageDashHandler, args),
        (r'/be/contests/\d+/manage/dash', ContestManageDashHandler, args),
        (r'/be/contests/\d+/manage/general', ContestManageGeneralHandler, args),
        (r'/be/contests/\d+/manage/desc', ContestManageDescEditHandler, args),
        (r'/be/contests/\d+/manage/acct', ContestManageAcctHandler, args),
        (r'/be/contests/\d+/manage/pro', ContestManageProHandler, args),
        (r'/be/contests/\d+/manage/reg', ContestManageRegHandler, args),
    ]
