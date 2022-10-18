from django.core.management.base import BaseCommand
from django.core.management import call_command
import time


class Command(BaseCommand):
	help = "Save all auxilliar data: First Level categories, full record and hierarchical information of Descriptors and Qualifiers"

	def handle(self, *args, **options):

		self.stdout.write('This command saves all auxiliar data: First Level categories, full record and hierarchical information of Descriptors and Qualifiers. It takes more than one hour.')

		self.stdout.write('Saving First Level Categories')
		call_command('savefirstlevel')

		self.stdout.write('Saving Qualifiers')
		call_command('savequalifier')

		self.stdout.write('Saving Tree Qualifiers')
		call_command('savetree', 'Q')

		self.stdout.write('Saving Descriptors. It takes more than one hour.')
		call_command('savedescriptor')

		self.stdout.write('Saving Tree Descriptors. It takes more than one hour.')
		call_command('savetree', 'D')
