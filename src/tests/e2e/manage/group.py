from tests.e2e.util import AsyncTest, AccountContext

class ManageGroupTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            pass
