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

LOGGING_LEVEL = os.environ.get('LOGGING_LEVEL', 'INFO').upper()

logger = logging.getLogger('sieve')
logging.getLogger('googleapiclient').setLevel(logging.ERROR)
logging.basicConfig(
    format='%(asctime)s|%(name)s|%(message)s',
    level=LOGGING_LEVEL,
    handlers=[
        logging.FileHandler('sieve.log'),
        logging.StreamHandler()
    ]
)

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
}

CATEGORIES = {
    'CATEGORY_FORUMS': 'CATEGORY_FORUMS',
    'CATEGORY_SOCIAL': 'CATEGORY_SOCIAL',
    'CATEGORY_UPDATES': 'CATEGORY_UPDATES',
    'CATEGORY_FINANCE': 'CATEGORY_FINANCE',
    'CATEGORY_PERSONAL': 'CATEGORY_PERSONAL',
    'CATEGORY_SHOPPING': 'CATEGORY_SHOPPING',
    'CATEGORY_PURCHASES': 'CATEGORY_PURCHASES',
    'CATEGORY_PROMOTIONS': 'CATEGORY_PROMOTIONS',
}

ADD_ACTION_TO_LABEL = {
    'spam': 'SPAM',
    'star': 'STARRED',
    'inbox': 'INBOX',
    'trash': 'TRASH',
    'unread': 'UNREAD',
    'important': 'IMPORTANT',
}

REMOVE_ACTION_TO_LABEL = {
    'read': 'UNREAD',
    'unspam': 'SPAM',
    'unstar': 'STARRED',
    'archive': 'INBOX',
    'untrash': 'TRASH',
    'unimportant': 'IMPORTANT',
}

