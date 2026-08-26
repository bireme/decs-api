# -*- coding: utf-8 -*-
"""Layer 1 — the Elasticsearch query DSL produced by get_search_q().

No database, no cluster: every assertion is made on the rendered query dict, so
a change in how a prefix searches shows up here rather than in production.
"""

from django.test import SimpleTestCase

from api.esearch_functions import get_search_q, truncated_word_must

STATUS = '1'
THS = '1'
LANG = 'pt-br'

TERM_INDEXES = ['descriptor_term', 'qualifier_term']
PREVIOUS_INDEXES = ['previous_term']
ALL_TERM_INDEXES = ['descriptor_term', 'qualifier_term', 'previous_term']

FILTER_GRAL = [
	{'term': {'status': STATUS}},
	{'term': {'language_code': LANG}},
	{'term': {'term_thesaurus': THS}},
]
FILTER_NO_LANG = [
	{'term': {'status': STATUS}},
	{'term': {'term_thesaurus': THS}},
]
FILTER_PREFERRED = FILTER_GRAL + [{'term': {'record_preferred_term': 'Y'}}]
FILTER_SYNONYM = FILTER_GRAL + [{'term': {'record_preferred_term': 'N'}}]
MUST_NOT_ES_ES = [{'match': {'language_code': 'es-es'}}]


def build(op_prefix, text, op=None, status=STATUS, lang_code=LANG, ths=THS):
	return get_search_q(op_prefix, text, op, status, lang_code, ths)


def query_of(search_q):
	return search_q['query'].to_dict()


class FilterGralTest(SimpleTestCase):
	"""The three (lang_code, ths) combinations that decide the shared filter."""

	def test_no_language_and_no_thesaurus_means_no_filter_at_all(self):
		search_q = build('words', 'abdomen', lang_code=None, ths=None)

		# an empty filter list is dropped entirely by the DSL serializer
		self.assertNotIn('filter', query_of(search_q)['bool'])

	def test_no_language_keeps_status_and_thesaurus(self):
		search_q = build('words', 'abdomen', lang_code=None)

		self.assertEqual(query_of(search_q)['bool']['filter'], FILTER_NO_LANG)

	def test_language_adds_the_language_filter(self):
		search_q = build('words', 'abdomen')

		self.assertEqual(query_of(search_q)['bool']['filter'], FILTER_GRAL)


class WordsOptionTest(SimpleTestCase):

	def test_plain_text_matches_every_word_of_the_full_field(self):
		search_q = build('words', 'acute abdomen')

		self.assertEqual(search_q['index'], TERM_INDEXES)
		self.assertEqual(query_of(search_q), {
			'bool': {
				'must': [{'match': {'term_string': {'query': 'acute abdomen', 'operator': 'AND'}}}],
				'filter': FILTER_GRAL,
			}
		})

	def test_wildcard_text_becomes_a_wildcard_on_the_analyzed_field(self):
		search_q = build('words', 'abdom*')

		self.assertEqual(query_of(search_q)['bool']['must'], [{'wildcard': {'term_string': 'abdom*'}}])


class QuickOptionTest(SimpleTestCase):

	def test_plain_text_matches_every_word(self):
		search_q = build('quick', 'acute abdomen')

		self.assertEqual(search_q['index'], TERM_INDEXES)
		self.assertEqual(query_of(search_q), {
			'bool': {
				'must': [{'match': {'term_string': {'query': 'acute abdomen', 'operator': 'AND'}}}],
				'filter': FILTER_GRAL,
			}
		})

	def test_wildcard_text_is_searched_word_by_word(self):
		search_q = build('quick', 'transtorno espectro au*')

		self.assertEqual(query_of(search_q)['bool']['must'], [
			{'match': {'term_string': 'transtorno'}},
			{'match': {'term_string': 'espectro'}},
			{'wildcard': {'term_string': 'au*'}},
		])

	def test_without_a_language_spanish_from_spain_is_excluded(self):
		search_q = build('quick', 'abdomen', lang_code=None)

		self.assertEqual(query_of(search_q)['bool']['must_not'], MUST_NOT_ES_ES)

	def test_with_a_language_nothing_is_excluded(self):
		search_q = build('quick', 'abdomen')

		self.assertNotIn('must_not', query_of(search_q)['bool'])


class Prefix103Test(SimpleTestCase):
	"""103 is the quickterm "top 2 most relevant" phase and has its own shape."""

	def test_plain_text_is_a_phrase_query_with_prefix_and_exact_boosts(self):
		search_q = build('103', 'sindrome respiratoria')

		self.assertEqual(search_q['index'], TERM_INDEXES)
		self.assertEqual(query_of(search_q), {
			'bool': {
				'must': [{'match_phrase': {'term_string': {'query': 'sindrome respiratoria', 'slop': 1}}}],
				'should': [
					{'match_phrase_prefix': {'term_string': {'query': 'sindrome respiratoria', 'boost': 2}}},
					{'term': {'term_string.raw': {'value': 'sindrome respiratoria', 'boost': 5}}},
				],
				'filter': FILTER_GRAL,
			}
		})

	def test_wildcard_text_is_searched_word_by_word_not_as_a_full_field_wildcard(self):
		search_q = build('103', 'transtorno espectro au*')

		self.assertEqual(query_of(search_q), {
			'bool': {
				'must': [
					{'match': {'term_string': 'transtorno'}},
					{'match': {'term_string': 'espectro'}},
					{'wildcard': {'term_string': 'au*'}},
				],
				'filter': FILTER_GRAL,
			}
		})

	def test_without_a_language_both_branches_exclude_spanish_from_spain(self):
		plain = build('103', 'abdomen', lang_code=None)
		wildcard = build('103', 'abdom*', lang_code=None)

		self.assertEqual(query_of(plain)['bool']['must_not'], MUST_NOT_ES_ES)
		self.assertEqual(query_of(wildcard)['bool']['must_not'], MUST_NOT_ES_ES)


