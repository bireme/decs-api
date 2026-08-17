#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare two DeCS API deployments, response by response, in XML and in JSON.

This is not part of the test suite. It asserts nothing about content — it only
answers one question: do two deployments answer the same request identically?
Point it at the test environment and production before a release.

    python scripts/parity_check.py --base-a https://decs-api.teste.bvsalud.org

Both formats are compared, because they are produced by different code: the XML
comes from the hand-written serializers in api/ws_decs_serializer.py, the JSON is
plain tastypie output of a differently shaped dict. A change can break one and
leave the other intact.

Strict by default: any structural difference fails. --relaxed tolerates result
ordering and result counts, for when the two indexes are knowingly out of sync.

Exits 0 if every comparison passed, 1 otherwise.
"""

import argparse
import difflib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from lxml import etree

BASE_A_DEFAULT = os.environ.get('DECS_TEST_URL', 'http://localhost:8000')
BASE_B_DEFAULT = os.environ.get('DECS_TEST_PARITY_URL', 'https://decs-api.bvsalud.org')

# the production proxy rejects the default `Python-urllib/x.y` agent
USER_AGENT = os.environ.get('DECS_TEST_USER_AGENT', 'decs-api-parity/1.0')

# attributes that legitimately differ between two runs of the same query
VOLATILE_ATTRIBUTES = {'date'}

# how the records of a result list are identified when order is ignored
RECORD_KEYS = ('mfn', 'id', 'tree_id')

MAX_DIFF_LINES = 40


# --- the request matrix ----------------------------------------------------
# (name, path, params). Seeded from the live tests and from the parameter
# combinations the endpoint tests cover but that never reach a deployment.

CASES = [
	('index', '/api/thesaurus/', {}),

	('term-words', '/api/thesaurus/term/', {'words': 'Músculos'}),
	('term-words-en', '/api/thesaurus/term/', {'words': 'Muscles', 'lang': 'en'}),
	('term-words-es', '/api/thesaurus/term/', {'words': 'Serotonina', 'lang': 'es'}),
	('term-words-wildcard', '/api/thesaurus/term/', {'words': 'muscul$'}),
	('term-words-lang-fallback', '/api/thesaurus/term/', {'words': 'Músculos', 'lang': 'zz'}),
	('term-words-ths', '/api/thesaurus/term/', {'words': 'Músculos', 'ths': '2'}),
	('term-words-status', '/api/thesaurus/term/', {'words': 'Músculos', 'status': '0'}),
	('term-bool', '/api/thesaurus/term/', {'bool': '101 Músculos'}),
	('term-bool-or', '/api/thesaurus/term/', {'bool': '101 Músculos OR 101 Serotonina'}),
	('term-bool-and', '/api/thesaurus/term/', {'bool': '101 Músculos AND 101 Serotonina'}),
	('term-tree-first-level', '/api/thesaurus/term/', {'tree_id': ''}),
	('term-tree-second-level', '/api/thesaurus/term/', {'tree_id': 'A'}),
	('term-tree-record', '/api/thesaurus/term/', {'tree_id': 'A02.633'}),
	('term-tree-qualifier', '/api/thesaurus/term/', {'tree_id': 'Q45.020.010'}),

	('quick-term', '/api/thesaurus/quickterm/', {'query': 'Músculos'}),
	('quick-term-en', '/api/thesaurus/quickterm/', {'query': 'musculos', 'lang': 'en'}),
	('quick-count', '/api/thesaurus/quickterm/', {'query': 'mus', 'count': '5'}),
	('quick-count-one', '/api/thesaurus/quickterm/', {'query': 'mus', 'count': '1'}),
	('quick-wildcard', '/api/thesaurus/quickterm/', {'query': 'muscul*'}),
	('quick-wildcard-multiword', '/api/thesaurus/quickterm/', {'query': 'sindrome pe*'}),
	# the plan 002 regression: the words are not contiguous
	('quick-wildcard-noncontiguous', '/api/thesaurus/quickterm/', {'query': 'transtorno espectro au*'}),
	('quick-multiword', '/api/thesaurus/quickterm/', {'query': 'insuficiencia cardiaca'}),
	('quick-acronym', '/api/thesaurus/quickterm/', {'query': 'covid'}),
]


class Options(object):
	"""What the comparators need to know, gathered from the command line."""

	def __init__(self, ignore_order=False, ignore_count=False, volatile=None):
		self.ignore_order = ignore_order
		self.ignore_count = ignore_count
		self.volatile = set(volatile or VOLATILE_ATTRIBUTES)


# --- fetching --------------------------------------------------------------

def fetch(base_url, path, params, fmt, timeout):
	query = dict(params)
	query['format'] = fmt
	url = '%s%s?%s' % (base_url, path, urllib.parse.urlencode(query))
	request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})

	with urllib.request.urlopen(request, timeout=timeout) as response:
		return response.read()


# --- XML comparison --------------------------------------------------------

def normalize(text):
	return ' '.join((text or '').split())


def element_key(element):
	"""The identity of a result element, for order-insensitive comparison."""
	for name in RECORD_KEYS:
		value = element.get(name)
		if value is not None:
			return (element.tag, name, value)

	return (element.tag, 'text', normalize(element.text))


def is_result_list(left_children, right_children):
	"""True for a homogeneous run of siblings — <record_list>, <Result>, a term list.

	Order only means something for those. Applying the keyed comparison to a
	record's own fields instead would report a changed <descriptor> as a record
	that exists on one side only, which is true but useless.
	"""
	tags = {child.tag for child in left_children} | {child.tag for child in right_children}

	return len(tags) == 1 and max(len(left_children), len(right_children)) > 1


def first_difference(left, right, options, path='/'):
	"""Return the path of the first structural difference, or None if equal."""
	here = path + left.tag

	if left.tag != right.tag:
		return '%s (tag: %s != %s)' % (path, left.tag, right.tag)

	for name, value in left.attrib.items():
		if name in options.volatile:
			continue
		if right.get(name) != value:
			return '%s/@%s (%r != %r)' % (here, name, value, right.get(name))

	missing = set(right.attrib) - set(left.attrib) - options.volatile
	if missing:
		return '%s/@%s (missing on A)' % (here, sorted(missing)[0])

	if normalize(left.text) != normalize(right.text):
		return '%s/text() (%r != %r)' % (here, normalize(left.text), normalize(right.text))

	left_children, right_children = list(left), list(right)

	if options.ignore_order and is_result_list(left_children, right_children):
		return unordered_difference(left_children, right_children, options, here)

	if len(left_children) != len(right_children):
		return '%s (%d children != %d)' % (here, len(left_children), len(right_children))

	for index, (left_child, right_child) in enumerate(zip(left_children, right_children)):
		difference = first_difference(left_child, right_child, options, '%s[%d]/' % (here, index))
		if difference:
			return difference

	return None


def unordered_difference(left_children, right_children, options, here):
	"""Compare two child lists by identity rather than by position."""
	left_by_key = {element_key(child): child for child in left_children}
	right_by_key = {element_key(child): child for child in right_children}

	if not options.ignore_count:
		only_a = set(left_by_key) - set(right_by_key)
		only_b = set(right_by_key) - set(left_by_key)

		if only_a:
			return '%s (only on A: %s)' % (here, format_key(sorted(only_a)[0]))
		if only_b:
			return '%s (only on B: %s)' % (here, format_key(sorted(only_b)[0]))
		if len(left_children) != len(right_children):
			return '%s (%d children != %d)' % (here, len(left_children), len(right_children))

	for key in sorted(set(left_by_key) & set(right_by_key)):
		difference = first_difference(
			left_by_key[key], right_by_key[key], options, '%s[%s]/' % (here, format_key(key)))
		if difference:
			return difference

	return None


def format_key(key):
	tag, name, value = key
	return '%s@%s=%s' % (tag, name, value)


# --- JSON comparison -------------------------------------------------------

def json_key(item):
	"""The identity of a JSON result item, for order-insensitive comparison."""
	if isinstance(item, dict):
		# both resources wrap each result in a single-key dict whose value
		# carries an 'attr' object: {'item': {'attr': {'id': ..., ...}}}
		for value in item.values():
			if isinstance(value, dict) and isinstance(value.get('attr'), dict):
				for name in RECORD_KEYS:
					if name in value['attr']:
						return '%s=%s' % (name, value['attr'][name])

	return json.dumps(item, sort_keys=True, ensure_ascii=False)


def first_difference_json(left, right, options, path='$'):
	"""Return the path of the first difference between two decoded payloads."""
	if type(left) is not type(right):
		return '%s (type: %s != %s)' % (path, type(left).__name__, type(right).__name__)

	if isinstance(left, dict):
		only_a = sorted(set(left) - set(right) - options.volatile)
		only_b = sorted(set(right) - set(left) - options.volatile)

		if only_a:
			return '%s.%s (only on A)' % (path, only_a[0])
		if only_b:
			return '%s.%s (only on B)' % (path, only_b[0])

		for key in sorted(left):
			if key in options.volatile:
				continue
			difference = first_difference_json(left[key], right[key], options, '%s.%s' % (path, key))
			if difference:
				return difference

		return None

	if isinstance(left, list):
		if options.ignore_order and max(len(left), len(right)) > 1:
			return unordered_difference_json(left, right, options, path)

		if len(left) != len(right):
			return '%s (%d items != %d)' % (path, len(left), len(right))

		for index, (left_item, right_item) in enumerate(zip(left, right)):
			difference = first_difference_json(
				left_item, right_item, options, '%s[%d]' % (path, index))
			if difference:
				return difference

		return None

	if isinstance(left, str):
		if normalize(left) != normalize(right):
			return '%s (%r != %r)' % (path, normalize(left), normalize(right))
		return None

	if left != right:
		return '%s (%r != %r)' % (path, left, right)

	return None


def unordered_difference_json(left, right, options, path):
	left_by_key = {json_key(item): item for item in left}
	right_by_key = {json_key(item): item for item in right}

	if not options.ignore_count:
		only_a = sorted(set(left_by_key) - set(right_by_key))
		only_b = sorted(set(right_by_key) - set(left_by_key))

		if only_a:
			return '%s (only on A: %s)' % (path, only_a[0])
		if only_b:
			return '%s (only on B: %s)' % (path, only_b[0])
		if len(left) != len(right):
			return '%s (%d items != %d)' % (path, len(left), len(right))

	for key in sorted(set(left_by_key) & set(right_by_key)):
		difference = first_difference_json(
			left_by_key[key], right_by_key[key], options, '%s[%s]' % (path, key))
		if difference:
			return difference

	return None


# --- rendering -------------------------------------------------------------

def pretty_xml(content):
	root = etree.fromstring(content)
	return etree.tostring(root, pretty_print=True, encoding='unicode').splitlines()


def pretty_json(content):
	data = json.loads(content.decode('utf-8'))
	return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False).splitlines()


def print_diff(left_lines, right_lines, verbose):
	diff = list(difflib.unified_diff(
		left_lines, right_lines, fromfile='A', tofile='B', lineterm=''))

	if not verbose and len(diff) > MAX_DIFF_LINES:
		shown, hidden = diff[:MAX_DIFF_LINES], len(diff) - MAX_DIFF_LINES
		diff = shown + ['    … %d more lines, use -v for the whole diff' % hidden]

	for line in diff:
		print('    %s' % line)


# --- one comparison --------------------------------------------------------

def compare(case, fmt, args, options):
	"""Return (status, detail) for one case in one format."""
	name, path, params = case

	try:
		content_a = fetch(args.base_a, path, params, fmt, args.timeout)
	except (urllib.error.URLError, OSError) as error:
		return 'ERROR', 'A did not answer: %s' % error

	try:
		content_b = fetch(args.base_b, path, params, fmt, args.timeout)
	except (urllib.error.URLError, OSError) as error:
		return 'ERROR', 'B did not answer: %s' % error

	try:
		if fmt == 'xml':
			difference = first_difference(
				etree.fromstring(content_a), etree.fromstring(content_b), options)
			render = pretty_xml
		else:
			difference = first_difference_json(
				json.loads(content_a.decode('utf-8')),
				json.loads(content_b.decode('utf-8')),
				options)
			render = pretty_json
	except (etree.XMLSyntaxError, ValueError) as error:
		return 'ERROR', 'unparsable response: %s' % error

	if difference is None:
		return 'PASS', None

	print_diff(render(content_a), render(content_b), args.verbose)

	return 'FAIL', difference


# --- entry point -----------------------------------------------------------

def select_cases(args):
	cases = CASES

	if args.case:
		wanted = set(args.case)
		cases = [case for case in cases if case[0] in wanted]

	if args.path:
		cases = [case for case in cases if case[1].startswith(args.path)]

	return cases


def parse_args(argv=None):
	parser = argparse.ArgumentParser(
		description='Compare two DeCS API deployments in XML and JSON.')

	parser.add_argument('--base-a', default=BASE_A_DEFAULT,
	                    help='the deployment under test (default: %(default)s)')
	parser.add_argument('--base-b', default=BASE_B_DEFAULT,
	                    help='the reference deployment (default: %(default)s)')

	parser.add_argument('--format', choices=['xml', 'json', 'both'], default='both',
	                    help='which serialization to compare (default: %(default)s)')
	parser.add_argument('--case', action='append',
	                    help='run only this case, repeatable')
	parser.add_argument('--path', help='run only cases whose path starts with this')

	parser.add_argument('--ignore-order', action='store_true',
	                    help='compare result lists by identity instead of by position')
	parser.add_argument('--ignore-count', action='store_true',
	                    help='compare only the records both deployments returned')
	parser.add_argument('--relaxed', action='store_true',
	                    help='--ignore-order and --ignore-count together')
	parser.add_argument('--ignore-attr', action='append', default=[],
	                    help='also treat this attribute or key as volatile, repeatable')

	parser.add_argument('--timeout', type=int, default=int(os.environ.get('DECS_TEST_TIMEOUT', 60)),
	                    help='seconds to wait for each response (default: %(default)s)')
	parser.add_argument('-v', '--verbose', action='store_true',
	                    help='print whole diffs instead of the first %d lines' % MAX_DIFF_LINES)
	parser.add_argument('--list', action='store_true',
	                    help='print the case names and exit')

	return parser.parse_args(argv)


def main(argv=None):
	args = parse_args(argv)
	cases = select_cases(args)

	if args.list:
		for name, path, params in cases:
			print('%-30s %s %s' % (name, path, params))
		return 0

	if not cases:
		sys.stderr.write('no case matched the selection\n')
		return 1

	options = Options(
		ignore_order=args.ignore_order or args.relaxed,
		ignore_count=args.ignore_count or args.relaxed,
		volatile=VOLATILE_ATTRIBUTES | set(args.ignore_attr))

	formats = ['xml', 'json'] if args.format == 'both' else [args.format]

	print('A: %s' % args.base_a)
	print('B: %s' % args.base_b)
	print('%d cases × %s%s\n' % (
		len(cases), '+'.join(formats),
		', relaxed' if options.ignore_order or options.ignore_count else ', strict'))

	failures = []

	for case in cases:
		for fmt in formats:
			status, detail = compare(case, fmt, args, options)
			label = '%s [%s]' % (case[0], fmt)

			if status == 'PASS':
				print('  PASS  %s' % label)
			else:
				print('  %-5s %s — %s' % (status, label, detail))
				failures.append((label, status, detail))

	print('\n%s' % ('=' * 72))
	if failures:
		print('  %d of %d comparisons failed:' % (len(failures), len(cases) * len(formats)))
		for label, status, detail in failures:
			print('    %-5s %s — %s' % (status, label, detail))
	else:
		print('  all %d comparisons passed' % (len(cases) * len(formats)))
	print('%s\n' % ('=' * 72))

	return 1 if failures else 0


if __name__ == '__main__':
	sys.exit(main())
