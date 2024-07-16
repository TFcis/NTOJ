from handlers.chal import ChalListHandler, ChalHandler
from handlers.contests.contests import ContestInfoHandler, ContestListHandler
from handlers.contests.manage.url import get_contests_manage_url
from handlers.contests.proset import ContestProsetHandler
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
    ] + get_contests_manage_url(db, rs, pool)
