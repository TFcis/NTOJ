import asyncio
import unittest


def test_main(testing_loop):
    from tests.integrated.main import IntegratedTest
    asyncio.set_event_loop(testing_loop)
    integrated_suite = unittest.TestSuite()
    integrated_suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(IntegratedTest))
    unittest.TextTestRunner().run(integrated_suite)
