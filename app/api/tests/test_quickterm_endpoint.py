# -*- coding: utf-8 -*-
"""Layer 2 — /api/thesaurus/quickterm/.

The quick search runs two Elasticsearch queries per request: the top 2 most
relevant terms, then the alphabetical list. Both are faked here, so what is
under test is how the resource combines, truncates and renders them.
"""

from api.tests.support import (
	MUSCLES,
	POISONING,
	SEROTONIN,
	EndpointTestCase,
	quick_hit,
)


class QuickTermResponseTest(EndpointTestCase):

	def test_each_item_carries_the_first_tree_number_and_the_term(self):
		self.es.quick_results = [[quick_hit(MUSCLES)], []]

		root = self.xml(self.get_quickterm(query='musculos'))
		item = root.xpath('//item')[0]

		self.assertEqual(root.tag, 'DeCSTermService')
		self.assertEqual(item.get('id'), MUSCLES['tree_numbers'][0])
		self.assertEqual(item.get('term'), MUSCLES['pt'])

	def test_qualifier_terms_are_prefixed_with_a_slash(self):
		self.es.quick_results = [[quick_hit(POISONING, term_type='qualifier')], []]

		root = self.xml(self.get_quickterm(query='intoxicacao'))
		item = root.xpath('//item')[0]

		self.assertEqual(item.get('term'), '/' + POISONING['pt'])
		self.assertEqual(item.get('id'), 'Q45.020.010')

	def test_the_top_results_come_before_the_alphabetical_ones(self):
		self.es.quick_results = [
			[quick_hit(SEROTONIN)],
			[quick_hit(MUSCLES), quick_hit(POISONING, term_type='qualifier')],
		]

		root = self.xml(self.get_quickterm(query='ser'))

		self.assertEqual(root.xpath('//item/@term'),
		                 [SEROTONIN['pt'], MUSCLES['pt'], '/' + POISONING['pt']])

	def test_a_term_in_both_blocks_is_listed_twice(self):
		# the old API repeats the exact match at the top of the list; keep it
		self.es.quick_results = [[quick_hit(MUSCLES)], [quick_hit(MUSCLES)]]

		root = self.xml(self.get_quickterm(query='musculos'))

		self.assertEqual(root.xpath('//item/@term'), [MUSCLES['pt'], MUSCLES['pt']])

	def test_the_result_element_reports_the_number_of_items(self):
		self.es.quick_results = [[quick_hit(MUSCLES)], [quick_hit(SEROTONIN)]]

		root = self.xml(self.get_quickterm(query='mus'))
		result = root.xpath('//Result')[0]

		self.assertEqual(result.get('total'), '2')
		self.assertEqual(result.get('count'), '2')

	def test_a_missing_query_returns_no_items(self):
		response = self.get_quickterm(lang='pt')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(self.xml(response).xpath('//item'), [])
		self.assertFalse(self.es.quick_calls)


class QuickTermCountTest(EndpointTestCase):

	def setUp(self):
		super().setUp()
		self.es.quick_results = [
			[quick_hit(MUSCLES)],
			[quick_hit(SEROTONIN), quick_hit(POISONING, term_type='qualifier')],
		]

	def test_a_count_smaller_than_the_result_set_truncates_it(self):
		root = self.xml(self.get_quickterm(query='mus', count='2'))

		self.assertEqual(len(root.xpath('//item')), 2)
		self.assertEqual(root.xpath('//Result/@count'), ['2'])
		self.assertEqual(root.xpath('//Result/@total'), ['3'])

	def test_a_count_larger_than_the_result_set_leaves_it_whole(self):
		root = self.xml(self.get_quickterm(query='mus', count='50'))

		self.assertEqual(len(root.xpath('//item')), 3)


