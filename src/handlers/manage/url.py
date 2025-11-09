from handlers.manage.acct import ManageAcctHandler
from handlers.manage.board import ManageBoardHandler
from handlers.manage.bulletin import ManageBulletinHandler
from handlers.manage.contest import ManageContestHandler
from handlers.manage.dash import ManageDashHandler
from handlers.manage.judge import JudgeChalCntSub, ManageJudgeHandler
from handlers.manage.pack import ManagePackHandler
from handlers.manage.pro import ManageProHandler
from handlers.manage.proclass import ManageProClassHandler
from handlers.manage.question import ManageQuestionHandler


def get_manage_url(db, rs, pool):
    args = {
        'db': db,
        'rs': rs,
    }

    sub_args = {'pool': pool}

    return [
        ('/be/manage/dash', ManageDashHandler, args),
        ('/be/manage/acct', ManageAcctHandler, args),
        ('/be/manage/acct/(.+)', ManageAcctHandler, args),
        ('/be/manage/pro', ManageProHandler, args),
        ('/be/manage/pro/(.+)', ManageProHandler, args),
        ('/be/manage/board', ManageBoardHandler, args),
        ('/be/manage/board/(.+)', ManageBoardHandler, args),
        ('/be/manage/contest', ManageContestHandler, args),
        ('/be/manage/bulletin', ManageBulletinHandler, args),
        ('/be/manage/bulletin/(.+)', ManageBulletinHandler, args),
        ('/be/manage/proclass', ManageProClassHandler, args),
        ('/be/manage/proclass/(.+)', ManageProClassHandler, args),
        ('/be/manage/question', ManageQuestionHandler, args),
        ('/be/manage/question/(.+)', ManageQuestionHandler, args),
        ('/be/manage/judge', ManageJudgeHandler, args),
        ('/be/manage/judgecntws', JudgeChalCntSub, sub_args),
        ('/be/manage/pack', ManagePackHandler, args),
    ]
