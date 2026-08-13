# -*- coding: utf-8 -*-
"""Layer 2 — /api/thesaurus/term/.

Real URLconf, real resource, real dehydrate, real serializer, real records;
only Elasticsearch is faked. Assertions are made on the parsed response, never
on its string form.
"""

from api.tests.support import (
	MUSCLES,
	POISONING,
	SEROTONIN,
	EndpointTestCase,
	term_hit,
)


class WordsSearchTest(EndpointTestCase):

	def setUp(self):
		super().setUp()
		self.es.simple_results = [term_hit(MUSCLES)]

	def test_the_record_is_rendered_under_the_first_tree_number(self):
		root = self.xml(self.get_term(words='musculos'))

		self.assertEqual(root.tag, 'decsvmx')
		self.assertEqual(root.get('version'), '2.0')
		self.assertEqual(root.xpath('//decsws_response/@tree_id'), [MUSCLES['tree_numbers'][0]])
		self.assertEqual(root.xpath('//decsws_response/@service'), [''])

	def test_the_record_carries_the_language_the_database_and_the_mfn(self):
		root = self.xml(self.get_term(words='musculos'))
		record = root.xpath('//record')[0]

		self.assertEqual(record.get('lang'), 'pt')
		self.assertEqual(record.get('db'), 'decs')
		self.assertEqual(record.get('mfn'), MUSCLES['decs_code'])

	def test_every_language_of_the_descriptor_is_listed(self):
		root = self.xml(self.get_term(words='musculos'))

		self.assertEqual(
			dict(zip(root.xpath('//descriptor/@lang'), root.xpath('//descriptor/text()'))),
			{'en': 'Muscles', 'es': 'Músculos', 'pt-br': 'Músculos', 'fr': 'Muscles', 'es-es': 'músculos'},
		)

	def test_synonyms_are_limited_to_the_requested_language(self):
		root = self.xml(self.get_term(words='musculos'))

		self.assertTexts(root, '//synonym_list/synonym', ['Tecido Muscular'])

	def test_the_definition_is_the_scope_note_of_the_requested_language(self):
		root = self.xml(self.get_term(words='musculos'))

		self.assertEqual(
			root.xpath('//definition/occ/@n'),
			['Tecidos contráteis que produzem movimentos nos animais.'],
		)

	def test_every_tree_number_of_the_record_is_listed(self):
		root = self.xml(self.get_term(words='musculos'))

		self.assertTexts(root, '//tree_id_list/tree_id', MUSCLES['tree_numbers'])

	def test_the_nlm_identifier_is_returned(self):
		root = self.xml(self.get_term(words='musculos'))

		self.assertTexts(root, '//unique_identifier_nlm', [MUSCLES['nlm']])

	def test_the_query_is_echoed_on_the_root_element(self):
		root = self.xml(self.get_term(words='musculos'))

		self.assertEqual(root.get('query'), 'musculos')

	def test_the_search_reaches_elasticsearch_as_a_words_query(self):
		self.get_term(words='tecido muscular')

		self.assertEqual(self.es.simple_calls[0]['index'], ['descriptor_term', 'qualifier_term'])
		self.assertEqual(
			self.es.last_simple_query()['bool']['must'],
			[{'match': {'term_string': {'query': 'tecido muscular', 'operator': 'AND'}}}],
		)

	def test_a_dollar_sign_is_accepted_as_the_wildcard(self):
		self.get_term(words='muscul$')

		self.assertEqual(self.es.last_simple_query()['bool']['must'], [{'wildcard': {'term_string': 'muscul*'}}])

	def test_the_thesaurus_and_status_reach_elasticsearch(self):
		self.get_term(words='musculos', ths='2', status='0')

		self.assertEqual(self.es.last_simple_query()['bool']['filter'], [
			{'term': {'status': '0'}},
			{'term': {'language_code': 'pt-br'}},
			{'term': {'term_thesaurus': '2'}},
		])

	def test_no_recognised_parameter_returns_an_empty_response(self):
		response = self.get_term(unknown='musculos')
		root = self.xml(response)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(root.xpath('//decsws_response'), [])
		self.assertFalse(self.es.simple_calls)


