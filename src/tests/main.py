import asyncio
import unittest


def test_main(testing_loop):
    from tests.e2e.main import E2ETest
    asyncio.set_event_loop(testing_loop)
    e2e_suite = unittest.TestSuite()
    e2e_suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(E2ETest))
    unittest.TextTestRunner().run(e2e_suite)
