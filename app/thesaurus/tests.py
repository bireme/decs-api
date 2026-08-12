from django.test import SimpleTestCase

from django_elasticsearch_dsl.registries import registry


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
