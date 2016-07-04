import json
import sqlite3
import telepot
import time
import subprocess
import logging
import exceptions
from dateutil.relativedelta import relativedelta
from BeautifulSoup import BeautifulSoup
from HTMLParser import HTMLParser
from datetime import datetime
from urllib2 import urlopen

with open('admin_id') as f:
    admin_id = f.read()

logging.basicConfig(filename='chanogram.log',
                    level=logging.DEBUG,
                    filemode='w',
                    format='%(asctime)s %(levelname)s %(message)s')

class Chanogram:
    def __init__(self,
                 api_token_file = 'api_token.txt',
                 db_file = 'chanogram.db',
                 settings = {'board': 'pol',
                             'filter_list': ['edition', 'thread'],
                             'min_replies': 100,
                             'min_rpm': 4.4}):

        logging.debug('Attempting to init Chanogram instance...')
        with open(api_token_file, 'r') as f:
            self.api_token = f.read()
        self.bot = telepot.Bot(self.api_token)
        self.bot.message_loop(self.handle_input)

        logging.debug('Attempting to init Chanogram database...')
        self.db_file = db_file
        self.conn = sqlite3.connect(self.db_file)
        self.c = self.conn.cursor()
        self.c.execute(\
        "CREATE TABLE IF NOT EXISTS subscribers (entry TEXT UNIQUE)")
        self.c.execute(\
        "CREATE TABLE IF NOT EXISTS broadcast_history (entry TEXT UNIQUE)")
        self.conn.commit()
        self.conn.close()

        self.settings = settings

        last_commit = subprocess.check_output('git log -1', shell=True)
        global admin_id
        self.bot.sendMessage(admin_id,
                             'Deployed with last update:\n{0}'\
                             .format(last_commit))
        logging.info('Chanogram instance init complete.')


    def list_add(self, list_name, entry):
        logging.debug('Attempting to add {0} to list {1}...'\
                      .format(entry, list_name))
        self.conn = sqlite3.connect(self.db_file)
        self.c = self.conn.cursor()
        self.c.execute(\
        "INSERT OR IGNORE INTO {0} VALUES ('{1}')".format(list_name, entry))
        self.conn.commit()
        self.conn.close()
        logging.debug('Added {0} to list {1}.'.format(entry, list_name))


    def list_del(self, list_name, entry):
        logging.debug('Attempting to delete {0} from list {1}...'\
                      .format(entry, list_name))
        self.conn = sqlite3.connect(self.db_file)
        self.c = self.conn.cursor()
        self.c.execute(\
        "DELETE FROM {0} WHERE entry='{1}'".format(list_name, entry))
        self.conn.commit()
        self.conn.close()
        logging.debug('Deleted {0} from list {1}.'.format(entry, list_name))


    def list_get(self, list_name):
        logging.debug('Attempting to get list {0}...'.format(list_name))
        self.conn = sqlite3.connect(self.db_file)
        self.c = self.conn.cursor()
        entries = []
        for e in self.c.execute("SELECT * FROM {0}".format(list_name)):
            entries.append(e[0])
        self.conn.close()
        logging.debug('Got list {0}.'.format(list_name))
        return entries


    def handle_input(self, msg):
        global admin_id
        from_id = str(msg['from']['id'])
        text = msg['text']
        logging.debug('Attempting to handle message from {0}: "{1}"...'\
                      .format(from_id, text[:20]))


        if text == '/start':
            self._start(from_id)


        elif text == '/stop':
            self._stop(from_id)


        elif text == '/ping':
            self.bot.sendMessage(from_id, '''Pong.''')

        elif text == '/log' and from_id == admin_id:
            self._log(admin_id)

        elif text == '/debug' and from_id == admin_id:
            self._debug(admin_id)

        elif text == '/subs' and from_id == admin_id:
            self._subs(admin_id)


        else:
            if from_id == admin_id:
                reply =\
'''These are all available commands including your admin commands:
/start to _subscribe,_
/stop to _unsubscribe,_
/ping to _receive a pong_,
/log to _receive the latest logging entries_,
/subs to _receive a list of subscribers_.'''
                self.bot.sendMessage(from_id, reply, parse_mode='Markdown')
            else:
                reply =\
