from msgpack import packb, unpackb

from services.user import UserConst, UserService


class QuestionService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        QuestionService.inst = self

    # TODO: Migrate Question data from redis to database

    async def get_queslist(self, acct_id):
        if (await self.rs.get(f'{acct_id}_msg_active')) is None:
            await self.rs.set(f'{acct_id}_msg_active', packb(True))
            await self.rs.set(f'{acct_id}_msg_ask', packb(False))
            await self.rs.set(f'{acct_id}_msg_list', packb([]))
            return None, []

        else:
            return None, unpackb((await self.rs.get(f'{acct_id}_msg_list')))

    async def set_ques(self, acct_id: int, ques_text: str):
        if (active := (await self.rs.get(f'{acct_id}_msg_active'))) is None:
            await self.rs.set(f'{acct_id}_msg_active', packb(True))
            await self.rs.set(f'{acct_id}_msg_ask', packb(False))
            await self.rs.set(f'{acct_id}_msg_list', packb([]))

        elif not active:
            return 'Eacces'

        await self.rs.set(f'{acct_id}_msg_ask', packb(True))
        ques_list = unpackb((await self.rs.get(f'{acct_id}_msg_list')))
        ques_list.append(
            {
                'Q': ques_text,
                'A': None,
            }
        )

        while len(ques_list) > 10:
            ques_list.pop(0)

        # await self.rs.set('someoneask', packb(True))
        await self.rs.set(f'{acct_id}_msg_list', packb(ques_list))
        return None

    async def reply(self, qacct_id, index, rtext):
        _, ques_list = await self.get_queslist(acct_id=qacct_id)

        ques_list[int(index)]['A'] = rtext
        # await self.rs.set('someoneask', packb(False))
        await self.rs.set(f'{qacct_id}_msg_list', packb(ques_list))
        await self.rs.set(f'{qacct_id}_msg_ask', packb(False))
        await self.rs.set(f'{qacct_id}_have_reply', packb(True))

    async def rm_ques(self, acct_id: int, index: int):
        _, ques_list = await self.get_queslist(acct_id)

        ques_list.pop(int(index))
        if len(ques_list) == 0:
            await self.rs.set(f"{acct_id}_msg_ask", packb(False))

        await self.rs.set(f"{acct_id}_msg_list", packb(ques_list))
        return None

    async def have_reply(self, acct_id):
        if (reply := (await self.rs.get(f'{acct_id}_have_reply'))) is None:
            await self.rs.set(f'{acct_id}_have_reply', packb(False))
            return False

        return unpackb(reply)

    async def get_asklist(self):
        _, acctlist = await UserService.inst.list_acct(UserConst.ACCTTYPE_USER, True)

        asklist = {}
        ask_cnt = 0
        for acct in acctlist:
            if (ask := (await self.rs.get(f"{acct.acct_id}_msg_ask"))) is None:
                asklist.update({acct.acct_id: False})
            else:
                ask = unpackb(ask)
                asklist.update({acct.acct_id: ask})
                if ask:
                    ask_cnt += 1

        return None, asklist, ask_cnt
