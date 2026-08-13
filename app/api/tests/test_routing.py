# -*- coding: utf-8 -*-
"""Layer 2 — the routes themselves: what the API exposes and what it refuses."""

from api.tests.support import EndpointTestCase


class ApiIndexTest(EndpointTestCase):

	def test_the_index_lists_both_resources(self):
		response = self.client.get('/api/thesaurus/', HTTP_ACCEPT='application/json')
		payload = self.json(response)

		self.assertEqual(sorted(payload), ['quickterm', 'term'])
		self.assertEqual(payload['term']['list_endpoint'], '/api/thesaurus/term/')
		self.assertEqual(payload['quickterm']['list_endpoint'], '/api/thesaurus/quickterm/')


class SchemaTest(EndpointTestCase):
	"""Characterization: tastypie's built-in schema view is broken here.

	build_schema() calls get_object_list(request), but both resources declare
	get_object_list(self, bundle) and read bundle.request, so the view raises
	AttributeError and the client gets a 500.
	"""

	def setUp(self):
		super().setUp()
		self.allow_server_error()

	def test_the_term_schema_returns_500(self):
		response = self.client.get('/api/thesaurus/term/schema/', HTTP_ACCEPT='application/json')

		self.assertEqual(response.status_code, 500)

	def test_the_quickterm_schema_returns_500(self):
		response = self.client.get('/api/thesaurus/quickterm/schema/', HTTP_ACCEPT='application/json')

		self.assertEqual(response.status_code, 500)


class AllowedMethodTest(EndpointTestCase):

	def assertNotAllowed(self, method, url):
		response = getattr(self.client, method)(url, data={}, content_type='application/json')

		self.assertEqual(response.status_code, 405)

	def test_the_term_resource_is_read_only(self):
		for method in ('post', 'put', 'delete', 'patch'):
			with self.subTest(method=method):
				self.assertNotAllowed(method, '/api/thesaurus/term/')

	def test_the_quickterm_resource_is_read_only(self):
		for method in ('post', 'put', 'delete', 'patch'):
			with self.subTest(method=method):
				self.assertNotAllowed(method, '/api/thesaurus/quickterm/')


class FormatNegotiationTest(EndpointTestCase):
	"""Both resources default to XML, unlike tastypie's own default of JSON."""

	def test_term_defaults_to_xml(self):
		self.assertContentType(self.get_term(words='musculos'), 'application/xml')

	def test_quickterm_defaults_to_xml(self):
		self.assertContentType(self.get_quickterm(query='musculos'), 'application/xml')

	def test_the_format_parameter_wins_over_the_default(self):
		self.assertContentType(self.get_term(words='musculos', format='json'), 'application/json')
		self.assertContentType(self.get_quickterm(query='musculos', format='json'), 'application/json')

	def test_an_unsupported_format_falls_back_to_xml(self):
		response = self.get_term(words='musculos', format='yaml')

		self.assertEqual(response.status_code, 200)
		self.assertContentType(response, 'application/xml')
