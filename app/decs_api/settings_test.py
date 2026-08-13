"""Settings for the automated test suite.

Runs the offline layers (pure unit + endpoint tests) with no MySQL, no
Elasticsearch and no network:

    python manage.py test --settings=decs_api.settings_test

The environment defaults below are set *before* importing the real settings,
which read os.environ at module level and would otherwise raise without
conf/app-env present (settings.ALLOWED_HOSTS calls .split(",") on the value).
"""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-used-in-production")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "testserver,localhost")
os.environ.setdefault("DEBUG", "0")

from decs_api.settings import *  # noqa: F401,F403,E402

# SQLite in-memory: fast, disposable, and available wherever Python is.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'TEST': {'NAME': ':memory:'},
    }
}

# Most thesaurus models are managed = False in 0001_initial.py, so migrate
# creates no tables for them. The runner creates the missing ones by hand;
# see decs_api/test_runner.py for why the usual pre_migrate hook cannot work.
TEST_RUNNER = 'decs_api.test_runner.UnmanagedTablesRunner'

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# fixtures live next to the tests that use them, not in the default app/fixtures
FIXTURE_DIRS = [os.path.join(BASE_DIR, 'api', 'tests', 'fixtures')]  # noqa: F405

DEBUG = False

# Never talk to a real cluster from the offline layers. The live layer
# (DECS_TEST_ES=1) reads ELASTICSEARCH_HOST from the environment instead.
ELASTICSEARCH_DSL_AUTOSYNC = False
ELASTICSEARCH_DSL_AUTO_REFRESH = False

# tastypie converts unhandled exceptions into 500 responses and logs the
# traceback through django.request. The characterization tests deliberately
# trigger those, so keep the output out of the test report.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'null': {'class': 'logging.NullHandler'},
    },
    'loggers': {
        'django.request': {'handlers': ['null'], 'level': 'CRITICAL', 'propagate': False},
        'tastypie': {'handlers': ['null'], 'level': 'CRITICAL', 'propagate': False},
    },
}