ACTION_TO_LABEL = {
    'spam': ('SPAM', True),
    'star': ('STARRED', True),
    'inbox': ('INBOX', True),
    'trash': ('TRASH', True),
    'unread': ('UNREAD', True),
    'important': ('IMPORTANT', True),

    'read': ('UNREAD', False),
    'unspam': ('SPAM', False),
    'unstar': ('STARRED', False),
    'archive': ('INBOX', False),
    'untrash': ('TRASH', False),
    'unimportant': ('IMPORTANT', False),
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

class LabelIntersectionError(Exception):
    def __init__(self, addLabelIds, removeLabelIds):
        msg = f'error: addLabelIds={addLabelIds} and removeLabelIds={removeLabelIds} intersect'
        super().__init__(msg)

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

def ppl(obj):
    logger.info(pf(obj))

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

def is_valid(obj):
    return len(set(obj.addLabelIds) & set(obj.removeLabelIds)) == 0

def difference(minuend, subtrahend):
    minuend = set(minuend)
    subtrahend = set(subtrahend)
    difference = tuple(minuend - subtrahend)
    return difference

def intersect(a, b):
    a = set(a)
    b = set(b)
    intersection = tuple(a & b)
    return intersection

def union(a, b):
    a = set(a)
    b = set(b)
    union = tuple(a | b)
    return union

def filter_category_labels(labelIds):
    return tuple([labelId for labelId in labelIds if labelId not in CATEGORIES])

class Message:
    def __init__(self, thread, id, labelIds, threadId, historyId=None, internalDate=None, sizeEstimate=None, snippet=None, payload=None, raw=None):
        self.thread = thread
        self.id = id
        self.labelIds = filter_category_labels(labelIds)
        self.threadId = threadId
        self.historyId = historyId
        self.internalDate = internalDate
        self.sizeEstimate = sizeEstimate
        self.snippet = snippet
        self.payload = Addict(payload if payload else {})
        self.raw = raw

    __repr__ = __repr__

    @property
    @lru_cache()
    def subject(self):
        '''subject: singular'''
        return self.headers.get('subject')

    @property
    @lru_cache()
    def sender(self):
        '''sender: plural'''
        return format_emails(self.headers.get('sender'))

    @property
    @lru_cache()
    def fr(self):
        '''from: plural'''
        return format_emails(self.headers.get('from'))

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
            self.thread.sieve.ids_to_labels[id]: id
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
    def __init__(self, sieve, id, messages, historyId=None, snippet=None):
        self.id = id
        self.sieve = sieve
        self.messages = [Message(thread=self, **message) for message in messages]
        self.historyId = historyId
        self.snippet = snippet

    __repr__ = __repr__

    @property
    def labels(self):
        '''labels: plural'''
        return [m.labelIds for m in self.messages]

    @property
    def labels_are_uniform(self):
        '''labels_are_uniform: singular'''
        return len(set(self.labels)) == 1

    @property
    def subject(self):
        '''subject: singular'''
        return self.messages[0].subject

    @property
    def subjects(self):
        '''subjects: plural'''
        return tuple(m.subject for m in self.messages)

    @property
    def senders(self):
        '''senders: plural'''
        return tuple(m.sender for m in self.messages)

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

    def labels_match(self, labels):
        '''labels_match: singular'''
        if self.labels_are_uniform:
            return self.labels[0] == labels
        return False

    def is_uptodate(self, body):
        def is_uptodate(labels, body):
            if len(intersect(labels, body.addLabelIds)) != len(body.addLabelIds):
                logger.debug(f'ADD: intersect failed: labels={labels} body.addLabelIds={body.addLabelIds} add_result={intersect(labels, body.addLabelIds)}')
                return False
            if len(intersect(labels, body.removeLabelIds)) != 0:
                logger.debug(f'REMOVE: intersect failed: labels={labels} body.removeLabelIds={body.removeLabelIds} remove_result={intersect(labels, body.removeLabelIds)}')
                return False
            return True
        return all(is_uptodate(labels, body) for labels in self.labels)

class Filter:
    def __init__(self, name=None, subject=None, sender=None, fr=None, to=None, cc=None, bcc=None, precedence=None, addLabelIds=None, removeLabelIds=None, **headers):
        self.name = name
        self.subject = subject
        self.sender = sender
        self.fr = tuplify(fr)
        self.to = to
        self.cc = tuplify(cc)
        self.bcc = tuplify(bcc)
        self.precedence = precedence
        self.addLabelIds = tuple([] if addLabelIds is None else set(addLabelIds))
        self.removeLabelIds = tuple([] if removeLabelIds is None else set(removeLabelIds))
        self.headers = headers

        if not is_valid(self):
            raise LabelIntersectionError(self.addLabelIds, self.removeLabelIds)

    __repr__ = __repr__

    def to_json(self):
        return {
            'name': self.name,
            'subject': self.subject,
            'sender': self.sender,
            'fr': self.fr,
            'to': self.to,
            'cc': self.cc,
            'bcc': self.bcc,
            'precedence': self.precedence,
            'addLabelIds': tuple(self.addLabelIds),
            'removeLabelIds': tuple(self.removeLabelIds),
            'headers': self.headers,
        }

class Change:
    def __init__(self, sieve, thread, filters):
        self.sieve = sieve
        self.thread = thread
        self.filters = filters

    __repr__ = __repr__

    def execute(self):
        body = Addict(addLabelIds=[], removeLabelIds=[])
        logger.info(f'thread.id={self.thread.id}: "{self.thread.subject}"')
        logger.debug(f'thread.labels={self.thread.labels}')
        for f in self.filters:
            body.addLabelIds += f.addLabelIds
            body.removeLabelIds += f.removeLabelIds
            if not is_valid(body):
                raise LabelIntersectionError(body.addLabelIds, body.removeLabelIds)
        logger.debug(f'after collecting filters:')
        logger.debug(f'body={pf(body)}')
        body2 = self.sieve.body_ids_to_labels(body)
        logger.debug(f'body2={pf(body2)}')

        if self.thread.is_uptodate(body):
            logger.debug(f'thread is up to date, already has changes {pf(body2)}')
        else:
            logger.info(f'thread needs changes {pf(body2)}')
            try:
                self.sieve.threads_api.modify(userId='me', id=self.thread.id, body=body).execute()
                logger.info('completed successfullly')
            except HttpError as e:
                logger.info(f'Error executing actions={body} for thread_id={thread_id}')
                raise e

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
    def labels_to_ids(self):
        return {
            label['name']: label['id']
            for label
            in self.labels_api.list(userId='me').execute()['labels']
        }

    @property
    def ids_to_labels(self):
        return {
            label['id']: label['name']
            for label
            in self.labels_api.list(userId='me').execute()['labels']
        }

    def body_ids_to_labels(self, body):
        return Addict(
            addLabelIds=tuple(self.ids_to_labels[id] for id in body.addLabelIds),
            removeLabelIds=tuple(self.ids_to_labels[id] for id in body.removeLabelIds)
        )

    def auth(self, creds_json):
        creds = None
        creds_json = os.path.realpath(os.path.expanduser(creds_json))
        token_json = os.path.join(os.path.dirname(creds_json), '.token.json')
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

    def actions_to_label_ids(self, actions):
        body = Addict(removeLabelIds=[], addLabelIds=[])
        for action in actions:
            if action in REMOVE_ACTION_TO_LABEL:
                body.removeLabelIds += [REMOVE_ACTION_TO_LABEL[action]]
            elif action in ADD_ACTION_TO_LABEL:
                body.addLabelIds += [ADD_ACTION_TO_LABEL[action]]
            elif action in self.labels_to_ids:
                body.addLabelIds += [self.labels_to_ids[action]]
            else:
                try:
                    result = self.labels_api.create(userId='me', body={'name': action}).execute()
                    body.addLabelIds += [result['id']]
                except HttpError as e:
                    print(f'Error creating label="{action}"')
                    if e.resp.status == 409:
                        body.addLabelIds += [self.labels_to_ids[action]]
                    else:
                        raise e
        return body

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
        if cfg.spammers.sender:
            self.filters += [
                Filter(
                    name=f'spammer-{sender}',
                    sender=sender,
                    **self.actions_to_label_ids([
                        'archive',
                        f'_/{sender}',
                    ])
                )
                for sender
                in cfg.spammers.sender
            ]
        if cfg.spammers.fr:
            self.filters += [
                Filter(
                    name=f'spammer-{fr}',
                    fr=fr,
                    **self.actions_to_label_ids([
                        'archive',
                        f'_/{fr}',
                    ])
                )
                for fr
                in cfg.spammers.fr
            ]
        if cfg.spammers.to:
            self.filters += [
                Filter(
                    name=f'spammer-{to}',
                    to=to,
                    **self.actions_to_label_ids([
                        'archive',
                        f'_/{to}',
                    ])
                )
                for to
                in cfg.spammers.to
            ]
        if cfg.filters:
            self.filters += [
                Filter(
                    sieve=self,
                    name=name,
                    subject=body.get('subject'),
                    sender=body.get('sender'),
                    fr=tuplify(body.get('fr')),
                    to=body.get('to'),
                    cc=tuplify(body.get('cc')),
                    bcc=tuplify(body.get('bcc')),
                    precedence=body.get('precedence'),
                    **self.actions_to_label_ids(body.get('actions')),
                    headers={},
                )
                for name, body
                in [head_body(f) for f in cfg.filters]
            ]
        self.cfg = cfg

    def show_filters(self):
        pp([f.to_json() for f in self.filters])

    def filter_thread(self, thread):
        filters = []
        for f in self.filters:
            subject, sender, fr, to, cc, bcc = [True]*6
            if f.subject:
                subject = len(FuzzyList(thread.subjects).include(f.subject))
            if f.sender:
                sender = len(FuzzyList(thread.senders).include(f.sender))
            if f.fr:
                fr = any([FuzzyList(m.fr).include(*f.fr) for m in thread.messages])
            if f.to:
                to = any([FuzzyList(m.to).include(f.to) for m in thread.messages])
            if f.cc:
                cc = any([FuzzyList(m.cc).include(*f.cc) for m in thread.messages])
            if f.bcc:
                bcc = any([FuzzyList(m.bcc).include(*f.bcc) for m in thread.messages])
            if subject and sender and fr and to and cc and bcc:
                filters += [f]
                break #FIXME: should be able to apply multiple filters
        if filters:
            return [Change(self, thread, filters)]
        return []

    def filter_gmail(self):
        threads_req = self.threads_api.list(q=self.cfg.query, userId='me', maxResults=self.cfg.max_results)
        changes = []
        while threads_req:
            threads_res = threads_req.execute()
            threads = threads_res.get('threads', [])
            logger.info(f'len(threads)={len(threads)}')
            for thread in threads:
                thread = Thread(sieve=self, **self.threads_api.get(userId='me', id=thread['id'], format='metadata', metadataHeaders=METADATA_HEADERS).execute())
                changes += self.filter_thread(thread)
            ## keep searching until None
            threads_req = self.threads_api.list_next(threads_req, threads_res)
        return changes

    def execute_changes(self, changes):
        for change in changes:
            change.execute()
            logger.info('*'*80)

    def run(self):
        ppl(self.labels_to_ids)
        changes = self.filter_gmail()
        self.execute_changes(changes)

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

