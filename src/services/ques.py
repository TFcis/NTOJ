from msgpack import packb, unpackb

from services.user import UserService, UserConst


class QuestionService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        QuestionService.inst = self

    async def get_queslist(self, acct, acctid=None):
        if acct is not None:
            if acct['acct_id'] == UserConst.ACCTID_GUEST:
                return 'Esign', None

            if acct['acct_type'] != UserConst.ACCTTYPE_USER:
                return 'Eacces', None
            acct_id = acct['acct_id']

        else:
            if acctid == UserConst.ACCTID_GUEST:
                return 'Esign', None

            acct_id = acctid

        if (await self.rs.get(f'{acct_id}_msg_active')) is None:
            await self.rs.set(f'{acct_id}_msg_active', packb(True))
            await self.rs.set(f'{acct_id}_msg_ask', packb(False))
            await self.rs.set(f'{acct_id}_msg_list', packb([]))
            return None, []

        else:
            return None, unpackb((await self.rs.get(f'{acct_id}_msg_list')))

    async def set_ques(self, acct, ques_text):
        if acct['acct_id'] == UserConst.ACCTID_GUEST:
            return 'Esign'

        if acct['acct_type'] != UserConst.ACCTTYPE_USER:
            return 'Eacces'

        acct_id = acct['acct_id']
        if (active := (await self.rs.get(f'{acct_id}_msg_active'))) is None:
            await self.rs.set(f'{acct_id}_msg_active', packb(True))
            await self.rs.set(f'{acct_id}_msg_ask', packb(False))
            await self.rs.set(f'{acct_id}_msg_list', packb([]))

        elif not active:
            return 'Eacces'

        await self.rs.set(f'{acct_id}_msg_ask', packb(True))
        ques_list = unpackb((await self.rs.get(f'{acct_id}_msg_list')))
        ques_list.append({
            'Q': ques_text,
            'A': None,
        })

        while len(ques_list) > 10:
            ques_list.pop(0)

        # await self.rs.set('someoneask', packb(True))
        await self.rs.set(f'{acct_id}_msg_list', packb(ques_list))
        return None

    async def reply(self, acct, qacct_id, index, rtext):
        if acct['acct_type'] != UserService.ACCTTYPE_KERNEL:
            return 'Eacces'

        err, ques_list = await self.get_queslist(acct=None, acctid=qacct_id)
        if err:
            return err

        ques_list[int(index)]['A'] = rtext
        # await self.rs.set('someoneask', packb(False))
        await self.rs.set(f'{qacct_id}_msg_list', packb(ques_list))
        await self.rs.set(f'{qacct_id}_have_reply', packb(True))

    async def rm_ques(self, acct, index: int):
        if acct['acct_type'] != UserService.ACCTTYPE_USER:
            return 'Eacces'

        err, ques_list = await self.get_queslist(acct=acct)
        if err:
            return err

        ques_list.pop(int(index))
        await self.rs.set(f"{acct['acct_id']}_msg_list", packb(ques_list))
        return None

    async def have_reply(self, acct_id):
        if (reply := (await self.rs.get(f'{acct_id}_have_reply'))) is None:
            await self.rs.set(f'{acct_id}_have_reply', packb(False))
            return False

        return unpackb(reply)

    async def get_asklist(self):
        err, acctlist = await UserService.inst.list_acct(UserConst.ACCTTYPE_KERNEL, True)

        asklist = {}
        ask_cnt = 0
        for acct in acctlist:
            if (ask := (await self.rs.get(f"{acct['acct_id']}_msg_ask"))) is None:
                asklist.update({acct['acct_id']: False})
            else:
                ask = unpackb(ask)
                asklist.update({acct['acct_id']: ask})
                if ask:
                    ask_cnt += 1

        return None, asklist, ask_cnt
