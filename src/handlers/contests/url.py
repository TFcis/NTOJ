from handlers.chal import ChalListHandler, ChalHandler
from handlers.contests.contests import ContestInfoHandler, ContestListHandler
from handlers.contests.manage.url import get_contests_manage_url
from handlers.contests.proset import ContestProsetHandler
from handlers.contests.reg import ContestRegHandler
from handlers.contests.scoreboard import ContestScoreboardHandler, ContestScoreboardNewChalHandler
from handlers.pro import ProHandler, ProStaticHandler
from handlers.submit import SubmitHandler


def get_contests_url(db, rs, pool):
    args = {
        'db': db,
        'rs': rs,
    }

    sub_args = {'pool': pool}

    return [
        (r'/contests', ContestListHandler, args),
        (r'/contests/\d+', ContestInfoHandler, args),
        (r'/contests/\d+/info', ContestInfoHandler, args),
        (r'/contests/\d+/pro/(\d+)/(.*)', ProStaticHandler, args),
        (r'/contests/\d+/pro/(\d+)', ProHandler, args),
        (r'/contests/\d+/proset', ContestProsetHandler, args),
        (r'/contests/\d+/chal', ChalListHandler, args),
        (r'/contests/\d+/chal/(\d+)', ChalHandler, args),
        (r'/contests/\d+/submit/(\d+)', SubmitHandler, args),
        (r'/contests/\d+/submit', SubmitHandler, args),
        (r'/contests/\d+/reg', ContestRegHandler, args),
        (r'/contests/\d+/scoreboard', ContestScoreboardHandler, args),
        (r'/contests/\d+/scoreboardsub', ContestScoreboardNewChalHandler, sub_args),
        # (r'/contests/\d+/question', args), # TODO: question
        # ('/contests/pro/(.+)', args),  # Experiment Problem UI
    ] + get_contests_manage_url(db, rs, pool)