class LanguageTest(EndpointTestCase):

	def setUp(self):
		super().setUp()
		self.es.simple_results = [term_hit(MUSCLES)]

	def assertLanguage(self, response, lang, self_term):
		root = self.xml(response)

		self.assertEqual(root.xpath('//record/@lang'), [lang])
		self.assertTexts(root, '//tree/self/term_list/term', [self_term])

	def test_portuguese_is_the_default(self):
		self.assertLanguage(self.get_term(words='musculos'), 'pt', MUSCLES['pt'])

	def test_english_is_honoured(self):
		self.assertLanguage(self.get_term(words='muscles', lang='en'), 'en', MUSCLES['en'])

	def test_spanish_is_honoured(self):
		self.assertLanguage(self.get_term(words='musculos', lang='es'), 'es', MUSCLES['es'])

	def test_an_unknown_language_falls_back_to_portuguese(self):
		self.assertLanguage(self.get_term(words='musculos', lang='zz'), 'pt', MUSCLES['pt'])

	def test_the_language_filter_reaches_elasticsearch(self):
		self.get_term(words='muscles', lang='en')

		self.assertIn({'term': {'language_code': 'en'}}, self.es.last_simple_query()['bool']['filter'])


class DescriptorExtrasTest(EndpointTestCase):
	"""The blocks that only descriptors carry, each filtered by language."""

	def test_pharmacological_actions_are_listed_in_the_requested_language(self):
		self.es.simple_results = [term_hit(SEROTONIN)]

		root = self.xml(self.get_term(words='serotonina'))

		self.assertTexts(root, '//pharmacological_action_list/pharmacological_action',
		                 ['Agonistas do Receptor de Serotonina'])
		self.assertAttrs(root, '//pharmacological_action_list/pharmacological_action', 'lang', ['pt'])

	def test_entry_combinations_keep_their_own_attributes_and_gain_the_language(self):
		self.es.simple_results = [term_hit(MUSCLES)]

		root = self.xml(self.get_term(words='musculos'))
		entry_combination = root.xpath('//entry_combination_list/entry_combination')[0]

		self.assertEqual(entry_combination.text, 'Desenvolvimento Muscular')
		self.assertEqual(entry_combination.get('sh_abbr1'), 'GD')
		self.assertEqual(entry_combination.get('lang'), 'pt-br')

	def test_see_related_terms_are_listed(self):
		self.es.simple_results = [term_hit(MUSCLES)]

		root = self.xml(self.get_term(words='musculos'))

		self.assertTexts(root, '//see_related_list/see_related',
		                 ['Miografia', 'Sarcolema', 'Retículo Sarcoplasmático'])

	def test_allowable_qualifiers_are_identified_by_their_decs_code(self):
		self.es.simple_results = [term_hit(MUSCLES)]

		root = self.xml(self.get_term(words='musculos'))
		qualifiers = root.xpath('//allowable_qualifier_list/allowable_qualifier')

		self.assertEqual(qualifiers[0].text, 'AB')
		self.assertEqual(qualifiers[0].get('id'), '22005')
		self.assertEqual(len(qualifiers), 23)

	def test_the_indexing_annotation_and_consider_also_are_in_the_requested_language(self):
		self.es.simple_results = [term_hit(MUSCLES)]

		root = self.xml(self.get_term(words='musculos'))

		self.assertTexts(root, '//consider_also_terms_at', ['MIO-'])
		self.assertEqual(len(root.xpath('//indexing_annotation')), 1)
		self.assertIn('MÚSCULO ESQUELÉTICO', root.xpath('//indexing_annotation')[0].text)


