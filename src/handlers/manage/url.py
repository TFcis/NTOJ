from handlers.manage.acct import ManageAcctHandler
from handlers.manage.board import ManageBoardHandler
from handlers.manage.contest import ManageContestHandler
from handlers.manage.dash import ManageDashHandler
from handlers.manage.info import ManageInfoHandler
from handlers.manage.judge import ManageJudgeHandler
from handlers.manage.pack import ManagePackHandler
from handlers.manage.pro.url import get_manage_pro_url
from handlers.manage.proclass import ManageProClassHandler
from handlers.manage.question import ManageQuestionHandler


def get_manage_url(db, rs, pool):
    args = {
        'db': db,
        'rs': rs,
    }

    # Get pro management URLs with args applied
    pro_urls = [(pattern, handler, args) for pattern, handler in get_manage_pro_url()]

    return [
        ('/be/manage/dash', ManageDashHandler, args),
        ('/be/manage/info', ManageInfoHandler, args),
        ('/be/manage/acct', ManageAcctHandler, args),
        ('/be/manage/acct/(.+)', ManageAcctHandler, args),
        ('/be/manage/board', ManageBoardHandler, args),
        ('/be/manage/board/(.+)', ManageBoardHandler, args),
        ('/be/manage/contest', ManageContestHandler, args),
        ('/be/manage/proclass', ManageProClassHandler, args),
        ('/be/manage/proclass/(.+)', ManageProClassHandler, args),
        ('/be/manage/question', ManageQuestionHandler, args),
        ('/be/manage/question/(.+)', ManageQuestionHandler, args),
        ('/be/manage/judge', ManageJudgeHandler, args),
        ('/be/manage/pack', ManagePackHandler, args),
    ] + pro_urls