class FullFieldPrefixTest(SimpleTestCase):
	"""1## — whole field search."""

	def test_101_searches_the_full_field_filtered_to_preferred_terms(self):
		search_q = build('101', 'Abdomen, Acute')

		self.assertEqual(search_q['index'], TERM_INDEXES)
		self.assertEqual(query_of(search_q), {
			'bool': {
				'must': [{'match': {'term_string.full_field': 'Abdomen, Acute'}}],
				'filter': FILTER_PREFERRED,
			}
		})

	def test_102_searches_the_full_field_filtered_to_synonyms(self):
		search_q = build('102', 'Acute Abdomen')

		self.assertEqual(query_of(search_q)['bool']['filter'], FILTER_SYNONYM)

	def test_a_wildcard_turns_the_full_field_match_into_a_wildcard(self):
		search_q = build('101', 'Abdom*')

		self.assertEqual(query_of(search_q)['bool']['must'], [{'wildcard': {'term_string.full_field': 'Abdom*'}}])

	def test_104_searches_only_the_historical_index(self):
		search_q = build('104', 'Abdomen')

		self.assertEqual(search_q['index'], PREVIOUS_INDEXES)
		self.assertEqual(query_of(search_q)['bool']['filter'], FILTER_GRAL)

	def test_107_searches_preferred_synonym_and_historical_indexes(self):
		search_q = build('107', 'Abdomen')

		self.assertEqual(search_q['index'], ALL_TERM_INDEXES)
		self.assertEqual(query_of(search_q)['bool']['filter'], FILTER_GRAL)


class WordByWordPrefixTest(SimpleTestCase):
	"""4## — word by word search, one indexed word at a time."""

	def test_401_matches_a_single_word_with_the_keyword_analyzer(self):
		search_q = build('401', 'Supply')

		self.assertEqual(search_q['index'], TERM_INDEXES)
		self.assertEqual(query_of(search_q), {
			'bool': {
				'must': [{'match': {'term_string': {'query': 'Supply', 'analyzer': 'keyword_asciifolding'}}}],
				'filter': FILTER_PREFERRED,
			}
		})

	def test_402_filters_to_synonyms(self):
		search_q = build('402', 'Supply')

		self.assertEqual(query_of(search_q)['bool']['filter'], FILTER_SYNONYM)

	def test_403_filters_to_preferred_and_synonyms_together(self):
		search_q = build('403', 'Supply')

		self.assertEqual(query_of(search_q)['bool']['filter'], FILTER_GRAL)

	def test_more_than_one_word_matches_nothing(self):
		# the 4## indexes hold one word per document, so a phrase can never match
		search_q = build('401', 'Water Supply')

		self.assertEqual(query_of(search_q)['bool']['must'], [{'match_none': {}}])

	def test_404_searches_only_the_historical_index(self):
		search_q = build('404', 'Supply')

		self.assertEqual(search_q['index'], PREVIOUS_INDEXES)

	def test_407_searches_all_three_indexes(self):
		search_q = build('407', 'Supply')

		self.assertEqual(search_q['index'], ALL_TERM_INDEXES)


class CombinedPrefixTest(SimpleTestCase):
	"""105/106/405/406 need two independent searches, so they return a prefix pair."""

	def test_105_expands_to_preferred_plus_historical(self):
		self.assertEqual(build('105', 'Abdomen'), ['101', '104'])

	def test_106_expands_to_synonym_plus_historical(self):
		self.assertEqual(build('106', 'Abdomen'), ['102', '104'])

	def test_405_expands_to_preferred_plus_historical_word_by_word(self):
		self.assertEqual(build('405', 'Abdomen'), ['401', '404'])

	def test_406_expands_to_synonym_plus_historical_word_by_word(self):
		self.assertEqual(build('406', 'Abdomen'), ['402', '404'])


class TreeIdOptionTest(SimpleTestCase):

	def test_tree_id_searches_the_tree_number_indexes(self):
		search_q = build('tree_id', 'C01.001')

		self.assertEqual(search_q['index'], ['descriptor_treenumber', 'qualifier_treenumber'])
		self.assertEqual(query_of(search_q), {
			'bool': {
				'filter': [
					{'term': {'tree_number': 'C01.001'}},
					{'match': {'identifier.thesaurus_id': THS}},
				]
			}
		})


class InvalidPrefixTest(SimpleTestCase):

	def test_an_unknown_prefix_matches_nothing(self):
		search_q = build('999', 'Abdomen')

		self.assertEqual(search_q['index'], ['descriptor_term'])
		self.assertEqual(query_of(search_q), {'match_none': {}})


class TruncatedWordMustTest(SimpleTestCase):

	def test_wildcard_words_become_wildcards_and_the_rest_exact_matches(self):
		self.assertEqual([q.to_dict() for q in truncated_word_must('agua pot* rural')], [
			{'match': {'term_string': 'agua'}},
			{'wildcard': {'term_string': 'pot*'}},
			{'match': {'term_string': 'rural'}},
		])

	def test_a_single_word_gives_a_single_clause(self):
		self.assertEqual(len(truncated_word_must('abdom*')), 1)

	def test_empty_text_gives_no_clauses(self):
		self.assertEqual(truncated_word_must(''), [])
