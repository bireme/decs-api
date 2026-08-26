# -*- coding: utf-8 -*-
"""Block until the API answers, for `make dev_test_live`.

The live layer drives the API over HTTP, so the server started alongside it has
to be up before the tests run. Exits non-zero if it never comes up.
"""

import os
import sys
import time
import urllib.request

URL = os.environ.get('DECS_TEST_URL', 'http://localhost:8000') + '/api/thesaurus/'
ATTEMPTS = int(os.environ.get('DECS_TEST_WAIT', 60))


def main():
    for _ in range(ATTEMPTS):
        try:
            urllib.request.urlopen(URL, timeout=2).read()
            return 0
        except Exception:
            time.sleep(1)

    sys.stderr.write("the API did not answer at %s after %d attempts\n" % (URL, ATTEMPTS))
    return 1


if __name__ == '__main__':
    sys.exit(main())
