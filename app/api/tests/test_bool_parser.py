# -*- coding: utf-8 -*-
"""Layer 1 — the bool expression parser and the set algebra built on top of it.

complex_search() is exercised with execute_simple_search() stubbed, so what is
asserted is the combination of results, not Elasticsearch.
"""

from unittest import mock

from django.http import Http404
from django.test import SimpleTestCase

from api import esearch_functions
from api.esearch_functions import complex_search, f_parse

STATUS = '1'
THS = '1'
LANG = 'pt-br'


def descriptor(identifier):
	return {'identifier': identifier, 'term_type': 'descriptor'}


class FParseTest(SimpleTestCase):

	def test_or_between_two_prefixed_terms(self):
		self.assertEqual(
			f_parse('401 Supply OR (401 Rural AND 401 Water)'),
			[['401', 'Supply'], 'OR', [['401', 'Rural'], 'AND', ['401', 'Water']]],
		)

	def test_and_not_binds_to_the_right(self):
		self.assertEqual(
			f_parse('(401 Supply AND NOT 401 Water) AND 401 Rural'),
			[[['401', 'Supply'], 'AND NOT', ['401', 'Water']], 'AND', ['401', 'Rural']],
		)

	def test_terms_may_contain_commas(self):
		self.assertEqual(
			f_parse('101 Abdomen, Acute AND 103 Acute Abdomen'),
			[['101', 'Abdomen, Acute'], 'AND', ['103', 'Acute Abdomen']],
		)

	def test_a_bare_term_without_a_prefix_is_a_single_condition(self):
		self.assertEqual(f_parse('Acute Abdomen'), ['Acute Abdomen'])

	def test_latin1_characters_are_accepted(self):
		self.assertEqual(f_parse('101 Nutrición AND 101 Saúde'),
		                 [['101', 'Nutrición'], 'AND', ['101', 'Saúde']])

	def test_nested_groups_are_preserved(self):
		self.assertEqual(
			f_parse('(401 A OR 401 B) AND (401 C OR 401 D)'),
			[[['401', 'A'], 'OR', ['401', 'B']], 'AND', [['401', 'C'], 'OR', ['401', 'D']]],
		)

	def test_an_unbalanced_expression_raises_http404(self):
		with self.assertRaises(Http404):
			f_parse('401 Supply AND (401 Water')


class ComplexSearchTest(SimpleTestCase):
	"""Set algebra over the stubbed search results."""

	def setUp(self):
		self.results = {}
		patcher = mock.patch.object(
			esearch_functions, 'execute_simple_search',
			side_effect=lambda search_q: self.results.get(self.text_of(search_q), []),
		)
		self.execute = patcher.start()
		self.addCleanup(patcher.stop)

	def text_of(self, search_q):
		"""Recover the searched text from the rendered query, to key the stub on."""
		return repr(search_q['query'].to_dict())

	def stub(self, prefix, text, results):
		search_q = esearch_functions.get_search_q(prefix, text, None, STATUS, LANG, THS)
		self.results[self.text_of(search_q)] = results

	def search(self, parts):
		return complex_search(parts, STATUS, LANG, THS)

	def test_a_single_bare_term_is_searched_as_407(self):
		self.stub('407', 'Abdomen', [descriptor(1)])

		self.assertEqual(self.search(['Abdomen']), [descriptor(1)])

	def test_a_single_prefixed_term_is_searched_with_that_prefix(self):
		self.stub('101', 'Abdomen', [descriptor(1)])

		self.assertEqual(self.search(['101', 'Abdomen']), [descriptor(1)])

	def test_and_intersects_the_two_result_sets(self):
		self.stub('401', 'Water', [descriptor(1), descriptor(2)])
		self.stub('401', 'Supply', [descriptor(2), descriptor(3)])

		self.assertEqual(self.search([['401', 'Water'], 'AND', ['401', 'Supply']]), [descriptor(2)])

	def test_or_unions_the_result_sets_keeping_first_seen_order(self):
		self.stub('401', 'Water', [descriptor(1), descriptor(2)])
		self.stub('401', 'Supply', [descriptor(2), descriptor(3)])

		self.assertEqual(
			self.search([['401', 'Water'], 'OR', ['401', 'Supply']]),
			[descriptor(1), descriptor(2), descriptor(3)],
		)

	def test_and_not_removes_the_right_hand_results(self):
		self.stub('401', 'Water', [descriptor(1), descriptor(2)])
		self.stub('401', 'Supply', [descriptor(2)])

		self.assertEqual(self.search([['401', 'Water'], 'AND NOT', ['401', 'Supply']]), [descriptor(1)])

	def test_105_runs_two_independent_searches_and_unions_them(self):
		# 105 = preferred term OR historical term, which cannot be one query
		self.stub('101', 'Abdomen', [descriptor(1)])
		self.stub('104', 'Abdomen', [descriptor(2)])

		self.assertEqual(self.search(['105', 'Abdomen']), [descriptor(1), descriptor(2)])
		self.assertEqual(self.execute.call_count, 2)

	def test_406_runs_two_independent_word_by_word_searches(self):
		self.stub('402', 'Abdomen', [descriptor(1)])
		self.stub('404', 'Abdomen', [descriptor(2)])

		self.assertEqual(self.search(['406', 'Abdomen']), [descriptor(1), descriptor(2)])

	def test_an_unknown_operator_returns_nothing(self):
		self.assertEqual(self.search([['401', 'Water'], 'NEAR', ['401', 'Supply']]), [])
		self.assertFalse(self.execute.called)

	def test_nested_groups_are_resolved_depth_first(self):
		self.stub('401', 'A', [descriptor(1), descriptor(2)])
		self.stub('401', 'B', [descriptor(2), descriptor(3)])
		self.stub('401', 'C', [descriptor(3)])

		parts = [[['401', 'A'], 'OR', ['401', 'B']], 'AND', ['401', 'C']]

		self.assertEqual(self.search(parts), [descriptor(3)])
