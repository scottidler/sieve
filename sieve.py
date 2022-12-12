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
from collections import OrderedDict

from leatherman.dictionary import head_body
from leatherman.fuzzy import fuzzy, FuzzyList
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

LABELS = {
    'CHAT': 'CHAT',
    'SPAM': 'SPAM',
    #'DRAFT': 'DRAFT',
    'INBOX': 'INBOX',
    'TRASH': 'TRASH',
    'UNREAD': 'UNREAD',
    'STARRED': 'STARRED',
    'IMPORTANT': 'IMPORTANT',
    'CATEGORY_FORUMS': 'CATEGORY_FORUMS',
    'CATEGORY_SOCIAL': 'CATEGORY_SOCIAL',
    'CATEGORY_UPDATES': 'CATEGORY_UPDATES',
    'CATEGORY_FINANCE': 'CATEGORY_FINANCE',
    'CATEGORY_PERSONAL': 'CATEGORY_PERSONAL',
    'CATEGORY_SHOPPING': 'CATEGORY_SHOPPING',
    'CATEGORY_PURCHASES': 'CATEGORY_PURCHASES',
    'CATEGORY_PROMOTIONS': 'CATEGORY_PROMOTIONS',
}

ADDING = {
    'spam': 'SPAM',
    'star': 'STARRED',
    'inbox': 'INBOX',
    'trash': 'TRASH',
    'unread': 'UNREAD',
    'important': 'IMPORTANT',
}

REMOVING ={
    'read': 'UNREAD',
    'unspam': 'SPAM',
    'unstar': 'STARRED',
    'archive': 'INBOX',
    'untrash': 'TRASH',
    'unimportant': 'IMPORTANT',
}

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

def tuplify(obj):
    if obj is None:
        return ()
    if isinstance(obj, list):
        return tuple(obj)
    elif isinstance(obj, tuple):
        return obj
    return tuple([obj])

def compare(item, test):
    if item:
        return item == test
    return False

def format_emails(s, regex=re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')):
    if s:
        return tuple(regex.findall(s))
    return ()

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

    __repr__ = __repr__

    @property
    def subject(self):
        '''subject: singular'''
        return self.headers['subject']

    @property
    @lru_cache()
    def fr(self):
        '''from: plural'''
        return format_emails(self.headers['from'])

    @property
    @lru_cache()
    def to(self):
        '''to: plural'''
        return format_emails(self.headers.get('to'))

    @property
    @lru_cache()
    def cc(self):
        '''cc: plural'''
        return format_emails(self.headers.get('cc'))

    @property
    @lru_cache()
    def bcc(self):
        '''bcc: plural'''
        return format_emails(self.headers.get('bcc'))

    @property
    def prescedence(self):
        '''prescedence: singular'''
        return self.headers.get('prescedence')

    @property
    @lru_cache()
    def labels(self):
        '''labels: plural'''
        return {
            self.thread.sieve.labels[id]: id
            for id
            in self.labelIds
        }

    @property
    @lru_cache()
    def headers(self):
        '''headers: plural'''
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

    __repr__ = __repr__

    @property
    def subject(self):
        '''subject: singular'''
        return self.messages[0].subject

    @property
    def subjects(self):
        '''subjects: plural'''
        return tuple(m.subject for m in self.messages)

    @property
    def frs(self):
        '''frs: plural'''
        return tuple(m.fr for m in self.messages)

    @property
    def tos(self):
        '''tos: plural'''
        return tuple(m.to for m in self.messages)

    @property
    def ccs(self):
        '''ccs: plural'''
        return tuple(m.cc for m in self.messages)

    @property
    def bccs(self):
        '''bccs: plural'''
        return tuple(m.bcc for m in self.messages)

class Filter(Addict):
    def __init__(self, name=None, subject=None, fr=None, to=None, cc=None, bcc=None, precedence=None, actions=None, **headers):
        dict.__init__(
            self,
            name=name,
            subject=subject,
            fr=tuplify(fr),
            to=to,
            cc=tuplify(cc),
            bcc=tuplify(bcc),
            precedence=precedence,
            actions=actions,
            **headers,
        )

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
    def labels(self):
        return {
            label['name']: label['id']
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
        self.filters = []
        if cfg.spammers.fr:
            self.filters += [
                Filter(name=f'spammer-{fr}', fr=fr, actions=['archive', f'_/{fr}'])
                for fr
                in cfg.spammers.fr
            ]
        if cfg.spammers.to:
            self.filters += [
                Filter(name=f'spammer-{to}', to=to, actions=['archive', f'_/{to}'])
                for to
                in cfg.spammers.to
            ]
        if cfg.filters:
            self.filters += [
                    Filter(
                        name=name,
                        subject=body.get('subject'),
                        fr=tuplify(body.get('fr')),
                        to=body.get('to'),
                        cc=tuplify(body.get('cc')),
                        bcc=tuplify(body.get('bcc')),
                        precedence=body.get('precedence'),
                        actions=body.get('actions'),
                        headers={},
                    )
                for name, body
                in [head_body(f) for f in cfg.filters]
            ]
        self.cfg = cfg

    def show_filters(self):
        pp(self.filters)

    def filter_thread(self, thread):
        actions = []
        for f in self.filters:
            subject, fr, to, cc, bcc = [True]*5
            if f.subject:
                subject = len(FuzzyList(thread.subjects).include(f.subject))
            if f.fr:
                fr = any([FuzzyList(m.fr).include(*f.fr) for m in thread.messages])
            if f.to:
                to = any([FuzzyList(m.to).include(f.to) for m in thread.messages])
            if f.cc:
                cc = any([FuzzyList(m.cc).include(*f.cc) for m in thread.messages])
            if f.bcc:
                bcc = any([FuzzyList(m.bcc).include(*f.bcc) for m in thread.messages])
            if subject and fr and to and cc and bcc:
                actions += f.actions
        return actions

    def filter_gmail(self):
        threads_req = self.threads_api.list(q=self.cfg.query, userId='me', maxResults=self.cfg.max_results)
        changes = []
        while threads_req:
            threads_res = threads_req.execute()
            threads = threads_res.get('threads', [])
            print('len(threads) =', len(threads))
            for thread in threads:
                thread = Thread(sieve=self, **self.threads_api.get(userId='me', id=thread['id'], format='metadata', metadataHeaders=METADATA_HEADERS).execute())
                actions = self.filter_thread(thread)
                if actions:
                    changes += [(thread.id, actions)]
            ## keep searching until None
            threads_req = self.threads_api.list_next(threads_req, threads_res)
        return changes

    def get_or_create_label_id(self, label):
        if label in ADDING:
            return ADDING[label], None
        if label in REMOVING:
            return None, REMOVING[label]
        if label in self.labels:
            return self.labels[label], None
        try:
            result = self.labels_api.create(userId='me', body={'name': label}).execute()
            return result['id'], None
        except HttpError as e:
            if e.resp.status == 409:
                dbg('label =', label)
                pp(dict(labels=self.labels))
                return self.labels[label], None
            else:
                print(f'Error creating label {label}')
                raise e

    def execute_actions(self, changes):
        for thread_id, actions in changes:
            body = Addict(addLabelIds=[], removeLabelIds=[])
            for action in actions:
                add, remove = self.get_or_create_label_id(action)
                if add:
                    body.addLabelIds.append(add)
                if remove:
                    body.removeLabelIds.append(remove)
            pp(dict(thread_id=thread_id, body=body))
            print(80*'-')

    def run(self):
        pp(self.labels)
        changes = self.filter_gmail()
        self.execute_actions(changes)

def main(args):
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

