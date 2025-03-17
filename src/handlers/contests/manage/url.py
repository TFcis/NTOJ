from handlers.contests.manage.acct import ContestManageAcctHandler
from handlers.contests.manage.general import (
    ContestManageGeneralHandler,
    ContestManageAddHandler,
    ContestManageDashHandler,
    ContestManageDescEditHandler,
)
from handlers.contests.manage.pro import ContestManageProHandler
from handlers.contests.manage.reg import ContestManageRegHandler
from handlers.contests.manage.qa import ContestManageQuestionHandler, ContestManageAnnounceHandler, ContestManageQANewQuesHandler

def get_contests_manage_url(db, rs, pool):
    args = {
        'db': db,
        'rs': rs,
    }

    sub_args = {'pool': pool}

    return [
        (r'/contests/manage/add', ContestManageAddHandler, args),
        (r'/contests/\d+/manage', ContestManageDashHandler, args),
        (r'/contests/\d+/manage/dash', ContestManageDashHandler, args),
        (r'/contests/\d+/manage/general', ContestManageGeneralHandler, args),
        (r'/contests/\d+/manage/desc', ContestManageDescEditHandler, args),
        (r'/contests/\d+/manage/acct', ContestManageAcctHandler, args),
        (r'/contests/\d+/manage/pro', ContestManageProHandler, args),
        (r'/contests/\d+/manage/reg', ContestManageRegHandler, args),
        (r'/contests/\d+/manage/question', ContestManageQuestionHandler, args),
        (r'/contests/\d+/manage/announce', ContestManageAnnounceHandler, args),
        (r'/contests/\d+/manage/qasub', ContestManageQANewQuesHandler, sub_args),
    ]
