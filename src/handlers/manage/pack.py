import json

from handlers.base import require_permission, reqenv, RequestHandler
from services.pack import PackService
from services.user import UserConst


class ManagePackHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument('reqtype')

        if reqtype == 'gettoken':
            _, pack_token = await PackService.inst.gen_token()
            self.finish(json.dumps(pack_token))
