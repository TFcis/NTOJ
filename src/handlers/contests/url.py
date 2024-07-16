from handlers.contests.contests import ContestInfoHandler, ContestListHandler
from handlers.contests.manage.url import get_contests_manage_url


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
    ] + get_contests_manage_url(db, rs, pool)
