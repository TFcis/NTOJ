from handlers.chal import ChalListHandler, ChalHandler
from handlers.contests.contests import ContestInfoHandler, ContestListHandler
from handlers.contests.manage.url import get_contests_manage_url
from handlers.contests.proset import ContestProsetHandler
from handlers.contests.reg import ContestRegHandler
from handlers.contests.scoreboard import ContestScoreboardHandler, ContestScoreboardNewChalHandler
from handlers.contests.qa import ContestQAHandler, ContestNewQAHandler
from handlers.pro import ProHandler, ProStaticHandler
from handlers.submit import SubmitHandler


def get_contests_url(db, rs, pool):
    args = {
        'db': db,
        'rs': rs,
    }

    sub_args = {'pool': pool}

    return [
        (r'/be/contests', ContestListHandler, args),
        (r'/be/contests/\d+', ContestInfoHandler, args),
        (r'/be/contests/\d+/info', ContestInfoHandler, args),
        (r'/be/contests/\d+/pro/(\d+)/(.*)', ProStaticHandler, {'db': db, 'rs': rs, 'path': 'problem'}),
        (r'/be/contests/\d+/pro/(\d+)', ProHandler, args),
        (r'/be/contests/\d+/proset', ContestProsetHandler, args),
        (r'/be/contests/\d+/chal', ChalListHandler, args),
        (r'/be/contests/\d+/chal/(\d+)', ChalHandler, args),
        (r'/be/contests/\d+/submit/(\d+)', SubmitHandler, args),
        (r'/be/contests/\d+/submit', SubmitHandler, args),
        (r'/be/contests/\d+/reg', ContestRegHandler, args),
        (r'/be/contests/\d+/scoreboard', ContestScoreboardHandler, args),
        (r'/be/contests/\d+/scoreboardsub', ContestScoreboardNewChalHandler, sub_args),
        (r'/be/contests/\d+/qa', ContestQAHandler, args),
        (r'/be/contests/\d+/qasub', ContestNewQAHandler, sub_args),
        # ('/contests/pro/(.+)', args),  # Experiment Problem UI
    ] + get_contests_manage_url(db, rs, pool)
