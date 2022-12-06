#!/usr/bin/env python3

## https://developers.google.com/gmail/api/guides/filter_settings#python
## https://googleapis.github.io/google-api-python-client/docs/dyn/gmail_v1.users.settings.filters.html
## https://medium.com/analytics-vidhya/email-extraction-using-python-with-some-filters-233ae451f011
## https://saralgyaan.com/posts/make-python-your-ps/
## https://developers.google.com/gmail/api/quickstart/python
## https://support.google.com/mail/answer/7190?hl=en
## https://github.com/googleapis/google-auth-library-python/issues/501
## https://google-auth.readthedocs.io/en/stable/reference/google.oauth2.credentials.html

## https://console.cloud.google.com/home/dashboard?project=gmailfilter-370504
## https://console.cloud.google.com/apis/credentials?project=sieve-370505

import os
import re
import sys
sys.dont_write_bytecode = True

import json
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from addict import Addict
from ruamel import yaml
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from itertools import chain
from dataclasses import dataclass
from typing import List, Dict
from functools import lru_cache

from leatherman.dictionary import head_body
from leatherman.fuzzy import fuzzy
from leatherman.repr import __repr__
from leatherman.dbg import dbg

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
file_handler = logging.FileHandler('sieve.log')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# If modifying these scopes, delete the file token.json.
SCOPES = [
	'https://mail.google.com/', ## for gmail
    ## 'https://www.googleapis.com/auth/admin.directory.group.readonly', ## for groups
]

METADATA_HEADERS = [
    'to',
    'cc',
    'bcc',
    'from',
    'date',
    'list-id',
    'subject',
    'delivered-to',
    'precedence',
    'sender',
    'reply-to',
    'in-reply-to',
    'mailing-list',
]

DIR = os.path.abspath(os.path.dirname(__file__))
CWD = os.path.abspath(os.getcwd())
REL = os.path.relpath(DIR, CWD)

REAL_FILE = os.path.abspath(__file__)
REAL_NAME = os.path.basename(REAL_FILE)
REAL_PATH = os.path.dirname(REAL_FILE)
if os.path.islink(__file__):
    LINK_FILE = REAL_FILE; REAL_FILE = os.path.abspath(os.readlink(__file__))
    LINK_NAME = REAL_NAME; REAL_NAME = os.path.basename(REAL_FILE)
    LINK_PATH = REAL_PATH; REAL_PATH = os.path.dirname(REAL_FILE)

NAME, EXT = os.path.splitext(REAL_NAME)

class SieveYmlNotFoundError(Exception):
    def __init__(self, sieve_yml):
        msg = f'error: sieve_yml={sieve_yml} not found'
        super().__init__(msg)

def pf(obj):
    if isinstance(obj, str):
        obj = json.loads(obj)
    return json.dumps(obj, indent=2, sort_keys=True)

def pp(obj):
    print(pf(obj))

def compare(item, test):
    if item:
        return item == test
    return False

