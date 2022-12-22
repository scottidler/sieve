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

## https://googleapis.github.io/google-api-python-client/docs/dyn/gmail_v1.users.html

import os
import re
import sys
sys.dont_write_bytecode = True

import json
import signal
import asyncio
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from addict import Addict
from ruamel import yaml
from argparse import ArgumentParser
from itertools import chain
from functools import lru_cache, wraps
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from leatherman.fuzzy import FuzzyList
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

loop = asyncio.new_event_loop()

class LabelIntersectionError(Exception):
    def __init__(self, addLabelIds, removeLabelIds):
        msg = f'error: addLabelIds={addLabelIds} and removeLabelIds={removeLabelIds} intersect'
        super().__init__(msg)

class SieveYmlNotFoundError(Exception):
    def __init__(self, sieve_yml):
        msg = f'error: sieve_yml={sieve_yml} not found'
        super().__init__(msg)

def auth(creds_json):
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
    return creds

def is_sequence(obj):
    return isinstance(obj, (set, list, tuple))

def asyncify(func):
    '''
    turns a sync function into an async function, using threads
    '''
    pool = ThreadPoolExecutor(1)

    @wraps(func)
    def wrapper(*args, **kwargs):
        future = pool.submit(func, *args, **kwargs)
        return asyncio.wrap_future(future)
    return wrapper

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

    def __repr__(self):
        return f'Message(id={self.id})'

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
            header['name'].lower():header['value']
            for header
            in self.payload.headers
        }

class Thread:
    def __init__(self, sieve, id, messages, historyId=None, snippet=None):
        self.id = id
        self.sieve = sieve
        self.messages = [Message(thread=self, **message) for message in messages]
        self.historyId = historyId
        self.snippet = snippet

    def __repr__(self):
        return f'Thread(id={self.id}, messages={self.messages}, historyId={self.historyId}, snippet={self.snippet})'

    __str__ = __repr__

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

    @property
    def message_ids(self):
        return [m.id for m in self.messages]

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
    def __init__(self, name=None, actions=None, **headers):
        self.name = name
        self.actions = tuplify(actions)
        self.headers = {
            h: tuplify(v) if h in ('fr', 'cc', 'bcc') else v
            for h, v
            in headers.items()
        }

    __repr__ = __repr__

    def to_json(self):
        return {
            'name': self.name,
            'actions': self.actions,
            'headers': self.headers,
        }

class Labels:
    def __init__(self, add=None, remove=None):
        self.add = add or {}
        self.remove = remove or {}

    def __hash__(self):
        items = tuple(self.add.items()) + tuple(self.remove.items())
        return hash(items)

    def __eq__(self, other):
        if isinstance(other, Labels):
            return self.add == other.add and self.remove == other.remove
        return False

    def __bool__(self):
        if len(self.add) or len(self.remove):
            return True
        return False

    def __repr__(self):
        return f'Lables(add={self.add_names}, remove={self.remove_names})'

    def __add__(self, other):
        result = Labels(
            add=dict(self.add, **other.add),
            remove=dict(self.remove, **other.remove),
        )
        if intersect(result.add.keys(), result.remove.keys()):
            raise LabelIntersectionError(result.add_names, result.remove_names)
        return result

    @property
    def add_ids(self):
        return tuplify(list(self.add.keys()))

    @property
    def remove_ids(self):
        return tuplify(list(self.remove.keys()))

    @property
    def add_names(self):
        return tuplify(list(self.add.values()))

    @property
    def remove_names(self):
        return tuplify(list(self.remove.values()))

    def to_json(self):
        return dict(
            addLabelIds=self.add_ids,
            removeLabelIds=self.remove_ids,
        )

class Change:
    def __init__(self, sieve, labels, message_ids):
        self.sieve = sieve
        self.labels = labels
        self.message_ids = message_ids

    def __repr__(self):
        return f'Change(lables={self.labels}, message_ids={len(self.message_ids)})'

    @asyncify
    def execute_batch(self, batch):
        logger.debug(f'execute_batch: labels={self.labels} len(batch)={len(batch)}')
        body = dict(
            ids=batch,
            **self.labels.to_json())
        result = self.sieve.messages_api.batchModify(userId='me', body=body).execute()
        logger.debug(f'execute_batch: result={result}')
        return [result]

    async def execute(self):
        def batch_by(items, count):
            if items:
                if len(items) > count:
                    return items[:count], items[1000:]
                return items, []
            return [], []
        results = []
        batch, rem = batch_by(self.message_ids, 1000)
        while batch:
            results += await self.execute_batch(batch)
            batch, rem = batch_by(rem, 1000)
        return results