class QualifierRecordTest(EndpointTestCase):

	def setUp(self):
		super().setUp()
		self.es.simple_results = [term_hit(POISONING, term_type='qualifier')]

	def test_labels_are_prefixed_with_a_slash(self):
		root = self.xml(self.get_term(words='intoxicacao'))

		self.assertEqual(
			dict(zip(root.xpath('//descriptor/@lang'), root.xpath('//descriptor/text()')))['pt-br'],
			'/' + POISONING['pt'],
		)

	def test_synonyms_are_prefixed_with_a_slash(self):
		root = self.xml(self.get_term(words='intoxicacao'))

		self.assertTexts(root, '//synonym_list/synonym',
		                 ['/envenenamento', '/efeitos venenosos', '/efeitos tóxicos'])

	def test_tree_numbers_are_limited_to_the_family_of_the_rendered_one(self):
		# the record also has Y07.020.010 and Y10.040, which belong to the other tree
		root = self.xml(self.get_term(words='intoxicacao'))

		self.assertTexts(root, '//tree_id_list/tree_id', ['Q45.020.010', 'Q60.040'])

	def test_the_descriptor_only_blocks_are_empty(self):
		root = self.xml(self.get_term(words='intoxicacao'))

		for block in ('allowable_qualifier_list', 'entry_combination_list',
		              'pharmacological_action_list', 'see_related_list'):
			self.assertEqual(len(root.xpath('//%s/*' % block)), 0, block)


class BoolSearchTest(EndpointTestCase):

	def test_an_or_expression_returns_the_union_of_both_searches(self):
		self.es.queue_simple([term_hit(MUSCLES)], [term_hit(SEROTONIN)])

		root = self.xml(self.get_term(bool='101 Músculos OR 101 Serotonina'))

		self.assertEqual(len(self.es.simple_calls), 2)
		self.assertTexts(root, '//unique_identifier_nlm', [MUSCLES['nlm'], SEROTONIN['nlm']])

	def test_an_and_expression_returns_the_intersection(self):
		self.es.queue_simple([term_hit(MUSCLES), term_hit(SEROTONIN)], [term_hit(SEROTONIN)])

		root = self.xml(self.get_term(bool='101 Músculos AND 101 Serotonina'))

		self.assertTexts(root, '//unique_identifier_nlm', [SEROTONIN['nlm']])

	def test_each_part_is_searched_with_its_own_prefix(self):
		self.es.queue_simple([term_hit(MUSCLES)], [term_hit(SEROTONIN)])

		self.get_term(bool='101 Músculos OR 401 Serotonina')

		self.assertEqual(self.es.simple_calls[0]['query'].to_dict()['bool']['must'],
		                 [{'match': {'term_string.full_field': 'Músculos'}}])
		self.assertEqual(self.es.simple_calls[1]['query'].to_dict()['bool']['must'],
		                 [{'match': {'term_string': {'query': 'Serotonina', 'analyzer': 'keyword_asciifolding'}}}])

	def test_the_expression_is_echoed_on_the_root_element(self):
		self.es.simple_results = [term_hit(MUSCLES)]

		root = self.xml(self.get_term(bool='101 Músculos'))

		self.assertEqual(root.get('query'), '101 Músculos')

	def test_a_dollar_sign_is_accepted_as_the_wildcard(self):
		self.es.simple_results = [term_hit(MUSCLES)]

		self.get_term(bool='101 Muscul$')

		self.assertEqual(self.es.last_simple_query()['bool']['must'],
		                 [{'wildcard': {'term_string.full_field': 'Muscul*'}}])

	def test_an_unparsable_expression_is_a_404(self):
		response = self.get_term(bool='101 Músculos AND (101 Serotonina')

		self.assertEqual(response.status_code, 404)


