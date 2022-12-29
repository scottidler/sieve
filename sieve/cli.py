#!/usr/bin/env python3

import os
import sys

from argparse import ArgumentParser, RawDescriptionHelpFormatter, Action
from addict import Addict
from ruamel import yaml

from leatherman.dbg import dbg

from sieve import Sieve, ADD_ACTION_TO_LABEL, REMOVE_ACTION_TO_LABEL, METADATA_HEADERS

def actions_choices():
    return list(ADD_ACTION_TO_LABEL.keys()) + list(REMOVE_ACTION_TO_LABEL.keys())

class HeaderAction(Action):
    '''
    custom action to parse a list of key, value pairs separated by an equals sign
    '''
    def __init__(self, option_strings, dest, **kwargs):
        self.header_keys = kwargs.get('header_keys', [])
        super().__init__(option_strings, dest, nargs='*', **kwargs)
    def __call__(self, parser, namespace, values, option_string=None):
        def split_by(s, *seps):
            for sep in seps:
                parts = s.split(sep)
                if len(parts) > 1:
                    return parts
            raise ValueError(f'no separator found in {s}')
        headers = {
            key: value
            for key, value in [
                split_by(value, '=', ':')
                for value in values
            ]
        }
        setattr(namespace, self.dest, headers)

def main(args):
    parser = ArgumentParser()
    parser.add_argument(
        '-v', '--verbose',
        dest='verbose',
        action='store_true',
        help='enable verbose logging')
    parser.add_argument(
        '-n', '--nerf',
        action='store_true',
        help='do not perform any actions')
    parser.add_argument(
        '--creds-json',
        metavar='CREDS-JSON',
        default='./.creds.json',
        help='default="%(default)s"; path to the creds file')
    parser.add_argument(
        '--sieve-yml',
        metavar='SIEVE-YML',
        default='./sieve.yml',
        help='default="%(default)s"; path to the sieve config file')
    parser.add_argument(
        'spec_pattern',
        metavar='spec-pattern',
        nargs='?',
        help='spec to run')
    parser.add_argument(
        'filter_pattern',
        metavar='filter-pattern',
        nargs='?',
        help='filter to run')
    parser.add_argument(
        '-q', '--query',
        dest='query_override',
        metavar='QUERY',
        help='query to run')
    parser.add_argument(
        '-H', '--headers',
        dest='headers_override',
        metavar='KEY=VALUE',
        action=HeaderAction,
        help='set headers for matching')
    parser.add_argument(
        '-a', '--actions',
        dest='actions_override',
        metavar='ACTION',
        choices=actions_choices(),
        nargs='+',
        help='set actions to perform')
    ns = parser.parse_args(args)
    print(ns)
    if ns.query_override and not ns.spec_pattern:
        parser.error('spec-name is required when query is specified')
    if ns.headers_override:
        if not ns.spec_pattern:
            parser.error('spec-name is required when headers are specified')
        if not all([key in METADATA_HEADERS for key in ns.headers_override.keys()]):
            msg = f'invalid header keys: {list(ns.headers_override.keys())}; valid keys are {METADATA_HEADERS}'
            parser.error(msg)
    if ns.actions_override and not ns.spec_pattern:
        parser.error('spec-name is required when actions are specified')

    print(ns)
    sieve = Sieve(**ns.__dict__)
    sieve.run()

if __name__ == '__main__':
    main(sys.argv[1:])