'''I *only* know the following commands:
/start to _subscribe,_
/stop to _unsubscribe,_
/ping to _receive a pong_.'''
                self.bot.sendMessage(from_id, reply, parse_mode='Markdown')

        logging.debug('Message handled from {0}: {1}'\
                      .format(from_id, text[:40]))


    def _start(self, from_id):
        if str(from_id) in self.list_get('subscribers'):
            reply = \
'''You are *already subscribed*.
_Use_ /stop _if you want to unsubscribe._'''
            self.bot.sendMessage(from_id, reply, parse_mode='Markdown')

        else:
            self.list_add('subscribers', from_id)
            if len(self.settings['filter_list']) > 1:
                plural_handler = 's'
            else:
                plural_handler = ''
            reply = \
'''You have *subscribed*.

You will receive a *notification* if a *thread* on 4chan's /{0}/ board is attracting *lots of responses in a short time*.

Currently, a notification is triggered when a thread attracts *more than {1} replies per minute*, has *at least {2} replies* and does not have the following keyword{3}: *{4}* _(since those threads usually aren't related to breaking news but attract lots of replies per minute because of regular posters)._

_Use_ /stop _to unsubscribe._'''\
                .format(self.settings['board'],
                        str(self.settings['min_rpm']),
                        str(self.settings['min_replies']),
                        plural_handler,
                        '; '.join(self.settings['filter_list']))
            self.bot.sendMessage(from_id, reply, parse_mode='Markdown')
            logging.info('User with ID {0} subscribed.'.format(from_id))


    def _stop(self, from_id):
        if str(from_id) in self.list_get('subscribers'):
            self.list_del('subscribers', from_id)
            self.bot.sendMessage(from_id,
'''You have *unsubscribed*.
_Use_ /start _to subscribe again._''',
                                 parse_mode='Markdown')
            logging.info('User with ID {0} unsubscribed.'.format(from_id))

        else:
            self.bot.sendMessage(from_id,
'''You are *already unsubscribed*.
_Use_ /start _to subscribe again._''',
                                 parse_mode='Markdown')


    def _log(self, admin_id):
        loglevel = logging.getLogger().getEffectiveLevel()
        if loglevel == 10:
            lines = 100
        else:
            lines = 20
        logtail = subprocess.check_output('tail -n {0} chanogram.log'\
                                          .format(lines),
                                          shell=True)
        self.bot.sendMessage(admin_id, logtail[-4000:].replace('\n','\n\n'))
        logging.debug(\
                      'Sent logtail to admin with ID {0}.'\
                      .format(admin_id))


    def _debug(self, admin_id):
        logging.getLogger().setLevel(logging.DEBUG)
        reply =\