class QuickTermSearchTest(EndpointTestCase):
	"""What reaches Elasticsearch: two searches, with the request parameters."""

	def setUp(self):
		super().setUp()
		self.es.quick_results = [[quick_hit(MUSCLES)], []]

	def test_the_top_search_uses_the_relevance_ranked_prefix(self):
		self.get_quickterm(query='sindrome respiratoria', lang='pt')

		self.assertEqual(self.es.quick_query(0)['bool']['must'],
		                 [{'match_phrase': {'term_string': {'query': 'sindrome respiratoria', 'slop': 1}}}])
		self.assertIsNone(self.es.quick_calls[0]['sort'])

	def test_the_alphabetical_search_is_sorted(self):
		self.get_quickterm(query='sindrome', lang='pt')

		self.assertEqual(self.es.quick_calls[1]['sort'], 'Y')
		self.assertEqual(self.es.quick_query(1)['bool']['must'],
		                 [{'match': {'term_string': {'query': 'sindrome', 'operator': 'AND'}}}])

	def test_both_searches_look_in_the_term_indexes(self):
		self.get_quickterm(query='musculos')

		for call in self.es.quick_calls:
			self.assertEqual(call['search_q']['index'], ['descriptor_term', 'qualifier_term'])

	def test_without_a_language_spanish_from_spain_is_excluded(self):
		self.get_quickterm(query='musculos')

		self.assertEqual(self.es.quick_query(0)['bool']['must_not'],
		                 [{'match': {'language_code': 'es-es'}}])
		self.assertEqual(self.es.quick_query(1)['bool']['must_not'],
		                 [{'match': {'language_code': 'es-es'}}])

	def test_a_language_replaces_the_exclusion_with_a_filter(self):
		self.get_quickterm(query='muscles', lang='en')

		self.assertNotIn('must_not', self.es.quick_query(0)['bool'])
		self.assertIn({'term': {'language_code': 'en'}}, self.es.quick_query(0)['bool']['filter'])

	def test_the_thesaurus_and_status_are_threaded_through(self):
		self.get_quickterm(query='musculos', ths='2', status='0')

		self.assertEqual(self.es.quick_query(0)['bool']['filter'],
		                 [{'term': {'status': '0'}}, {'term': {'term_thesaurus': '2'}}])

	def test_a_dollar_sign_is_accepted_as_the_wildcard(self):
		self.get_quickterm(query='muscul$')

		self.assertEqual(self.es.quick_query(1)['bool']['must'],
		                 [{'wildcard': {'term_string': 'muscul*'}}])


class QuickTermCharacterizationTest(EndpointTestCase):
	"""Today's behaviour on paths that are known to be fragile.

	These are not endorsements: each one pins what the API does now so the
	follow-up fix has something to change deliberately.
	"""

	def setUp(self):
		super().setUp()
		self.allow_server_error()

	def test_a_term_without_a_tree_number_returns_500(self):
		# thesaurus_quickterm_api.py:150-151 indexes treeN_list[0] with no guard,
		# so a term whose identifier has no TreeNumbersList row raises IndexError.
		# Reproduce with: any query matching such a term.
		self.es.quick_results = [[{'identifier': 999999, 'term_type': 'descriptor', 'term_string': 'ghost'}], []]

		response = self.get_quickterm(query='ghost')

		self.assertEqual(response.status_code, 500)

	def test_the_page_size_of_one_request_leaks_into_the_next(self):
		# thesaurus_quickterm_api.py:128-131 assigns self._meta.limit on the
		# resource, which every later request shares. A request that searches
		# nothing never reassigns it, so it reports the previous request's size.
		self.es.quick_results = [[quick_hit(MUSCLES)], [quick_hit(SEROTONIN)]]
		self.get_quickterm(query='mus', count='1')

		root = self.xml(self.get_quickterm(lang='pt'))

		self.assertEqual(root.xpath('//item'), [])
		self.assertEqual(root.xpath('//Result/@count'), ['1'])


class QuickTermFormatTest(EndpointTestCase):

	def setUp(self):
		super().setUp()
		self.es.quick_results = [[quick_hit(MUSCLES)], []]

	def test_xml_is_the_default(self):
		response = self.get_quickterm(query='musculos')

		self.assertContentType(response, 'application/xml')

	def test_json_is_returned_on_request(self):
		payload = self.json(self.get_quickterm(query='musculos', format='json'))

		self.assertEqual(payload['objects'][0]['item']['attr'],
		                 {'id': MUSCLES['tree_numbers'][0], 'term': MUSCLES['pt']})

	def test_json_keeps_the_pagination_metadata_that_xml_folds_into_result(self):
		payload = self.json(self.get_quickterm(query='musculos', format='json'))

		self.assertEqual(payload['meta']['total_count'], 1)
