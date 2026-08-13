from django.test import SimpleTestCase, TestCase

from django_elasticsearch_dsl.registries import registry

# the four documents the API actually searches; every one of them has rows in
# the fixture, so prepare() can be exercised against real data
SEARCHED_INDEXES = {'descriptor_term', 'qualifier_term', 'descriptor_treenumber', 'qualifier_treenumber'}


class PreparedFieldsTest(SimpleTestCase):
	"""Guard against the silent indexing regression described in BaseDocument.

	When _prepared_fields comes back empty, prepare() returns {} and
	``search_index --rebuild`` populates every index with empty documents
	while still reporting success and the correct document count. Nothing
	raises, so only an explicit check catches it.
	"""

	def test_every_document_prepares_all_of_its_mapped_fields(self):
		documents = registry.get_documents()
		self.assertTrue(documents, "no documents registered")

		for document in documents:
			with self.subTest(document=document.__name__):
				prepared = {name for name, _, _ in document()._prepared_fields}
				self.assertEqual(prepared, set(document._fields))


class PreparedDocumentTest(TestCase):
	"""The same guard one level further: a real row must produce a real document.

	_prepared_fields being right is necessary but not sufficient — this is the
	check that would have caught the empty-document rebuild at the level the
	cluster sees it.
	"""

	fixtures = ['decs_sample.json']

	def test_a_real_row_is_prepared_into_a_non_empty_document(self):
		covered = set()

		for document in registry.get_documents():
			index_name = document._index._name
			instance = document.django.model.objects.first()
			if instance is None:
				continue

			with self.subTest(index=index_name):
				prepared = document().prepare(instance)

				self.assertTrue(prepared, "%s prepared an empty document" % index_name)
				self.assertEqual(set(prepared), set(document._fields))
				covered.add(index_name)

		self.assertEqual(SEARCHED_INDEXES - covered, set(), "fixture no longer covers every searched index")
