"""Test runner that creates tables for the unmanaged thesaurus models.

The DeCS database is owned by another application, so most thesaurus models
declare ``managed = False`` and ``0001_initial.py`` carries that option into the
migration. The API still reads several of those tables (TermListDesc,
TreeNumbersListDesc, TreeNumbersListQualif), so the test database needs them.

Flipping ``managed`` on the model Meta from a ``pre_migrate`` receiver does not
help: CreateModel decides whether to build a table from the *migration state*,
where ``'managed': False`` is recorded, not from the live model class. So create
the missing tables explicitly once the normal database setup is done.
"""

from contextlib import contextmanager

from django.apps import apps
from django.db import connections
from django.test.runner import DiscoverRunner

# Apps whose unmanaged models the API reads.
UNMANAGED_APPS = ('thesaurus', 'utils')


def unmanaged_models():
    """Every unmanaged model in UNMANAGED_APPS, concrete models before their m2m through models.

    create_model() also creates the through table of each m2m field, so the
    concrete models have to come first — otherwise a through table gets created
    on its own and the owning model's create_model() fails on the duplicate.
    """
    concrete, through = [], []

    for app_label in UNMANAGED_APPS:
        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:
            continue

        for model in app_config.get_models(include_auto_created=True):
            if model._meta.managed or model._meta.proxy:
                continue
            (through if model._meta.auto_created else concrete).append(model)

    return concrete + through


@contextmanager
def nullable_columns(model):
    """Build the table with every non-key column nullable.

    The DeCS database predates these model definitions and holds NULL in plenty
    of columns the models declare NOT NULL (blank=True without null=True). The
    fixtures are dumped from that database, so the test tables have to accept
    the same rows.
    """
    relaxed = [field for field in model._meta.local_fields if not field.primary_key and not field.null]
    for field in relaxed:
        field.null = True
    try:
        yield
    finally:
        for field in relaxed:
            field.null = False


def create_missing_tables(connection):
    """Create a table for every unmanaged model in UNMANAGED_APPS that lacks one."""
    created = []

    with connection.schema_editor() as schema_editor:
        for model in unmanaged_models():
            # refreshed every iteration: create_model() also creates m2m through tables
            if model._meta.db_table in connection.introspection.table_names():
                continue

            with nullable_columns(model):
                schema_editor.create_model(model)
            created.append(model._meta.db_table)

    return created


class UnmanagedTablesRunner(DiscoverRunner):

    def setup_databases(self, **kwargs):
        old_config = super().setup_databases(**kwargs)

        for connection in connections.all():
            created = create_missing_tables(connection)
            if created and self.verbosity >= 2:
                self.log("Created tables for unmanaged models: %s" % ", ".join(sorted(created)))

        return old_config