class FirstLevelTest(EndpointTestCase):
	"""tree_id= (empty) browses the first level categories."""

	def test_the_categories_are_listed_in_the_requested_language(self):
		root = self.xml(self.get_term(tree_id=''))

		terms = root.xpath('//tree/term_list/term')

		self.assertEqual(terms[0].get('tree_id'), 'A')
		self.assertEqual(terms[0].text, 'ANATOMIA')
		self.assertEqual([term.get('tree_id') for term in terms][:4], ['A', 'B', 'C', 'D'])
		# qualifier categories (Q, Y) are not part of the descriptor tree
		self.assertNotIn('Q', [term.get('tree_id') for term in terms])

	def test_the_response_carries_no_tree_id_and_no_record(self):
		root = self.xml(self.get_term(tree_id=''))

		self.assertEqual(root.xpath('//decsws_response/@tree_id'), [''])
		self.assertEqual(root.xpath('//record'), [])

	def test_english_returns_the_english_labels(self):
		root = self.xml(self.get_term(tree_id='', lang='en'))

		self.assertEqual(root.xpath('//tree/term_list/term')[0].text, 'ANATOMY')
		self.assertEqual(root.xpath('//tree/term_list/@lang'), ['en'])

	def test_elasticsearch_is_not_involved(self):
		self.get_term(tree_id='')

		self.assertFalse(self.es.simple_calls)


class SecondLevelTest(EndpointTestCase):
	"""A tree_id shorter than three characters browses one category."""

	def test_the_category_and_its_descendants_are_returned(self):
		root = self.xml(self.get_term(tree_id='A'))

		self.assertEqual(root.xpath('//decsws_response/@tree_id'), ['A'])
		self.assertTexts(root, '//tree/self/term_list/term', ['ANATOMIA'])
		self.assertEqual(root.xpath('//tree/descendants/term_list/term/@tree_id')[:3], ['A01', 'A02', 'A03'])

	def test_the_category_is_matched_case_insensitively(self):
		root = self.xml(self.get_term(tree_id='a'))

		self.assertTexts(root, '//tree/self/term_list/term', ['ANATOMIA'])

	def test_there_are_no_ancestors_and_no_siblings(self):
		root = self.xml(self.get_term(tree_id='A'))

		for block in ('ancestors', 'preceding_sibling', 'following_sibling'):
			self.assertEqual(len(root.xpath('//tree/%s/*' % block)), 0, block)

	def test_the_record_is_a_skeleton_with_the_category_labels(self):
		root = self.xml(self.get_term(tree_id='A'))

		self.assertEqual(root.xpath('//record/@mfn'), [''])
		self.assertEqual(sorted(root.xpath('//descriptor/text()')),
		                 sorted(['ANATOMY', 'ANATOMÍA', 'ANATOMIA', 'ANATOMIE']))
		self.assertEqual(root.xpath('//definition/occ/@n'), [''])
		self.assertEqual(len(root.xpath('//allowable_qualifier_list/*')), 0)


class FullTreeTest(EndpointTestCase):
	"""A full tree_id returns the record plus its neighbourhood in that tree."""

	def setUp(self):
		super().setUp()
		self.es.simple_results = [term_hit(MUSCLES)]

	def test_the_tree_id_is_searched_in_the_tree_number_indexes(self):
		self.get_term(tree_id='a02.633')

		self.assertEqual(self.es.simple_calls[0]['index'], ['descriptor_treenumber', 'qualifier_treenumber'])
		self.assertEqual(self.es.last_simple_query()['bool']['filter'][0], {'term': {'tree_number': 'A02.633'}})

	def test_the_requested_tree_number_drives_the_response(self):
		root = self.xml(self.get_term(tree_id='A10.690'))

		self.assertEqual(root.xpath('//decsws_response/@tree_id'), ['A10.690'])
		self.assertTexts(root, '//tree/self/term_list/term', [MUSCLES['pt']])
		self.assertEqual(root.xpath('//tree/self/term_list/term/@tree_id'), ['A10.690'])

	def test_ancestors_cover_every_tree_number_of_the_record(self):
		root = self.xml(self.get_term(tree_id='A02.633'))

		self.assertEqual(root.xpath('//tree/ancestors/term_list/term/@tree_id'), ['A', 'A02', 'A', 'A10'])

	def test_siblings_and_descendants_come_from_the_requested_tree_number(self):
		root = self.xml(self.get_term(tree_id='A02.633'))

		self.assertEqual(root.xpath('//tree/preceding_sibling/term_list/term/@tree_id'),
		                 ['A02.083', 'A02.165', 'A02.340', 'A02.513'])
		self.assertEqual(root.xpath('//tree/following_sibling/term_list/term/@tree_id'),
		                 ['A02.734', 'A02.835', 'A02.880'])
		self.assertEqual(root.xpath('//tree/descendants/term_list/term/@tree_id'),
		                 ['A02.633.567', 'A02.633.570', 'A02.633.580'])

	def test_the_query_attribute_is_not_the_tree_id(self):
		# characterizes today's behaviour: only words= and bool= echo a query,
		# so the serializer's placeholder is what reaches the client here
		root = self.xml(self.get_term(tree_id='A02.633'))

		self.assertEqual(root.get('query'), 'query')


