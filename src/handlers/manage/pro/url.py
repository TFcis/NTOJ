"""URL routing configuration for problem management handlers"""

from handlers.manage.pro.prolist import ManageProListHandler
from handlers.manage.pro.add import ManageProAddHandler
from handlers.manage.pro.updategeneral import ManageProUpdateGeneralHandler
from handlers.manage.pro.judge_dispatcher import ManageProJudgeHandler
from handlers.manage.pro.limit import ManageProLimitHandler
from handlers.manage.pro.subtask import ManageProSubtaskHandler
from handlers.manage.pro.testdata_dispatcher import ManageProTestdataHandler
from handlers.manage.pro.filemanager import ManageProFilemanagerHandler


def get_manage_pro_url():
    """Return URL patterns for problem management"""
    return [
        # Problem list (list, rechallenge)
        ('/be/manage/pro', ManageProListHandler),
        ('/be/manage/pro/add', ManageProAddHandler),
        ('/be/manage/pro/update', ManageProUpdateGeneralHandler),
        # Judge configuration (dispatches to problem type-specific handlers)
        ('/be/manage/pro/updatejudge', ManageProJudgeHandler),
        ('/be/manage/pro/updatelimit', ManageProLimitHandler),
        ('/be/manage/pro/updatesubtask', ManageProSubtaskHandler),
        # Testdata management (dispatches to problem type-specific handlers)
        ('/be/manage/pro/updatetestdata', ManageProTestdataHandler),
        ('/be/manage/pro/filemanager', ManageProFilemanagerHandler),
    ]
