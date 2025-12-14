import sys
import traceback
from tests.unitmain import main

rc = 0
try:
    result = main()
    if result is None:
        rc = 1
    elif hasattr(result, "wasSuccessful") and not result.wasSuccessful():
        rc = 1
except BaseException as exc:
    print("Exception while running tests:", exc)
    traceback.print_exc()
    rc = 1

sys.exit(rc)