'DEBUG MODE ENABLED for up to 30 seconds. Use /log to check the output.'
        self.bot.sendMessage(admin_id, reply)


    def _subs(self, admin_id):
        subs = self.list_get('subscribers')
        if len(subs) > 1:
            plural_handler = '''Currently there are {0} subscribers:\n{1}'''
        else:
            plural_handler = '''Currently there is one subscriber: {1}'''
        reply = plural_handler.format(len(subs), '\n'.join(subs))
        self.bot.sendMessage(admin_id, reply, parse_mode='Markdown')
        logging.debug(\
            'Sent subscribers list with {0} entries to admin with ID {1}.'\
            .format(len(subs), admin_id))


    def broadcast(self, msg):
        logging.debug('Attempting to broadcast message: "{0}"...'\
                      .format(msg[:40]))
        subs = self.list_get('subscribers')
        for sub in subs:
            self.bot.sendMessage(sub, msg, parse_mode='Markdown')
        logging.info('Broadcasted message to {0} subscribers: "{1}".'\
                     .format(len(subs), msg[:40]))


    def get_threads(self):
        logging.debug('Attempting to get API file for /{0}/ board...'
                      .format(self.settings['board']))
        api_file = urlopen('https://a.4cdn.org/{0}/catalog.json'\
                           .format(self.settings['board'])).read()
      #  with open('catalog.json', 'r') as f:
     #       api_file = f.read()
        api_json = json.loads(api_file)
        logging.debug('Got API file.')

        logging.debug('Attempting to process threads...')
        threads = []
        for page in api_json:
            for thread in page['threads']:
                thread['board'] = self.settings['board']
                thread['url'] = 'http://boards.4chan.org/{0}/thread/{1}'\
                                .format(self.settings['board'], thread['no'])

                thread['text'] = 'No text available'
                if 'name' in thread:
                    thread['text'] = thread['name']
                if 'sub' in thread:
                    thread['text'] = thread['sub']
                if 'com' in thread:
                    thread['text'] = thread['com']
                s = BeautifulSoup(thread['text']).getText()
                pars = HTMLParser()
                s = pars.unescape(s)
                thread['text'] = s.encode('utf8')

                thread['age_s'] = (datetime.now() -
                                datetime.fromtimestamp(thread['time'])).seconds

                age = relativedelta(datetime.now(),
                                    datetime.fromtimestamp(thread['time']))
                if age.hours:
                    if age.minutes > 9:
                        thread['age_hm'] ='{0}:{1}h'\
                            .format(age.hours, age.minutes)
                    else:
                        thread['age_hm'] ='{0}:0{1}h'\
                            .format(age.hours,age.minutes)
                else:
                    thread['age_hm'] = '{0}min'.format(age.minutes)

                thread['rpm'] = float("%.1f" % (float(thread['replies']) * 60.0/
                                                float(thread['age_s'])))

                threads.append(thread)

        logging.debug('Attempting to remove read threads...')
        unread = []
        read = self.list_get('broadcast_history')
        for thread in threads:
            if thread['id'] not in read:
                unread.append(thread)
        logging.debug('Removed {0} read threads.'\
                      .format(len(threads) - len(unread)))
        threads = unread

        logging.debug('Attempting to filter threads...')
        i = 0
        r = 0
        words = self.settings['filter_list']
        while i < len(threads):
            if 'sub' in threads[i]\
            and any(w in threads[i]['sub'].lower() for w in words):
                del threads[i]
                r = r + 1
            else:
                i = i + 1
        logging.debug('Filtered out {0} threads.'.format(r))

        threads.sort(key=lambda t: t['rpm'],reverse = True)

        logging.debug('Finally arrived at {0} threads from board /{1}/ .'\
                      .format(len(threads), self.settings['board']))
        return threads


    def format_thread(self, thread):
        logging.debug('Formatting thread...')
        thread = '*{0}/min ({1}r in {2})*\n{3}\n\n(from {4})\n{5}'\
                 .format(thread['rpm'],
                         thread['replies'],
                         thread['age_hm'],
                         thread['text'],
                         thread['country_name'],
                         thread['url'])
        logging.debug('Thread formatted.')
        return thread


    def run(self):
        try:
            logging.debug('Attempting a check operation...')
            threads = self.get_threads()
            t = threads[0]

            if float(t['replies']) > self.settings['min_replies'] and\
               t['rpm'] > self.settings['min_rpm']:
                if t['id'] not in self.list_get('broadcast_history'):
                    formatted_thread = self.format_thread(t)
                    self.broadcast(formatted_thread)
                    self.list_add('broadcast_history', str(t['id']))
                else:
                    logging.debug('Already broadcasted message: {0}'\
                                  .format(t['id']))
            else:
                percentage = "%.1f" % (t['rpm'] * 100 /
                                       self.settings['min_rpm'])
                logging.debug('No threads matching requirements, closest at {0}/min ({1}%): "{2}"'.format(t['rpm'], percentage, t['text'][:30]))
            logging.debug('Check operation complete.')
        except exceptions.Exception as e:
            print e
            logging.error('Check operation failed with error: ', e)


c = Chanogram()
while True:
    c.run()
    time.sleep(30)
    logging.getLogger().setLevel(logging.INFO)
