from django.core.management.base import BaseCommand
from django.core.management import call_command
import time


class Command(BaseCommand):
	help = "Create and populate indexes in ElasticSearch for hierarchical and textual searches"

	def handle(self, *args, **options):

		self.stdout.write('Create and populate indexes in ElasticSearch for hierarchical and textual searches.')

		# '-rebuild' Delete the indices and then recreate and populate them
		# '-f' Force operations without asking
		self.stdout.write('Indexing Qualifiers')
		call_command('search_index', '--rebuild', '-f', '--models', 'thesaurus.TermListQualif')

