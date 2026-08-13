# -*- coding: utf-8 -*-
"""Layer 1 — language resolution.

get_valid_lang() maps a requested language onto the pair (lang, lang_code) used
for filtering and for the lang attributes of the response. The set of known
languages comes from the database through the cached get_decs_languages().
"""

from unittest import mock

from django.test import SimpleTestCase

from api import thesaurus_term_api
from api.thesaurus_term_api import get_valid_lang

DECS_LANGUAGES = ['en', 'es', 'pt-br', 'es-es', 'fr']


class GetValidLangTest(SimpleTestCase):

	def setUp(self):
		patcher = mock.patch.object(thesaurus_term_api, 'get_decs_languages', return_value=DECS_LANGUAGES)
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_portuguese_maps_to_the_brazilian_language_code(self):
		self.assertEqual(get_valid_lang('pt'), ['pt', 'pt-br'])

	def test_english_maps_to_itself(self):
		self.assertEqual(get_valid_lang('en'), ['en', 'en'])

	def test_spanish_maps_to_itself(self):
		self.assertEqual(get_valid_lang('es'), ['es', 'es'])

	def test_only_the_first_two_characters_are_considered(self):
		self.assertEqual(get_valid_lang('pt-BR'), ['pt', 'pt-br'])
		self.assertEqual(get_valid_lang('es-AR'), ['es', 'es'])
		self.assertEqual(get_valid_lang('en-US'), ['en', 'en'])

	def test_an_unknown_language_falls_back_to_portuguese(self):
		self.assertEqual(get_valid_lang('zz'), ['pt', 'pt-br'])

	def test_an_empty_language_falls_back_to_portuguese(self):
		self.assertEqual(get_valid_lang(''), ['pt', 'pt-br'])


class DecsLanguagesCacheTest(SimpleTestCase):
	"""The language list is read from the database once and cached."""

	databases = {'default'}

	def setUp(self):
		thesaurus_term_api.get_decs_languages.cache_clear()
		self.addCleanup(thesaurus_term_api.get_decs_languages.cache_clear)

	def test_the_database_is_queried_only_on_the_first_call(self):
		with mock.patch.object(thesaurus_term_api.TermListDesc, 'objects') as objects:
			objects.distinct.return_value.values.return_value = [{'language_code': 'en'}]

			first = thesaurus_term_api.get_decs_languages()
			second = thesaurus_term_api.get_decs_languages()

		self.assertEqual(first, ['en'])
		self.assertEqual(second, ['en'])
		self.assertEqual(objects.distinct.call_count, 1)
