# -*- coding: utf-8 -*-
"""Dump the curated record slice used by the endpoint tests.

Run through the dev container (see `make dev_dump_test_fixtures`), which points
DATABASE_* at the dev MySQL. Writes app/api/tests/fixtures/decs_sample.json.

The slice is three real DeCS records plus everything the API reads to render
them. They were chosen for coverage, not size:

  * Muscles (decs_code 9324) — two tree numbers, pt-br/en/es labels, synonyms,
    scope notes, annotation, considerAlso, entry combinations, see-also and
    allowable qualifiers.
  * Serotonin (decs_code 24311) — three tree numbers plus pharmacological
    actions, which no single descriptor carries together with considerAlso.
  * /poisoning (decs_code 22025) — a qualifier with both Q and Y tree numbers.

The "full" tables (Descriptor, Qualifier, Tree*) share their primary key with
the corresponding Identifier* row, which is what the resources rely on when they
turn an Elasticsearch hit into a record; TreeDescriptor/TreeQualifier rows in
turn share their id with the TreeNumbersList* row. The dump follows those links
so the fixture loads with referential integrity intact.
"""

import json
import os
import sys

import django

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "decs_api.settings")
django.setup()

from django.core import serializers  # noqa: E402
from django.core.serializers.json import DjangoJSONEncoder  # noqa: E402

from thesaurus.models_descriptors import (  # noqa: E402
    IdentifierConceptListDesc,
    IdentifierDesc,
    TermListDesc,
    TreeNumbersListDesc,
)
from thesaurus.models_full import (  # noqa: E402
    Descriptor,
    FirstLevel,
    Qualifier,
    TreeDescriptor,
    TreeQualifier,
)
from thesaurus.models_qualifiers import (  # noqa: E402
    IdentifierConceptListQualif,
    IdentifierQualif,
    TermListQualif,
    TreeNumbersListQualif,
)
from thesaurus.models_thesaurus import Thesaurus  # noqa: E402

# documented record set — decs_code in the comment, primary key in the code
DESCRIPTOR_PKS = [10673, 14096]  # Muscles (9324), Serotonin (24311)
QUALIFIER_PKS = [53]             # /poisoning (22025)
THESAURUS = 1

PLACEHOLDER_TIMESTAMP = '2020-01-01T00:00:00Z'

FIXTURE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'api', 'tests', 'fixtures', 'decs_sample.json'
)


def collect():
    tree_desc = TreeNumbersListDesc.objects.filter(identifier_id__in=DESCRIPTOR_PKS)
    tree_qualif = TreeNumbersListQualif.objects.filter(identifier_id__in=QUALIFIER_PKS)

    concept_desc_pks = list(
        IdentifierConceptListDesc.objects.filter(identifier_id__in=DESCRIPTOR_PKS).values_list('pk', flat=True)
    )
    concept_qualif_pks = list(
        IdentifierConceptListQualif.objects.filter(identifier_id__in=QUALIFIER_PKS).values_list('pk', flat=True)
    )
    tree_desc_pks = list(tree_desc.values_list('pk', flat=True))
    tree_qualif_pks = list(tree_qualif.values_list('pk', flat=True))

    return [
        Thesaurus.objects.all(),
        # IdentifierDesc.abbreviation (m2m to IdentifierQualif) is left out: no
        # endpoint reads it — the resources use Descriptor.allowableQualifier —
        # and serializing it hits an unbounded recursion, because the serializer
        # loads the related rows with .only("pk") while Generic.__init__ builds
        # a model_to_dict() of every field, so each deferred field reloads the
        # row and constructs another instance.
        IdentifierDesc.objects.filter(pk__in=DESCRIPTOR_PKS),
        IdentifierQualif.objects.filter(pk__in=QUALIFIER_PKS),
        IdentifierConceptListDesc.objects.filter(pk__in=concept_desc_pks),
        IdentifierConceptListQualif.objects.filter(pk__in=concept_qualif_pks),
        TermListDesc.objects.filter(identifier_concept_id__in=concept_desc_pks),
        TermListQualif.objects.filter(identifier_concept_id__in=concept_qualif_pks),
        tree_desc,
        tree_qualif,
        Descriptor.objects.filter(pk__in=DESCRIPTOR_PKS),
        Qualifier.objects.filter(pk__in=QUALIFIER_PKS),
        TreeDescriptor.objects.filter(pk__in=tree_desc_pks),
        TreeQualifier.objects.filter(pk__in=tree_qualif_pks),
        # every first level category, so the tree_id browsing tests see the real list
        FirstLevel.objects.filter(thesaurus=THESAURUS).order_by('type', 'treeNumber'),
    ]


def main():
    records = []
    for queryset in collect():
        instances = list(queryset)

        # one queryset at a time, so m2m fields can be dropped per model
        fields = [field.name for field in queryset.model._meta.fields]
        serialized = serializers.serialize('python', instances, fields=fields)

        for record in serialized:
            # loaddata saves raw, so auto_now / auto_now_add are not filled in,
            # and some dev rows hold NULL where the model says NOT NULL — the
            # MySQL column is nullable. No endpoint reads these timestamps, so
            # a fixed stand-in keeps the fixture loadable on SQLite.
            for field in queryset.model._meta.fields:
                if not (getattr(field, 'auto_now', False) or getattr(field, 'auto_now_add', False)):
                    continue
                if not record['fields'].get(field.name):
                    record['fields'][field.name] = PLACEHOLDER_TIMESTAMP

            # created_by / updated_by point at editor accounts that only exist
            # in the DeCS admin database; no endpoint reads them
            for name in ('created_by', 'updated_by'):
                if name in record['fields']:
                    record['fields'][name] = None

        records.extend(serialized)
        print("%-32s %d" % (queryset.model.__name__, len(instances)))

    with open(FIXTURE_PATH, 'w', encoding='utf-8') as fixture:
        json.dump(records, fixture, indent=1, ensure_ascii=False, cls=DjangoJSONEncoder)
        fixture.write("\n")

    print("\nwrote %s (%d objects, %.0f KB)" % (
        os.path.relpath(FIXTURE_PATH), len(records), os.path.getsize(FIXTURE_PATH) / 1024,
    ))


if __name__ == '__main__':
    main()
