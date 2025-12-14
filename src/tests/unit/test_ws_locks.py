import asyncio
import random
import unittest

from handlers.base import UnifiedWebSocketHandler


class DummyConn:
    def __init__(self, id_):
        self.id_ = id_
        self.session_id = f"session-{id_}"


class TestWSLocks(unittest.IsolatedAsyncioTestCase):
    async def test_subscriptions_snapshot_no_crash(self):
        # Prepare dummy connections
        conns = [DummyConn(i) for i in range(10)]

        async def modifier_add():
            for i in range(200):
                async with UnifiedWebSocketHandler._subscriptions_lock:
                    UnifiedWebSocketHandler.subscriptions.setdefault(conns[i % 10], set()).add(
                        f"chan-{i%5}"
                    )
                await asyncio.sleep(random.random() * 0.001)

        async def modifier_remove():
            for i in range(200):
                async with UnifiedWebSocketHandler._subscriptions_lock:
                    s = UnifiedWebSocketHandler.subscriptions.get(conns[i % 10])
                    if s:
                        s.discard(f"chan-{i%5}")
                await asyncio.sleep(random.random() * 0.001)

        async def snapshotter():
            # repeat snapshot and iterate - should not crash with concurrent mods
            for _ in range(1000):
                async with UnifiedWebSocketHandler._subscriptions_lock:
                    snapshot = list(UnifiedWebSocketHandler.subscriptions.items())
                # iterate outside lock to simulate real dispatching code
                for conn, types in snapshot:
                    # simply read and touch item
                    if types:
                        max_len = max((len(types), 0))
                await asyncio.sleep(random.random() * 0.001)

        await asyncio.gather(modifier_add(), modifier_remove(), snapshotter())

    async def test_register_channel_callbacks_concurrent(self):
        # Register many callbacks concurrently
        def dummy_cb():
            pass

        async def reg(i):
            UnifiedWebSocketHandler.register_channel_callback(f"chan-{i}", dummy_cb)
            await asyncio.sleep(random.random() * 0.001)

        tasks = [asyncio.create_task(reg(i)) for i in range(50)]
        await asyncio.gather(*tasks)

        # ensure keys present (note: registration may be scheduled async to subscribe)
        async with UnifiedWebSocketHandler._channel_callbacks_lock:
            for i in range(50):
                self.assertIn(f"chan-{i}", UnifiedWebSocketHandler._channel_callbacks)

if __name__ == '__main__':
    unittest.main()