def filter_emails(s, regex=re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')):
    if s:
        return tuple(regex.findall(s))
    return None

class Message:
    def __init__(self, thread, id, historyId, internalDate, labelIds, payload, sizeEstimate, snippet, threadId, raw=None):
        self.id = id
        self.thread = thread
        self.historyId = historyId
        self.internalDate = internalDate
        self.labelIds = labelIds
        self.payload = Addict(payload)
        self.raw = raw
        self.sizeEstimate = sizeEstimate
        self.snippet = snippet
        self.threadId = threadId

    @property
    def subject(self):
        return self.headers['subject']

    @property
    @lru_cache()
    def to(self):
        return filter_emails(self.headers['to'])

    @property
    @lru_cache()
    def cc(self):
        return filter_emails(self.headers.get('cc', []))

    @property
    @lru_cache()
    def bcc(self):
        return filter_emails(self.headers.get('bcc', []))

    @property
    @lru_cache()
    def fr(self):
        return filter_emails(self.headers['from'])[0]

    @property
    def prescedence(self):
        return self.headers.get('prescedence')

    @property
    @lru_cache()
    def labels(self):
        return {
                id: self.thread.sieve.labels[id]
            for id
            in self.labelIds
        }

    @property
    @lru_cache()
    def headers(self):
        return {
            h['name'].lower():h['value']
            for h
            in self.payload.headers
        }

class Thread:
    def __init__(self, sieve, id, historyId, messages, snippet=None):
        self.id = id
        self.sieve = sieve
        self.historyId = historyId
        self.messages = [Message(thread=self, **message) for message in messages]
        self.snippet = snippet

    @lru_cache()
    def any_label(self, key, test):
        return any([message.labels.get(key) == test for message in self.messages])

    @lru_cache()
    def any_header(self, key, test):
        return any([message.header.get(key) == test for message in self.messages])


    @lru_cache()
    def to(self, test):
        return any([message.to == test for message in self.messages])

    @lru_cache()
    def cc(self, test):
        return any([message.cc == test for message in self.messages])

    @lru_cache()
    def bcc(self, test):
        return any([message.bcc == test for message in self.messages])

    @lru_cache()
    def fr(self, test):
        return any([message.fr == test for message in self.messages])

class Sieve:
    def __init__(self, creds_json, sieve_yml, **kwargs):
        self.auth(creds_json)
        self.gmail = build('gmail', 'v1', credentials=self.creds)
        self.profile = self.gmail.users().getProfile(userId='me').execute()
        self.labels_api = self.gmail.users().labels()
        self.threads_api = self.gmail.users().threads()
        self.directory = build('admin', 'directory_v1', credentials=self.creds)
        self.groups_api = self.directory.groups()
        self.load(sieve_yml)

    __repr__ = __repr__

    @property
    @lru_cache()
    def labels(self):
        return {
            label['id']: label['name']
            for label
            in self.labels_api.list(userId='me').execute()['labels']
        }

    def auth(self, creds_json):
        creds_json = os.path.realpath(os.path.expanduser(creds_json))
        token_json = os.path.join(os.path.dirname(creds_json), '.token.json')
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists(token_json):
            creds = Credentials.from_authorized_user_file(token_json, SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_json, SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(token_json, 'w') as token:
                token.write(pf(creds.to_json()))
        self.creds = creds

    def load(self, sieve_yml):
        sieve_yml = os.path.expanduser(sieve_yml)
        if not os.path.exists(sieve_yml):
            raise SieveYmlNotFoundError(sieve_yml)
        cfg = Addict({
            key.replace('-', '_'): value
            for key, value
            in yaml.safe_load(open(sieve_yml)).items()
        })
        filters = cfg.pop('filters', [])
        spammers = cfg.pop('spammers')
        cfg.filters = [
            Addict(name=to, to=to, action=['archive', f'_/{to}'])
            for to
            in spammers.to
        ]
        cfg.filters += [
            Addict(name=fr, fr=fr, action=['archive', f'_/{fr}'])
            for fr
            in spammers.fr
        ]
        cfg.filters += [
            Addict(name=name, **body)
            for name, body
            in [head_body(f) for f in filters]
        ]
        self.cfg = cfg

    def show_filters(self):
        pp(self.cfg.filters)

    def run(self):
        #gmail = build('gmail', 'v1', credentials=self.creds)
        #threads_api = gmail.users().threads()
        pp(dict(labels=self.labels))
        threads_req = self.threads_api.list(q=self.cfg.query, userId='me', maxResults=self.cfg.max_results)
        while threads_req:
            threads_res = threads_req.execute()
            threads = threads_res.get('threads', [])
            print('len(threads) =', len(threads))
            for thread in threads:
                thread = self.threads_api.get(userId='me', id=thread['id'], format='metadata', metadataHeaders=METADATA_HEADERS).execute()
                t = Thread(sieve=self, **thread)
                for message in t.messages:
                    print('subject =', message.subject)
                    if not t.to(tuple(['scott.idler@tatari.tv'])):
                        print('to =', message.to)
                        print('fr =', message.fr)
                        print('cc =', message.cc)
                        print('bcc =', message.bcc)
                        print('labels =', message.labels)
                print('*'*80)

            ## keep searching until None
            threads_req = threads_api.list_next(threads_req, threads_res)



#def sieves(path):
#    return [
#        item
#        for item
#        in os.listdir(path)
#        if os.path.isdir(os.path.join(path, item))
#    ]

def main(args):
#    parser = ArgumentParser(
#        description=__doc__,
#        formatter_class=RawDescriptionHelpFormatter,
#        add_help=False)
#    parser.add_argument(
#        '--config',
#        metavar='FILEPATH',
#        default='~/.config/%(NAME)s/%(NAME)s.yml' % globals(),
#        help='default="%(default)s"; config filepath')
#    ns, rem = parser.parse_known_args(args)
#    try:
#        config = dict([
#            (k.replace('-', '_'), v)
#            for k, v
#            in yaml.safe_load(open(os.path.expanduser(ns.config))).items()
#        ])
#        config['config'] = ns.config
#        config['creds'] = os.path.realpath(re.sub(r'^./', os.path.dirname(ns.config)+'/', config['creds']))
#    except FileNotFoundError as er:
#        config = dict()
#    parser = ArgumentParser(
#        parents=[parser])
#    parser.set_defaults(**config)
#    parser.add_argument(
#        '--creds',
#        help='default="%(default)s"; first name')
#
#    ns = parser.parse_args(rem)
#    print(ns)

#    base = os.path.expanduser('~/.config/%(NAME)s' % globals())
#    parser = ArgumentParser()
#    parser.add_argument(
#        'sieve',
#        choices=sieves(base),
#        help='choose your sieve')
#    ns = parser.parse_args()
#    print(ns)

    parser = ArgumentParser()
    parser.add_argument(
        '--creds-json',
        default='./.creds.json',
        help='default="%(default)s"; path to the creds file')
    parser.add_argument(
        '--sieve-yml',
        default='./sieve.yml',
        help='default="%(default)s"; path to the sieve config file')
    parser.add_argument(
        '-f', '--show-filters',
        action='store_true',
        help='toggle showing the filters')
    ns = parser.parse_args(args)
    sieve = Sieve(**ns.__dict__)
    if ns.show_filters:
        sieve.show_filters()
    else:
        sieve.run()

if __name__ == '__main__':
    main(sys.argv[1:])

