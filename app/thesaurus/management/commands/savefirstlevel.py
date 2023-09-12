from django.db.models.functions import Length, Substr
from django.core.management.base import BaseCommand, CommandError
from thesaurus.models_qualifiers import *
from thesaurus.models_descriptors import *
from thesaurus.models_full import FirstLevel
import time

class Command(BaseCommand):
	help = "Save first level categories and their descendats to thesaurus_firstlevel Model"

	def handle(self, *args, **options):

		# If FirstLevel has information delete all and recalculate
		if FirstLevel.objects.count():
			FirstLevel.objects.all().delete()

		start = time.time()

		first_level = [
			{
				'treeNumber': 'A',
				'type': 'Descriptor',
				'thesaurus': [1],
				'decs_code': "59596",
				'self_term': {
					'label': [
						{"@value": "ANATOMY", "@language": "en", "status": 1},
						{"@value": "ANATOMÍA", "@language": "es", "status": 1},
						{"@value": "ANATOMIA", "@language": "pt-br", "status": 1},
						{"@value": "ANATOMIE", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "A"}
				}
			},
			{
				'treeNumber': 'B',
				'type': 'Descriptor',
				'thesaurus': [1, 2],
				'decs_code': "59597",
				'self_term': {
					'label': [
						{"@value": "ORGANISMS", "@language": "en", "status": 1},
						{"@value": "ORGANISMOS", "@language": "es", "status": 1},
						{"@value": "ORGANISMOS", "@language": "pt-br", "status": 1},
						{"@value": "ORGANISMES", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "B"}
				}
			},
			{
				'treeNumber': 'C',
				'type': 'Descriptor',
				'thesaurus': [1, 2],
				'decs_code': "59598",
				'self_term': {
					'label': [
						{"@value": "DISEASES", "@language": "en", "status": 1},
						{"@value": "ENFERMEDADES", "@language": "es", "status": 1},
						{"@value": "DOENÇAS", "@language": "pt-br", "status": 1},
						{"@value": "MALADIES", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "C"}
				}
			},
			{
				'treeNumber': 'D',
				'type': 'Descriptor',
				'thesaurus': [1, 2],
				'decs_code': "59599",
				'self_term': {
					'label': [
						{"@value": "CHEMICALS AND DRUGS", "@language": "en", "status": 1},
						{"@value": "COMPUESTOS QUÍMICOS Y DROGAS", "@language": "es", "status": 1},
						{"@value": "COMPOSTOS QUÍMICOS E DROGAS", "@language": "pt-br", "status": 1},
						{"@value": "PRODUITS CHIMIQUES ET MÉDICAMENTS", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "D"}
				}
			},
			{
				'treeNumber': 'E',
				'type': 'Descriptor',
				'thesaurus': [1, 2],
				'decs_code': "59600",
				'self_term': {
					'label': [
						{"@value": "ANALYTICAL, DIAGNOSTIC AND THERAPEUTIC TECHNIQUES, AND EQUIPMENT", "@language": "en",
						 "status": 1},
						{"@value": "TÉCNICAS Y EQUIPOS ANALÍTICOS, DIAGNÓSTICOS Y TERAPÉUTICOS", "@language": "es", "status": 1},
						{"@value": "TÉCNICAS E EQUIPAMENTOS ANALÍTICOS, DIAGNÓSTICOS E TERAPÊUTICOS", "@language": "pt-br",
						 "status": 1},
						{"@value": "TECHNIQUES ET EQUIPEMENTS ANALYTIQUES, DIAGNOSTIQUES ET THERAPEUTIQUES", "@language": "fr",
						 "status": 1}
					],
					"attr": {"tree_id": "E"}
				}
			},
			{
				'treeNumber': 'F',
				'type': 'Descriptor',
				'thesaurus': [1, 2],
				'decs_code': "59601",
				'self_term': {
					'label': [
						{"@value": "PSYCHIATRY AND PSYCHOLOGY", "@language": "en",
						 "status": 1},
						{"@value": "PSIQUIATRÍA Y PSICOLOGÍA", "@language": "es", "status": 1},
						{"@value": "PSIQUIATRIA E PSICOLOGIA", "@language": "pt-br",
						 "status": 1},
						{"@value": "PSYCHIATRIE ET PSYCHOLOGIE", "@language": "fr",
						 "status": 1}
					],
					"attr": {"tree_id": "F"}
				}
			},
			{
				'treeNumber': 'G',
				'type': 'Descriptor',
				'thesaurus': [1, 2],
				'decs_code': "595602",
				'self_term': {
					'label': [
						{"@value": "PHENOMENA AND PROCESSES", "@language": "en", "status": 1},
						{"@value": "FENÓMENOS Y PROCESOS", "@language": "es", "status": 1},
						{"@value": "FENÔMENOS E PROCESSOS", "@language": "pt-br", "status": 1},
						{"@value": "PHÉNOMÈNES ET PROCESSUS", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "G"}
				}
			},
			{
				'treeNumber': 'H',
				'type': 'Descriptor',
				'thesaurus': [1, 2],
				'decs_code': "59603",
				'self_term': {
					'label': [
						{"@value": "DISCIPLINES AND OCCUPATIONS", "@language": "en", "status": 1},
						{"@value": "DISCIPLINAS Y OCUPACIONES", "@language": "es", "status": 1},
						{"@value": "DISCIPLINAS E OCUPAÇÕES", "@language": "pt-br", "status": 1},
						{"@value": "DISCIPLINES ET MÉTIERS", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "H"}
				}
			},
			{
				'treeNumber': 'HP',
				'type': 'Descriptor',
				'thesaurus': [1, 2],
				'decs_code': "59604",
				'self_term': {
					'label': [
						{"@value": "HOMEOPATHY", "@language": "en", "status": 1},
						{"@value": "HOMEOPATÍA", "@language": "es", "status": 1},
						{"@value": "HOMEOPATIA", "@language": "pt-br", "status": 1},
						{"@value": "HOMÉOPATHIE", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "HP"}
				}
			},
			{
				'treeNumber': 'I',
				'type': 'Descriptor',
				'thesaurus': [1, 2],
				'decs_code': "59605",
				'self_term': {
					'label': [
						{"@value": "ANTHROPOLOGY, EDUCATION, SOCIOLOGY, AND SOCIAL PHENOMENA", "@language": "en", "status": 1},
						{"@value": "ANTROPOLOGÍA, EDUCACIÓN, SOCIOLOGÍA Y FENÓMENOS SOCIALES", "@language": "es", "status": 1},
						{"@value": "ANTROPOLOGIA, EDUCAÇÃO, SOCIOLOGIA E FENÔMENOS SOCIAIS", "@language": "pt-br", "status": 1},
						{"@value": "ANTHROPOLOGIE, ÉDUCATION, SOCIOLOGIE ET PHÉNOMÈNES SOCIAUX", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "I"}
				}
			},
			{
				'treeNumber': 'J',
				'type': 'Descriptor',
				'thesaurus': [1, 2],
				'decs_code': "59606",
				'self_term': {
					'label': [
						{"@value": "ATECHNOLOGY, INDUSTRY, AND AGRICULTURE", "@language": "en", "status": 1},
						{"@value": "TECNOLOGÍA, INDUSTRIA Y AGRICULTURA", "@language": "es", "status": 1},
						{"@value": "TECNOLOGIA, INDÚSTRIA E AGRICULTURA", "@language": "pt-br", "status": 1},
						{"@value": "ATECHNOLOGIE, INDUSTRIE ET AGRICULTURE", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "J"}
				}
			},
			{
				'treeNumber': 'K',
				'type': 'Descriptor',
				'thesaurus': [1, 2],
				'decs_code': "59607",
				'self_term': {
					'label': [
						{"@value": "HUMANITIES", "@language": "en", "status": 1},
						{"@value": "HUMANIDADES", "@language": "es", "status": 1},
						{"@value": "CIÊNCIAS HUMANAS", "@language": "pt-br", "status": 1},
						{"@value": "HUMANITÉS", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "K"}
				}
			},
			{
				'treeNumber': 'L',
				'type': 'Descriptor',
				'thesaurus': [1, 2],
				'decs_code': "59608",
				'self_term': {
					'label': [
						{"@value": "INFORMATION SCIENCE", "@language": "en", "status": 1},
						{"@value": "CIENCIA DE LA INFORMACIÓN", "@language": "es", "status": 1},
						{"@value": "CIÊNCIA DA INFORMAÇÃO", "@language": "pt-br", "status": 1},
						{"@value": "SCIENCE DE L'INFORMATION", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "L"}
				}
			},
			{
				'treeNumber': 'M',
				'type': 'Descriptor',
				'thesaurus': [1, 2],
				'decs_code': "59609",
				'self_term': {
					'label': [
						{"@value": "NAMED GROUPS", "@language": "en", "status": 1},
						{"@value": "DENOMINACIONES DE GRUPOS", "@language": "es", "status": 1},
						{"@value": "DENOMINAÇÕES DE GRUPOS", "@language": "pt-br", "status": 1},
						{"@value": "GROUPES NOMMÉS", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "M"}
				}
			},
			{
				'treeNumber': 'N',
				'type': 'Descriptor',
				'thesaurus': [1, 2],
				'decs_code': "59610",
				'self_term': {
					'label': [
						{"@value": "HEALTH CARE", "@language": "en", "status": 1},
						{"@value": "ATENCIÓN DE SALUD", "@language": "es", "status": 1},
						{"@value": "ASSISTÊNCIA À SAÚDE", "@language": "pt-br", "status": 1},
						{"@value": "SOINS DE SANTÉ", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "N"}
				}
			},
			{
				'treeNumber': 'SH',
				'type': 'Descriptor',
				'thesaurus': [1, 2],
				'decs_code': "59611",
				'self_term': {
					'label': [
						{"@value": "SCIENCE AND HEALTH", "@language": "en", "status": 1},
						{"@value": "CIENCIA Y SALUD", "@language": "es", "status": 1},
						{"@value": "CIÊNCIA E SAÚDE", "@language": "pt-br", "status": 1},
						{"@value": "SCIENCE ET SANTÉ", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "SH"}
				}
			},
			{
				'treeNumber': 'SP',
				'type': 'Descriptor',
				'thesaurus': [1, 2],
				'decs_code': "59612",
				'self_term': {
					'label': [
						{"@value": "PUBLIC HEALTH", "@language": "en", "status": 1},
						{"@value": "SALUD PÚBLICA", "@language": "es", "status": 1},
						{"@value": "SAÚDE PÚBLICA", "@language": "pt-br", "status": 1},
						{"@value": "SANTÉ PUBLIQUE", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "SP"}
				}
			},
			{
				'treeNumber': 'V',
				'type': 'Descriptor',
				'thesaurus': [1],
				'decs_code': "59613",
				'self_term': {
					'label': [
						{"@value": "PUBLICATION CHARACTERISTICS", "@language": "en", "status": 1},
						{"@value": "CARACTERÍSTICAS DE PUBLICACIONES", "@language": "es", "status": 1},
						{"@value": "CARACTERÍSTICAS DE PUBLICAÇÕES", "@language": "pt-br", "status": 1},
						{"@value": "CARACTÉRISTIQUES DE PUBLICATION", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "V"}
				}
			},
			{
				'treeNumber': 'VS',
				'type': 'Descriptor',
				'thesaurus': [1, 2],
				'decs_code': "59614",
				'self_term': {
					'label': [
						{"@value": "SURVEILLANCE IN PUBLIC HEALTH", "@language": "en", "status": 1},
						{"@value": "VIGILANCIA DE LA SALUD", "@language": "es", "status": 1},
						{"@value": "VIGILÂNCIA EM SAÚDE", "@language": "pt-br", "status": 1},
						{"@value": "SURVEILLANCE DE LA SANTÉ PUBLIQUE", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "VS"}
				}
			},
			{
				'treeNumber': 'Z',
				'type': 'Descriptor',
				'thesaurus': [1, 2],
				'decs_code': "59615",
				'self_term': {
					'label': [
						{"@value": "GEOGRAPHICALS", "@language": "en", "status": 1},
						{"@value": "DENOMINACIONES GEOGRÁFICAS", "@language": "es", "status": 1},
						{"@value": "DENOMINAÇÕES GEOGRÁFICAS", "@language": "pt-br", "status": 1},
						{"@value": "GÉOGRAPHIQUES", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "Z"}
				}
			},
			{
				'treeNumber': 'Q',
				'type': 'Qualifier',
				'thesaurus': [1, 2],
				'decs_code': "59616",
				'self_term': {
					'label': [
						{"@value": "Other Qualifiers", "@language": "en", "status": 1},
						{"@value": "Otros Calificadores", "@language": "es", "status": 1},
						{"@value": "Outros qualificadores", "@language": "pt-br", "status": 1},
						{"@value": "Autres qualifications", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "Q"}
				}
			},
			{
				'treeNumber': 'Y',
				'type': 'Qualifier',
				'thesaurus': [1, 2],
				'decs_code': "59616",
				'self_term': {
					'label': [
						{"@value": "Other Qualifiers", "@language": "en", "status": 1},
						{"@value": "Otros Calificadores", "@language": "es", "status": 1},
						{"@value": "Outros qualificadores", "@language": "pt-br", "status": 1},
						{"@value": "Autres qualifications", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "Y"}
				}
			},
			{
				'treeNumber': 'MT',
				'type': 'Descriptor',
				'thesaurus': [1],
				'decs_code': "",
				'self_term': {
					'label': [
						{"@value": "TRADITIONAL, COMPLEMENTARY AND INTEGRATIVE MEDICINE", "@language": "en", "status": 1},
						{"@value": "MEDICINAS TRADICIONALES, COMPLEMENTARIAS E INTEGRATIVAS", "@language": "es", "status": 1},
						{"@value": "MEDICINAS TRADICIONAIS, COMPLEMENTARES E INTEGRATIVAS", "@language": "pt-br", "status": 1},
						{"@value": "MÉDECINE TRADITIONNELLE, COMPLÉMENTAIRE ET INTÉGRATIVE", "@language": "fr", "status": 1}
					],
					"attr": {"tree_id": "MT"}
				}
			},
		]
		exclude = {'H': 'HP', 'M': 'MT', 'V': 'VS'}
		for category in first_level:
			if category['type'] == 'Descriptor':
				TreeNumbersList = TreeNumbersListDesc
				TermList = TermListDesc
			else:
				TreeNumbersList = TreeNumbersListQualif
				TermList = TermListQualif

			# Una misma categoria tiene diferentes hijos en diferentes thesaurus
			for ths in category['thesaurus']:
				if category['treeNumber'] in ['H', 'M', 'V']:
					descendant_list = list(
						TreeNumbersList.objects.annotate(tree_number_tam=Length('tree_number')).filter(
							tree_number__startswith=category['treeNumber'],
							tree_number_tam=3,
							identifier__thesaurus=ths,
						).exclude(
							tree_number__startswith=exclude[category['treeNumber']]
						).order_by('tree_number').values('identifier_id', 'tree_number'))

					with_descendant = list(TreeNumbersList.objects.annotate(
						descendant=Substr('tree_number', 1, 3), tree_number_tam=Length('tree_number')
					).filter(
						tree_number__startswith=category['treeNumber'],
						tree_number_tam__gt=3,
						identifier__thesaurus=ths,
					).exclude(
						tree_number__startswith=exclude[category['treeNumber']]
					).order_by('tree_number').values('descendant'))

				else:
					descendant_list = list(
						TreeNumbersList.objects.annotate(tree_number_tam=Length('tree_number')).filter(
							tree_number__startswith=category['treeNumber'],
							tree_number_tam=3,
							identifier__thesaurus=ths,
						).order_by('tree_number').values('identifier_id', 'tree_number'))

					with_descendant = list(TreeNumbersList.objects.annotate(
						descendant=Substr('tree_number', 1, 3), tree_number_tam=Length('tree_number')).filter(
						tree_number__startswith=category['treeNumber'],
						tree_number_tam__gt=3,
						identifier__thesaurus=ths,
					).order_by('tree_number').values('descendant'))

				descendant_term_list = []
				for descendant_ids in descendant_list:
					descendant_terms = TermList.objects.filter(
						identifier_concept__identifier=descendant_ids['identifier_id'],
						record_preferred_term='Y',
						concept_preferred_term='Y')

					descendant_label = []
					for descendant_term in descendant_terms:
						term_text = descendant_term.term_string
						if category['type'] == 'Qualifier':
							term_text = "/" + term_text

						descendant_label.append(
							{'@value': term_text, '@language': descendant_term.language_code, 'status': descendant_term.status})

					term = {
						'label': descendant_label,
						'attr': {'tree_id': descendant_ids['tree_number']}}

					if {'descendant': descendant_ids['tree_number']} not in with_descendant:
						term['attr']['leaf'] = "true"

					descendant_term_list.append(term)

				if not descendant_term_list:
					descendant_term_list = None

				first_level_category = FirstLevel(
					treeNumber=category['treeNumber'],
					type=category['type'],
					thesaurus=ths,
					self_term=category['self_term'],
					descendant=descendant_term_list
				)
				first_level_category.save()
				self.stdout.write('Successfully saved "%s" Category, thesaurus "%s"' % (category['treeNumber'], ths))

		exec_time = time.time() - start
		self.stdout.write('Execution time "%s"' % time.strftime("%H:%M:%S",time.gmtime(exec_time)))
