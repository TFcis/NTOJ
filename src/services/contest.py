import datetime

from msgpack import packb, unpackb

from services.group import GroupService


class ContestConst:
    STATUS_ONLINE = 0
    STATUS_HIDDEN = 1
    STATUS_OFFLINE = 2


class ContestService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        ContestService.inst = self

    async def get_list(self):
        if (contest_list := (await self.rs.get('contest_list'))) is not None:
            return unpackb(contest_list)

    async def get(self, cont_name):
        if cont_name == 'default':
            data = await self.rs.get('contest')
            if data is None:
                return (None, {
                    'class': 0,
                    'status': ContestConst.STATUS_OFFLINE,

                    'start': datetime.datetime.now().replace(
                        tzinfo=datetime.timezone(
                            datetime.timedelta(hours=8))),

                    'end': datetime.datetime.now().replace(
                        tzinfo=datetime.timezone(
                            datetime.timedelta(hours=8))),
                })

            meta = unpackb(data)
            start = datetime.datetime.fromtimestamp(meta['start'])
            meta['start'] = start.replace(tzinfo=datetime.timezone(
                datetime.timedelta(hours=8)))

            end = datetime.datetime.fromtimestamp(meta['end'])
            meta['end'] = end.replace(tzinfo=datetime.timezone(
                datetime.timedelta(hours=8)))

            return None, meta

        else:
            cont_list = unpackb((await self.rs.get('contest_list')))
            if cont_name in cont_list:
                meta = unpackb((await self.rs.get(f"{cont_name}_contest")))
                start = datetime.datetime.fromtimestamp(meta['start'])
                meta['start'] = start.replace(tzinfo=datetime.timezone(
                    datetime.timedelta(hours=8)))
                end = datetime.datetime.fromtimestamp(meta['end'])
                meta['end'] = end.replace(tzinfo=datetime.timezone(
                    datetime.timedelta(hours=8)))
                return None, meta

            else:
                return 'Eexist', None

    async def remove_cont(self, cont_name):
        cont_list = await self.get_list()
        if cont_name not in cont_list:
            return 'Eexist', None

        cont_list.remove(cont_name)
        await self.rs.set('contest_list', packb(cont_list))
        await self.rs.delete(f"{cont_name}_contest")

    async def set(self, cont_name, clas, status, start, end, pro_list=None, acct_list=None):
        def _mp_encoder(obj):
            if isinstance(obj, datetime.datetime):
                return obj.astimezone(datetime.timezone.utc).timestamp()

            return obj

        if cont_name == 'default':
            await self.rs.set('contest', packb({
                'class': clas,
                'status': status,
                'start': start,
                'end': end
            }, default=_mp_encoder))

            return None, None

        else:
            pro = str(pro_list).replace(' ', '').split(',')
            pro_list = []
            for p in pro:
                if p != '':
                    pro_list.append(int(p))

            acct = str(acct_list).replace(' ', '').split(',')
            acct_list = []

            for a in acct:
                if a != '':
                    if a.isnumeric():
                        acct_list.append(int(a))
                    elif a.find('_group') != -1:
                        gacct = await GroupService.inst.list_acct_in_group(a[:-6])
                        for ga in gacct:
                            acct_list.append(int(ga['acct_id']))

            acct_list = list(set(acct_list))
            cont_list = await self.get_list()
            if not cont_name in cont_list:
                cont_list.append(cont_name)
                await self.rs.set('contest_list', packb(cont_list))

            await self.rs.set(f"{cont_name}_contest", packb({
                'status': status,
                'start': start,
                'end': end,
                'pro_list': pro_list,
                'acct_list': acct_list
            }, default=_mp_encoder))

            return None, None

    async def running(self):
        err, meta = await self.get('default')

        if meta['status'] == ContestConst.STATUS_OFFLINE:
            return None, False

        now = datetime.datetime.now().replace(
            tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
        if meta['start'] > now or meta['end'] <= now:
            return None, False

        return None, True
