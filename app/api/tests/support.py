# -*- coding: utf-8 -*-
"""Shared machinery for the endpoint tests (layer 2).

Elasticsearch is replaced at its two seams — execute_simple_search() and
execute_quick_search() — so everything downstream of the search is the real
thing: the real URLconf, the real tastypie resource, the real dehydrate() and
the real serializer, running against the fixture records in a test database.

The fakes record the search they were handed, which lets a test assert both the
rendered response and the query that would have reached the cluster.
"""

import json

from unittest import mock

from django.test import TestCase
from lxml import etree

from api import thesaurus_term_api

# --- the fixture records, by the values the tests assert on ----------------
# regenerate with `make dev_dump_test_fixtures`; see scripts/dump_test_fixtures.py

MUSCLES = {
	'identifier': 10673,
	'decs_code': '9324',
	'nlm': 'D009132',
	'tree_numbers': ['A02.633', 'A10.690'],
	'pt': 'Músculos',
	'en': 'Muscles',
	'es': 'Músculos',
}

SEROTONIN = {
	'identifier': 14096,
	'decs_code': '24311',
	'nlm': 'D012701',
	'tree_numbers': ['D02.092.211.215.801.852', 'D03.633.100.473.914.814', 'D23.469.050.650'],
	'pt': 'Serotonina',
	'en': 'Serotonin',
}

POISONING = {
	'identifier': 53,
	'decs_code': '22025',
	'nlm': 'Q000506',
	'tree_numbers': ['Q45.020.010', 'Q60.040', 'Y07.020.010', 'Y10.040'],
	'pt': 'intoxicação',
	'en': 'poisoning',
}


def term_hit(record, term_type='descriptor'):
	"""What execute_simple_search() returns for one record."""
	return {'identifier': record['identifier'], 'term_type': term_type}


def quick_hit(record, term_string=None, term_type='descriptor'):
	"""What execute_quick_search() returns for one record."""
	return {
		'identifier': record['identifier'],
		'term_type': term_type,
		'term_string': term_string if term_string is not None else record['pt'],
	}


class FakeElasticsearch(object):
	"""Stand-in for the two search functions, recording every call."""

	def __init__(self):
		self.simple_results = []
		self.simple_queue = []
		self.quick_results = []
		self.simple_calls = []
		self.quick_calls = []

	def queue_simple(self, *results):
		"""Answer consecutive searches differently, as a bool expression needs."""
		self.simple_queue = [list(result) for result in results]

	def execute_simple_search(self, search_q):
		self.simple_calls.append(search_q)

		if self.simple_queue:
			return self.simple_queue.pop(0)
		return list(self.simple_results)

	def execute_quick_search(self, search_q, sort=None, top_sorted=False):
		self.quick_calls.append({'search_q': search_q, 'sort': sort, 'top_sorted': top_sorted})

		# quickterm searches twice: the top 2 exact matches, then the
		# alphabetical list. Hand back one queued list per call.
		if self.quick_results:
			return list(self.quick_results.pop(0))
		return []

	# --- assertions on what reached the cluster ---------------------------

	def last_simple_query(self):
		return self.simple_calls[-1]['query'].to_dict()

	def quick_query(self, index):
		return self.quick_calls[index]['search_q']['query'].to_dict()


class EndpointTestCase(TestCase):
	"""Base case: fixture records loaded, Elasticsearch faked."""

	fixtures = ['decs_sample.json']

	def setUp(self):
		self.es = FakeElasticsearch()

		for target in (
			# patched where the name is bound: both API modules do
			# `from api.esearch_functions import *`
			'api.thesaurus_term_api.execute_simple_search',
			'api.thesaurus_quickterm_api.execute_simple_search',
			# and once more at its definition, because a bool= query is executed
			# by complex_search(), which looks the name up in its own module
			'api.esearch_functions.execute_simple_search',
		):
			patcher = mock.patch(target, side_effect=self.es.execute_simple_search)
			patcher.start()
			self.addCleanup(patcher.stop)

		patcher = mock.patch(
			'api.thesaurus_quickterm_api.execute_quick_search', side_effect=self.es.execute_quick_search
		)
		patcher.start()
		self.addCleanup(patcher.stop)

		# the language list is cached across tests, and the fixture is the
		# only database the endpoints should see
		thesaurus_term_api.get_decs_languages.cache_clear()
		self.addCleanup(thesaurus_term_api.get_decs_languages.cache_clear)

	# --- request helpers --------------------------------------------------

	def get_term(self, **params):
		return self.client.get('/api/thesaurus/term/', params)

	def get_quickterm(self, **params):
		return self.client.get('/api/thesaurus/quickterm/', params)

	def allow_server_error(self):
		"""Let a request that raises come back as a 500 instead of re-raising.

		tastypie turns an unhandled exception into a 500 response, but it also
		fires got_request_exception, which makes the test client re-raise. The
		characterization tests want the response the client would receive.
		"""
		self.client.raise_request_exception = False

	def assertContentType(self, response, content_type):
		# Django appends "; charset=utf-8" to the resource's content type
		self.assertEqual(response['Content-Type'].split(';')[0], content_type)

	def xml(self, response):
		self.assertEqual(response.status_code, 200)
		self.assertContentType(response, 'application/xml')
		return etree.fromstring(response.content)

	def json(self, response):
		self.assertEqual(response.status_code, 200)
		self.assertContentType(response, 'application/json')
		return json.loads(response.content)

	# --- assertions on the rendered response ------------------------------

	def assertTexts(self, root, xpath, expected):
		self.assertEqual([element.text for element in root.xpath(xpath)], expected)

	def assertAttrs(self, root, xpath, attribute, expected):
		self.assertEqual([element.get(attribute) for element in root.xpath(xpath)], expected)
