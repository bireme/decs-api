from django.db.models.functions import Length, Substr
from django.core.management.base import BaseCommand, CommandError
from thesaurus.models_descriptors import *
from thesaurus.models_full import TreeDescriptor, TreeQualifier, FirstLevel
from django.utils import timezone

import time


class Command(BaseCommand):
	help = 'Save full hierarchical information of Descriptors or Qualifiers to thesaurus_tree Model. ' \
	       'Enter type of tree number to save: "D" for Descriptor or "Q" for Qualifier. By default saves all TreeNumbers. Use --tree_number to save specific TreeNumber or ' \
	       '--from --total to save a range'

	def add_arguments(self, parser):
		parser.add_argument('type', help="Type of tree number to save 'D' for Descriptor or 'Q' for Qualifier")
		# parser.add_argument('--all', default=True, help='To save all Tree Numbers hierarchical information')
		parser.add_argument('--tree_number', help='The tree number of Descriptor to save the hierarchical information ')
		parser.add_argument('--total', type=int, help='Total of tree numbers to save')
		parser.add_argument('--from', type=int, default=1, help='Start id of tree numbers (default = 1)')

	def handle(self, *args, **options):
		start = time.time()

		if options['type'] == "D":
			TreeNumbersList = TreeNumbersListDesc
			TermList = TermListDesc
			IdentifierTable = IdentifierDesc
			FullTree = TreeDescriptor
			is_descriptor = True
		# opt_type = 'Descriptor'
		elif options['type'] == "Q":
			TreeNumbersList = TreeNumbersListQualif
			TermList = TermListQualif
			IdentifierTable = IdentifierQualif
			FullTree = TreeQualifier
			is_descriptor = False
		# opt_type = 'Qualifier'
		else:
			raise CommandError("Enter the correct type of tree number: 'D' for Descriptor or 'Q' for Qualifier")

		tree_numbers = TreeNumbersList.objects.all().order_by('id')

		for tree_number in tree_numbers:
			tree_id = tree_number.tree_number
			if len(tree_id) <= 3 and tree_id:
				identifier_obj = IdentifierTable.objects.get(pk=tree_number.identifier_id)
				ths = identifier_obj.thesaurus_id

				ancestor_term_list = []
				ancestors_tree_id = []

				parts = tree_id.split(".")
				# delete last
				parts.pop()

				# Ancestor only from first level categories  (ex: tree_number:A01 ancestor A)
				if not parts:
					category_id = get_category_id(tree_id)
					ancestors_tree_id.append(category_id)
				else:
					ancestor = ''
					for p in parts:
						if ancestor == '':
							ancestor = p
						else:
							ancestor = ancestor + '.' + p
						ancestors_tree_id.append(ancestor)

					# Obtener identifier _id para buscar term,
					# Hay q hacerlo en 2 pasos pq no se puede relacionar mas de 3 tablas
					ancestors_list = list(TreeNumbersList.objects.filter(
						tree_number__in=ancestors_tree_id,
						identifier__thesaurus=ths
					).order_by('tree_number').values('identifier_id', 'tree_number'))

				part1 = ""
				for tree_id_ancestor in ancestors_tree_id:
					if len(tree_id_ancestor) < 3:
						# llenar ancestor_label con category en todos los lang
						self.stdout.write('tree_id "%s", tree_id_ancestor "%s", thesaurus "%s"' % (tree_id, tree_id_ancestor, ths))
						try:
							category = FirstLevel.objects.get(treeNumber=tree_id_ancestor, thesaurus=ths)
							ancestor_term_list.append(category.self_term)
						except FirstLevel.DoesNotExist:
							self.stdout.write('tree_id_ancestor "%s", thesaurus "%s"' % (tree_id_ancestor, ths))
							raise CommandError('DoesNotExist tree_id_ancestor "%s", thesaurus "%s"' % (tree_id_ancestor, ths))


		exec_time = time.time() - start
		self.stdout.write('Execution time "%s"' % time.strftime("%H:%M:%S", time.gmtime(exec_time)))


def get_category_id(tree_number):
	if tree_number[1:2].isdigit():
		category_id = tree_number[0:1]
	else:
		category_id = tree_number[0:2]

	return category_id


"""
# Get tree info from TreeDescriptor or TreeQualifier
			if tree_number[0:1] not in ["Q", "Y"]:
				TreeFull = TreeDescriptor
			else:
				TreeFull = TreeQualifier

ancestor_term_list = []
for tree_id in tree_ids:
	tree_obj = TreeFull.objects.get(identifier_id=identifier_id, treeNumber=tree_id['tree_id'])
	if tree_id['tree_id'] == tree_number:
		# Self, sibling and descendant only for this tree_number
		full_tree = tree_obj

	for ancestor in tree_obj.ancestor:
		for label in ancestor['label']:
			if label['status'] == 1 and label['@language'] == lang_code:
				ancestor_term_list.append({'term': label['@value'], 'attr': ancestor['attr']})
				break

tree['ancestors'] = {'term_list': ancestor_term_list, 'attr': {'lang': lang}}

for label in full_tree.self_term['label']:
	if label['status'] == 1 and label['@language'] == lang_code:
		tree['self'] = {'term_list': {'term': label['@value'], 'attr': full_tree.self_term['attr']}, 'attr': {'lang': lang}}
		break

preceding_sibling = []
if full_tree.preceding_sibling:
	for preceding in full_tree.preceding_sibling:
		for label in preceding['label']:
			if label['status'] == 1 and label['@language'] == lang_code:
				preceding_sibling.append({'term': label['@value'], 'attr': preceding['attr']})

tree['preceding_sibling'] = {'term_list': preceding_sibling, 'attr': {'lang': lang}}

following_sibling = []
if full_tree.following_sibling:
	for following in full_tree.following_sibling:
		for label in following['label']:
			if label['status'] == 1 and label['@language'] == lang_code:
				following_sibling.append({'term': label['@value'], 'attr': following['attr']})

tree['following_sibling'] = {'term_list': following_sibling, 'attr': {'lang': lang}}

descendants = []
if full_tree.descendant:
	for one_descendant in full_tree.descendant:
		for label in one_descendant['label']:
			if label['status'] == 1 and label['@language'] == lang_code:
				descendants.append({'term': label['@value'], 'attr': one_descendant['attr']})

tree['descendants'] = {'term_list': descendants, 'attr': {'lang': lang}}
"""
