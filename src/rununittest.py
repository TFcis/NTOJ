import sys
import traceback
from tests.unitmain import main

rc = 0
try:
    result = main()
    if result is None:
        rc = 1
    elif not result.wasSuccessful():
        rc = 1
except Exception as exc:
    print("Exception while running tests:", exc)
    traceback.print_exception(exc)
    rc = 1

sys.exit(rc)
