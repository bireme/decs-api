# -*- coding: utf-8 -*-
"""Layer 3 — the running stack, with real MySQL and a real Elasticsearch index.

Skipped unless DECS_TEST_ES=1. Unlike layers 1 and 2, these tests drive the API
over HTTP rather than through the Django test client: the point is to exercise
the deployed application, its database and its index together, exactly as a
client would. `make dev_test_live` starts the server and points DECS_TEST_URL at it.

The expectations are pinned to real DeCS records that have been stable for
years. If one of them is edited in the thesaurus, the pinned value here is what
needs updating — the assertion failure names the record.

With DECS_TEST_PARITY=1 each response is additionally compared, structurally,
against the same query on production, and the first differing path is reported.
"""

import os
import unittest
import urllib.parse
import urllib.request

from lxml import etree

LIVE = os.environ.get('DECS_TEST_ES') == '1'
PARITY = os.environ.get('DECS_TEST_PARITY') == '1'

BASE_URL = os.environ.get('DECS_TEST_URL', 'http://localhost:8000')
PRODUCTION_URL = os.environ.get('DECS_TEST_PARITY_URL', 'https://decs-api.bvsalud.org')

TIMEOUT = int(os.environ.get('DECS_TEST_TIMEOUT', 60))

# the production proxy rejects the default `Python-urllib/x.y` agent
USER_AGENT = os.environ.get('DECS_TEST_USER_AGENT', 'decs-api-tests/1.0')

# attributes that legitimately differ between two runs of the same query
VOLATILE_ATTRIBUTES = {'date'}

# pinned records — decs_code (mfn) and the values the API renders for them
MUSCLES = {'mfn': '9324', 'tree_id': 'A02.633', 'pt': 'Músculos', 'en': 'Muscles', 'nlm': 'D009132'}
POISONING = {'mfn': '22025', 'tree_id': 'Q45.020.010', 'pt': '/intoxicação', 'nlm': 'Q000506'}


def fetch(base_url, path, params):
	url = '%s%s?%s' % (base_url, path, urllib.parse.urlencode(params))
	request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
	with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
		return response.read()


def normalize(text):
	return ' '.join((text or '').split())


def first_difference(left, right, path='/'):
	"""Return the path of the first structural difference, or None if equal."""
	here = path + left.tag

	if left.tag != right.tag:
		return '%s (tag: %s != %s)' % (path, left.tag, right.tag)

	for name, value in left.attrib.items():
		if name in VOLATILE_ATTRIBUTES:
			continue
		if right.get(name) != value:
			return '%s/@%s (%r != %r)' % (here, name, value, right.get(name))

	missing = set(right.attrib) - set(left.attrib) - VOLATILE_ATTRIBUTES
	if missing:
		return '%s/@%s (missing on the left)' % (here, sorted(missing)[0])

	if normalize(left.text) != normalize(right.text):
		return '%s/text() (%r != %r)' % (here, normalize(left.text), normalize(right.text))

	left_children, right_children = list(left), list(right)
	if len(left_children) != len(right_children):
		return '%s (%d children != %d)' % (here, len(left_children), len(right_children))

	for index, (left_child, right_child) in enumerate(zip(left_children, right_children)):
		difference = first_difference(left_child, right_child, '%s[%d]/' % (here, index))
		if difference:
			return difference

	return None


@unittest.skipUnless(LIVE, "set DECS_TEST_ES=1 to run against a live stack")
class LiveTestCase(unittest.TestCase):

	def get(self, path, **params):
		content = fetch(BASE_URL, path, params)
		root = etree.fromstring(content)

		if PARITY:
			self.assertMatchesProduction(root, path, params)

		return root

	def assertMatchesProduction(self, root, path, params):
		production = etree.fromstring(fetch(PRODUCTION_URL, path, params))
		difference = first_difference(root, production)

		self.assertIsNone(difference, "differs from production at %s for %s %s" % (difference, path, params))


class LiveTermTest(LiveTestCase):

	def test_a_words_search_returns_the_pinned_record(self):
		root = self.get('/api/thesaurus/term/', words='Músculos')

		self.assertIn(MUSCLES['mfn'], root.xpath('//record/@mfn'))
		self.assertIn(MUSCLES['nlm'], root.xpath('//unique_identifier_nlm/text()'))

	def test_a_words_search_in_english_returns_the_english_labels(self):
		root = self.get('/api/thesaurus/term/', words='Muscles', lang='en')

		self.assertIn(MUSCLES['en'], root.xpath('//descriptor[@lang="en"]/text()'))

	def test_a_bool_search_resolves_the_expression(self):
		root = self.get('/api/thesaurus/term/', **{'bool': '101 Músculos'})

		self.assertIn(MUSCLES['mfn'], root.xpath('//record/@mfn'))

	def test_a_tree_id_search_returns_the_record_and_its_neighbourhood(self):
		root = self.get('/api/thesaurus/term/', tree_id=MUSCLES['tree_id'])

		self.assertEqual(root.xpath('//decsws_response/@tree_id'), [MUSCLES['tree_id']])
		self.assertEqual(root.xpath('//tree/self/term_list/term/text()'), [MUSCLES['pt']])
		self.assertTrue(root.xpath('//tree/descendants/term_list/term'))

	def test_the_first_level_categories_are_browsable(self):
		root = self.get('/api/thesaurus/term/', tree_id='')

		self.assertEqual(root.xpath('//tree/term_list/term/@tree_id')[0], 'A')
		self.assertGreater(len(root.xpath('//tree/term_list/term')), 15)

	def test_a_second_level_category_lists_its_descendants(self):
		root = self.get('/api/thesaurus/term/', tree_id='A')

		self.assertIn('A02', root.xpath('//tree/descendants/term_list/term/@tree_id'))

	def test_a_qualifier_is_rendered_with_its_slash_prefix(self):
		root = self.get('/api/thesaurus/term/', tree_id=POISONING['tree_id'])

		self.assertEqual(root.xpath('//record/@mfn'), [POISONING['mfn']])
		self.assertEqual(root.xpath('//tree/self/term_list/term/text()'), [POISONING['pt']])


class LiveQuickTermTest(LiveTestCase):

	def test_a_quick_search_returns_matching_terms(self):
		root = self.get('/api/thesaurus/quickterm/', query='sindrome pe*')

		self.assertTrue(root.xpath('//item'))
		self.assertTrue(all(item.get('id') for item in root.xpath('//item')))

	def test_the_exact_term_is_among_the_first_results(self):
		root = self.get('/api/thesaurus/quickterm/', query='Músculos')

		self.assertIn(MUSCLES['pt'], root.xpath('//item/@term')[:2])

	def test_count_limits_the_number_of_items(self):
		root = self.get('/api/thesaurus/quickterm/', query='mus', count='5')

		self.assertLessEqual(len(root.xpath('//item')), 5)

	def test_a_truncated_multi_word_query_still_matches(self):
		# the plan 002 bug, against the real index: the words are not contiguous
		root = self.get('/api/thesaurus/quickterm/', query='transtorno espectro au*')

		self.assertTrue(root.xpath('//item'), "no match for a non-contiguous truncated query")

	def test_a_truncated_query_is_ordered_deterministically(self):
		# the plan 001 bug: two identical requests must agree on the top results
		first = self.get('/api/thesaurus/quickterm/', query='muscul*')
		second = self.get('/api/thesaurus/quickterm/', query='muscul*')

		self.assertEqual(first.xpath('//item/@term')[:2], second.xpath('//item/@term')[:2])
