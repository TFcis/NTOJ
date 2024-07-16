from handlers.contests.manage.url import get_contests_manage_url


def get_contests_url(db, rs, pool):
    args = {
        'db': db,
        'rs': rs,
    }

    sub_args = {'pool': pool}

    return [
    ] + get_contests_manage_url(db, rs, pool)