class CharacterizationTest(EndpointTestCase):
	"""Today's behaviour on paths that are known to be fragile.

	These are not endorsements: each one pins what the API does now so the
	follow-up fix has something to change deliberately.
	"""

	def setUp(self):
		super().setUp()
		self.allow_server_error()

	def test_a_tree_id_that_does_not_belong_to_the_record_returns_500(self):
		# thesaurus_term_api.py:372-384 only binds full_tree when one of the
		# record's tree numbers equals the requested one, and then reads it
		# unconditionally. Reproduce with: tree_id=C01.001 matching Muscles.
		self.es.simple_results = [term_hit(MUSCLES)]

		response = self.get_term(tree_id='C01.001')

		self.assertEqual(response.status_code, 500)

	def test_an_unknown_two_character_tree_id_returns_500_instead_of_404(self):
		# thesaurus_term_api.py:166 calls FirstLevel.objects.get() unguarded, so
		# a category that does not exist raises DoesNotExist.
		response = self.get_term(tree_id='ZZ')

		self.assertEqual(response.status_code, 500)

	def test_the_slash_prefix_of_a_qualifier_is_not_applied_twice(self):
		# thesaurus_term_api.py prefixes qualifier labels in place, mutating the
		# JSONField payload of the loaded model. Harmless today because the
		# object is discarded after each request — this test is what would fail
		# if the records were ever cached between requests.
		self.es.simple_results = [term_hit(POISONING, term_type='qualifier')]

		self.get_term(words='intoxicacao')
		root = self.xml(self.get_term(words='intoxicacao'))

		self.assertNotIn('//' + POISONING['pt'], root.xpath('//descriptor/text()'))
		self.assertIn('/' + POISONING['pt'], root.xpath('//descriptor/text()'))


class ResponseFormatTest(EndpointTestCase):

	def setUp(self):
		super().setUp()
		self.es.simple_results = [term_hit(MUSCLES)]

	def test_xml_is_the_default(self):
		response = self.get_term(words='musculos')

		self.assertContentType(response, 'application/xml')

	def test_json_is_returned_on_request(self):
		payload = self.json(self.get_term(words='musculos', format='json'))
		record = payload['objects'][0]['decsws_response']['record_list']['record']

		self.assertEqual(record['attr']['mfn'], MUSCLES['decs_code'])
		self.assertEqual(record['unique_identifier_nlm'], MUSCLES['nlm'])

	def test_the_accept_header_selects_json(self):
		response = self.client.get('/api/thesaurus/term/', {'words': 'musculos'},
		                           HTTP_ACCEPT='application/json')

		self.assertContentType(response, 'application/json')

	def test_pagination_metadata_is_not_part_of_the_response(self):
		payload = self.json(self.get_term(words='musculos', format='json'))

		self.assertNotIn('meta', payload)