class Spec:
    def __init__(self, name, sieve, query, filters, max_results=500):
        self.name = name or 'unnamed'
        self.sieve = sieve
        self.query = query
        self.filters = filters
        self.max_results = max_results
        self.default = None

    def to_json(self):
        return  dict(
            name=self.name,
            query=self.query,
            filters=[f.to_json() for f in self.filters],
        )

    __repr__ = __repr__

    __str__ = __repr__

    @asyncify
    def get_threads_ids(self, query=None, max_results=None):
        threads_req = self.sieve.threads_api.list(userId='me', q=query, maxResults=max_results)
        thread_ids = []
        while threads_req:
            threads_res = threads_req.execute()
            threads = threads_res.get('threads', [])
            logger.debug(f'len(threads)={len(threads)}')
            thread_ids += [thread['id'] for thread in threads]
            threads_req = self.sieve.threads_api.list_next(threads_req, threads_res)
        return thread_ids

    async def filter_thread(self, thread, filters):
        labels = Labels()
        for f in filters:
            if not f.headers: #if no headers, apply filter
                labels += self.sieve.actions_to_labels(f.actions)
                continue
            matches = [False] * len(f.headers)
            for i, (h, v) in enumerate(f.headers.items()):
                if h not in thread.headers:
                    break
                if h in ('subject', 'sender'):
                    matches[i] = len(FuzzyList(thread.headers[h]).include(v)) > 0
                elif is_sequence(v):
                    matches[i] = any([FuzzyList(m.headers[h]).include(*v) for m in thread.messages])
                else:
                    matches[i] = any([FuzzyList(m.headers[h]).include(v) for m in thread.messages])
            if all(matches):
                labels += self.sieve.actions_to_lables(f.actions)
        if labels:
            return (labels, thread.message_ids)
        elif self.default:
            return (self.sieve.actions_to_labels(self.default.actions), thread.message_ids)
        return (None, [])

    @asyncify
    def hydrate_thread(self, thread_id):
        logger.debug(f'hydrating thread_id={thread_id}')
        return Thread(sieve=self.sieve, **self.sieve.threads_api.get(userId='me', id=thread_id, format='metadata', metadataHeaders=METADATA_HEADERS).execute())

    async def filter_gmail(self, thread_ids, filters):
        work = {}
        work = defaultdict(list)
        for thread_id in thread_ids:
            thread = await self.hydrate_thread(thread_id)
            labels, message_ids = await self.filter_thread(thread, filters)
            if labels:
                work[labels].extend(message_ids)

        print(f'len(work.keys())={len(work.keys())}')
        return [
            Change(self.sieve, labels, message_ids)
            for labels, message_ids
            in work.items()
        ]

    async def execute_changes(self, changes):
        for change in changes:
            await change.execute()
            logger.info('*'*80)

    async def run(self):
        logger.info(f'name={self.name} query={self.query} max_results={self.max_results}')
        thread_ids = await self.get_threads_ids(query=self.query, max_results=self.max_results)
        logger.info(f'len(thread_ids)={len(thread_ids)}')
        changes = await self.filter_gmail(thread_ids, self.filters)
        logger.info(f'len(changes)={len(changes)}')
        await self.execute_changes(changes)

class Sieve:
    def __init__(self, creds_json, sieve_yml, **kwargs):
        creds = auth(creds_json)
        self.gmail = build('gmail', 'v1', credentials=creds)
        self.profile = self.gmail.users().getProfile(userId='me').execute()
        self.labels_api = self.gmail.users().labels()
        self.threads_api = self.gmail.users().threads()
        self.messages_api = self.gmail.users().messages()
        self.directory = build('admin', 'directory_v1', credentials=creds)
        self.groups_api = self.directory.groups()
        self.load_yml(sieve_yml)

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

    def label_ids_to_names(self, body):
        return Addict(
            addLabelIds=tuple(self.ids_to_labels[id] for id in body.addLabelIds),
            removeLabelIds=tuple(self.ids_to_labels[id] for id in body.removeLabelIds)
        )

    def actions_to_labels(self, actions):
        add = {}
        remove = {}
        for action in actions:
            if action in REMOVE_ACTION_TO_LABEL:
                label_id = REMOVE_ACTION_TO_LABEL[action]
                remove[label_id] = label_id
            elif action in ADD_ACTION_TO_LABEL:
                label_id = ADD_ACTION_TO_LABEL[action]
                add[label_id] = label_id
            elif action in self.labels_to_ids:
                label_id = self.labels_to_ids[action]
                add[label_id] = action
            else:
                try:
                    result = self.labels_api.create(userId='me', body={'name': action}).execute()
                    label_id = result['id']
                    add[label_id] = action
                except HttpError as e:
                    print(f'Error creating label="{action}"')
                    if e.resp.status == 409:
                        label_id = self.labels_to_ids[action]
                        add[label_id] = action
                    else:
                        raise e
        return Labels(add, remove)

    def load_spammer(self, label, *items):
        return [
            Filter(
                name=f'spammer-{label}',
                **{label: item},
                actions=[
                    'archive',
                    f'_/{item}',
                ])
            for item
            in items
        ]

    def load_filter(self, name, actions=None, **headers):
        assert actions != None, 'actions cannot be None'
        return Filter(
            name,
            **headers,
            actions=actions or []
        )

    def load_spec(self, name, query=None, spammers=None, filters=None):
        assert spammers != None or filters != None
        filters_ = []
        if spammers:
            filters_ += list(chain(*[
                self.load_spammer(name, *body)
                for name, body
                in spammers.items()
            ]))
        if filters:
            filters_ += [
                self.load_filter(name, **body)
                for name, body
                in filters.items()
            ]
        return Spec(name, self, query, filters_)

    def load_yml(self, sieve_yml):
        sieve_yml = os.path.expanduser(sieve_yml)
        if not os.path.exists(sieve_yml):
            raise SieveYmlNotFoundError(sieve_yml)
        docs = yaml.safe_load_all(open(sieve_yml))
        self.specs = [self.load_spec(**doc) for doc in docs]

    def show_filters(self):
        pp([w.to_json() for w in self.specs])


    async def run(self):
        for spec in self.specs:
            await spec.run()

async def main(args):
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
        await sieve.run()

async def _signal_handler():
    try:
        tasks = asyncio.all_tasks(loop)
        for task in tasks:
            task.cancel()
    except RuntimeError as err:
        print('SIGINT or SIGTSTP raised')
        print("cleaning and exiting")
        sys.exit(1)

if __name__ == '__main__':
    def signal_handler(*args):
        loop.create_task(_signal_handler())

    signal.signal(signal.SIGINT, signal_handler)

    loop.run_until_complete(main(sys.argv[1:]))