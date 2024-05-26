from handlers.manage.acct import ManageAcctHandler
from handlers.manage.board import ManageBoardHandler
from handlers.manage.bulletin import ManageBulletinHandler
from handlers.manage.contest import ManageContestHandler
from handlers.manage.dash import ManageDashHandler
from handlers.manage.group import ManageGroupHandler
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

    sub_args = {
        'pool': pool
    }

    return [
        ('/manage/dash', ManageDashHandler, args),
        ('/manage/acct', ManageAcctHandler, args),
        ('/manage/acct/(.+)', ManageAcctHandler, args),
        ('/manage/pro', ManageProHandler, args),
        ('/manage/pro/(.+)', ManageProHandler, args),
        ('/manage/board', ManageBoardHandler, args),
        ('/manage/board/(.+)', ManageBoardHandler, args),
        ('/manage/contest', ManageContestHandler, args),
        ('/manage/bulletin', ManageBulletinHandler, args),
        ('/manage/bulletin/(.+)', ManageBulletinHandler, args),
        ('/manage/proclass', ManageProClassHandler, args),
        ('/manage/proclass/(.+)', ManageProClassHandler, args),
        ('/manage/question', ManageQuestionHandler, args),
        ('/manage/question/(.+)', ManageQuestionHandler, args),
        ('/manage/group', ManageGroupHandler, args),
        ('/manage/judge', ManageJudgeHandler, args),
        ('/manage/judgecntws', JudgeChalCntSub, sub_args),
        ('/manage/pack', ManagePackHandler, args),
    ]
