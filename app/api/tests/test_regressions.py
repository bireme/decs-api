# -*- coding: utf-8 -*-
"""Named locks for the three bugs this branch line fixed.

Each test names the plan it belongs to and the symptom it prevents, so a future
change that reintroduces the bug fails with an explanation rather than a diff.
"""

from unittest import mock

from django.test import SimpleTestCase
from django_elasticsearch_dsl.registries import registry
from elasticsearch.dsl import Q

from api import esearch_functions
from api.tests.support import MUSCLES, EndpointTestCase, quick_hit


class QuickTermOrderingRegression(EndpointTestCase):
	""".ai/plans/001-fix-ordering-terms-quickterm.md

	A wildcard top-2 query is score-flat, so Elasticsearch returns an arbitrary
	order and the quick search showed different terms from the old API. The fix
	sorts that phase explicitly: preferred term first, then case-sensitive
	alphabetical.
	"""

	def setUp(self):
		super().setUp()
		self.es.quick_results = [[quick_hit(MUSCLES)], []]

	def test_a_wildcard_query_asks_for_the_deterministic_top_two(self):
		self.get_quickterm(query='muscul*')

		self.assertTrue(self.es.quick_calls[0]['top_sorted'])

	def test_a_plain_query_is_left_to_relevance(self):
		self.get_quickterm(query='musculos')

		self.assertFalse(self.es.quick_calls[0]['top_sorted'])

	def test_a_dollar_sign_counts_as_a_wildcard_for_the_sort(self):
		self.get_quickterm(query='muscul$')

		self.assertTrue(self.es.quick_calls[0]['top_sorted'])


class QuickSearchSortClauseRegression(SimpleTestCase):
	""".ai/plans/001-fix-ordering-terms-quickterm.md — the clauses themselves.

	Elasticsearch is replaced by a mock Search here, so the sort that would be
	sent to the cluster can be asserted without one.
	"""

	def search_for(self, **kwargs):
		search_q = {'index': ['descriptor_term'], 'query': Q('match_all')}

		with mock.patch.object(esearch_functions, 'Search') as search_class:
			esearch_functions.execute_quick_search(search_q, **kwargs)

		return search_class.return_value.query.return_value

	def test_the_top_two_are_ordered_preferred_first_then_alphabetically(self):
		search = self.search_for(top_sorted=True)

		search.extra.assert_called_once_with(size=2)
		search.extra.return_value.sort.assert_called_once_with(
			{'record_preferred_term': 'desc'},  # 'Y' before 'N'
			{'term_string.sort': 'asc'},
		)

	def test_an_unsorted_top_two_is_left_alone(self):
		search = self.search_for()

		self.assertFalse(search.extra.return_value.sort.called)

	def test_the_alphabetical_phase_sorts_on_the_case_sensitive_keyword(self):
		# term_string.sort has no normalizer, which is what reproduces the old
		# API's byte order
		search = self.search_for(sort='Y')

		search.sort.assert_called_once_with({'term_string.sort': 'asc'})


class WildcardMultiWordRegression(EndpointTestCase):
	""".ai/plans/002-fix-wildcard-multiword-quickterm.md

	'transtorno espectro au*' returned nothing, because a truncated quick search
	was sent as one wildcard over the whole field, which cannot skip the words
	in between ('transtorno do espectro autista'). Both phases now search word
	by word.
	"""

	QUERY = 'transtorno espectro au*'

	WORD_BY_WORD = [
		{'match': {'term_string': 'transtorno'}},
		{'match': {'term_string': 'espectro'}},
		{'wildcard': {'term_string': 'au*'}},
	]

	def setUp(self):
		super().setUp()
		self.es.quick_results = [[quick_hit(MUSCLES)], []]

	def test_the_top_two_phase_searches_word_by_word(self):
		self.get_quickterm(query=self.QUERY)

		self.assertEqual(self.es.quick_query(0)['bool']['must'], self.WORD_BY_WORD)

	def test_the_alphabetical_phase_searches_word_by_word(self):
		self.get_quickterm(query=self.QUERY)

		self.assertEqual(self.es.quick_query(1)['bool']['must'], self.WORD_BY_WORD)

	def test_neither_phase_falls_back_to_a_whole_string_wildcard(self):
		self.get_quickterm(query=self.QUERY)

		for index in (0, 1):
			self.assertNotIn({'wildcard': {'term_string.full_field': self.QUERY}},
			                 self.es.quick_query(index)['bool']['must'])


class EmptyDocumentRegression(SimpleTestCase):
	"""docs/elasticsearch.md — the empty-documents rebuild.

	elasticsearch-dsl 9.4 routes attribute writes into the internal _d_ dict, so
	django_elasticsearch_dsl's `self._prepared_fields = ...` was swallowed and
	prepare() returned {}: the rebuild filled every index with empty documents
	and still reported success. BaseDocument assigns through object.__setattr__,
	which puts the value in the instance __dict__.
	"""

	def test_prepared_fields_live_in_the_instance_dict(self):
		for document in registry.get_documents():
			with self.subTest(document=document.__name__):
				instance = document()

				self.assertIn('_prepared_fields', instance.__dict__)
				self.assertTrue(instance.__dict__['_prepared_fields'])
