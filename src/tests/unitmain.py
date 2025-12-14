import unittest


def main():
    loader = unittest.TestLoader()
    unit_suite = loader.discover("tests/unit/services", pattern="test_*.py")
    return unittest.TextTestRunner().run(unit_suite)

