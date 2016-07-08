import json
import sqlite3
import telepot
import time
import subprocess
import logging, logging.handlers
import exceptions
from dateutil.relativedelta import relativedelta
from BeautifulSoup import BeautifulSoup
from HTMLParser import HTMLParser
from datetime import datetime
from urllib2 import urlopen
with open('admin_id') as f:
    admin_id = f.read()

logger = logging.getLogger('chanogram')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(\
            '%(asctime)s - %(levelname)s - %(message)s')
fhd = logging.handlers.TimedRotatingFileHandler(\
     'logs/chanogram-debug.log', when='H',interval=24,backupCount=7)
fhi = logging.handlers.TimedRotatingFileHandler(\
     'logs/chanogram-info.log', when='H',interval=24,backupCount=7)
ch = logging.StreamHandler()
fhd.setLevel(logging.DEBUG)
fhd.setFormatter(formatter)
fhi.setLevel(logging.INFO)
fhi.setFormatter(formatter)
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)
logger.addHandler(fhd)
logger.addHandler(fhi)


class Chanogram:
    def __init__(self,
                 api_token_file = 'api_token.txt',
                 db_file = 'chanogram.db',
                 settings = {'board': 'pol',
                             'filter_list': ['edition', 'thread'],
                             'min_replies': 100,
                             'min_rpm': 4.4}):

        logger.debug('Attempting to init Chanogram instance...')
        with open(api_token_file, 'r') as f:
            self.api_token = f.read()
        self.bot = telepot.Bot(self.api_token)
        self.bot.message_loop(self.handle_input)

        logger.debug('Attempting to init Chanogram database...')
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
        self.latest = 'No latest thread yet, wait a bit and try again.'

        last_commit = subprocess.check_output('git log -1', shell=True)
        global admin_id
        self.bot.sendMessage(admin_id,
                             'Deployed with last update:\n{0}'\
                             .format(last_commit))
        logger.debug('Chanogram instance init complete.')


    def list_add(self, list_name, entry):
        logger.debug('Attempting to add {0} to list {1}...'\
                      .format(entry, list_name))
        self.conn = sqlite3.connect(self.db_file)
        self.c = self.conn.cursor()
        self.c.execute(\
        "INSERT OR IGNORE INTO {0} VALUES ('{1}')".format(list_name, entry))
        self.conn.commit()
        self.conn.close()
        logger.debug('Added {0} to list {1}.'.format(entry, list_name))


    def list_del(self, list_name, entry):
        logger.debug('Attempting to delete {0} from list {1}...'\
                      .format(entry, list_name))
        self.conn = sqlite3.connect(self.db_file)
        self.c = self.conn.cursor()
        self.c.execute(\
        "DELETE FROM {0} WHERE entry='{1}'".format(list_name, entry))
        self.conn.commit()
        self.conn.close()
        logger.debug('Deleted {0} from list {1}.'.format(entry, list_name))


    def list_get(self, list_name):
        logger.debug('Attempting to get list {0}...'.format(list_name))
        self.conn = sqlite3.connect(self.db_file)
        self.c = self.conn.cursor()
        entries = []
        for e in self.c.execute("SELECT * FROM {0}".format(list_name)):
            entries.append(str(e[0]))
        self.conn.close()
        logger.debug('Got list {0} with {1} entries, last being: {2}.'
                     .format(list_name,
                             len(entries),
                             ', '.join(entries[-5:])))
        return entries


    def handle_input(self, msg):
        global admin_id
        if msg['chat']['type'] == 'group'\
           or msg['chat']['type'] == 'supergroup':
            from_id = msg['chat']['id']
        else:
            from_id = str(msg['from']['id'])
        text = msg['text']
        logger.debug('Attempting to handle message from {0}: "{1}"...'\
                      .format(from_id, text[:20]))


        if text == '/start':
                self._start(from_id)

        elif text == '/stop':
            self._stop(from_id)

        elif text == '/ping':
            self.bot.sendMessage(from_id, '''Pong.''')

        elif text == '/top':
            self._top(from_id)

        elif text == '/log' and from_id == admin_id:
            self._log(admin_id)

        elif text == '/debug' and from_id == admin_id:
            self._debug(admin_id)

        elif text == '/subs' and from_id == admin_id:
            self._subs(admin_id)

        elif text.startswith('/broadcast_manually ') and from_id == admin_id:
            text = text[len('/broadcast_manually '):]
            self._broadcast_manually(text)


        else:
            if msg['chat']['type'] == 'group'\
             or msg['chat']['type'] == 'supergroup':
                pass
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
/top to receive _most popular thread right now_,
/ping to _receive a pong_.'''
                    self.bot.sendMessage(from_id, reply, parse_mode='Markdown')

        logger.debug('Message handled from {0}: {1}'\
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

Currently, a notification is triggered when a thread:
1. attracts more than *{1} replies per minute*,
2. has at least *{2} total replies* and
3. does not have the following keyword{3} in the subject: *{4}* _(since those threads usually aren't related to breaking news but attract lots of replies per minute because of regular posters)._

_Use_ /stop _to unsubscribe._'''\
                .format(self.settings['board'],
                        str(self.settings['min_rpm']),
                        str(self.settings['min_replies']),
                        plural_handler,
                        '; '.join(self.settings['filter_list']))
            self.bot.sendMessage(from_id, reply, parse_mode='Markdown')
            logger.info('User with ID {0} subscribed.'.format(from_id))


    def _stop(self, from_id):
        if str(from_id) in self.list_get('subscribers'):
            self.list_del('subscribers', from_id)
            self.bot.sendMessage(from_id,
'''You have *unsubscribed*.
_Use_ /start _to subscribe again._''',
                                 parse_mode='Markdown')
            logger.info('User with ID {0} unsubscribed.'.format(from_id))

        else:
            self.bot.sendMessage(from_id,
'''You are *already unsubscribed*.
_Use_ /start _to subscribe again._''',
                                 parse_mode='Markdown')

    def _top(self, from_id):
        try:
            self.bot.sendMessage(from_id, self.latest)
            logger.info('Sent latest to {0}.'.format(from_id))
        except:
            logger.error('Error sending latest to {0}.'.format(from_id))

    def _log(self, admin_id):
        logtail = subprocess.check_output('tail -n 50 logs/chanogram-debug.log',
                                          shell=True)
        self.bot.sendMessage(admin_id, logtail[-4000:].replace('\n','\n\n'))
        time.sleep(0.5)
        logtail = subprocess.check_output('tail -n 50 logs/chanogram-info.log',
                                          shell=True)
        self.bot.sendMessage(admin_id, logtail[-4000:].replace('\n','\n\n'))

    def _subs(self, admin_id):
        subs = self.list_get('subscribers')
        if len(subs) > 1:
            plural_handler = '''Currently there are {0} subscribers:\n{1}'''
        elif len(subs) == 1:
            plural_handler = '''Currently there is one subscriber: {1}'''
        else:
            plural_handler = '''Currently there are no subscribers.'''
        reply = plural_handler.format(len(subs), '\n'.join(subs))
        self.bot.sendMessage(admin_id, reply, parse_mode='Markdown')

    def _broadcast_manually(self, text):
        subs = self.list_get('subscribers')
        for sub in subs:
            self.bot.sendMessage(sub, text)


    def broadcast(self, msg):
        subs = self.list_get('subscribers')
        for sub in subs:
            try:
                try:
                    self.bot.sendMessage(sub, msg, parse_mode='Markdown')
                    self.latest = msg
                except:
                    self.bot.sendMessage(sub, msg)
                    self.latest = msg
            except Exception as e:
                logger.error('Failed to send message to {0}, '
                             'got this error: {1}'.format(sub, e))
        logger.info('BROADCASTED message to {0} subscribers: "{1}".'\
                     .format(len(subs), msg[:40]))


    def get_threads(self):
        api_file = urlopen('https://a.4cdn.org/{0}/catalog.json'\
                           .format(self.settings['board'])).read()
      #  with open('catalog.json', 'r') as f:
     #       api_file = f.read()
        api_json = json.loads(api_file)
        logger.debug('Got API file for /{0}/.'.format(self.settings['board']))

        threads = []
        for page in api_json:
            for thread in page['threads']:
                thread['board'] = self.settings['board']
                thread['url'] = 'http://boards.4chan.org/{0}/thread/{1}'\
                                .format(self.settings['board'], thread['no'])
                thread['no'] = str(thread['no'])

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

        unread = []
        read = self.list_get('broadcast_history')
        for thread in threads:
            if thread['no'] not in read:
                unread.append(thread)
        logger.debug('Removed {0} threads already broadcasted.'\
                      .format(len(threads) - len(unread)))
        threads = unread

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
        logger.debug('Removed {0} threads matching filter list.'.format(r))

        threads.sort(key=lambda t: t['rpm'],reverse = True)

        logger.debug('Finally arrived at {0} threads from board /{1}/ .'\
                      .format(len(threads), self.settings['board']))
        return threads


    def format_thread(self, thread):
        thread = '*{0}/min ({1}r in {2})*\n{3}\n\n(from {4})\n{5}'\
                 .format(thread['rpm'],
                         thread['replies'],
                         thread['age_hm'],
                         thread['text'],
                         thread['country_name'],
                         thread['url'])
        logger.debug('Thread formatted.')
        return thread


    def run(self):
        try:
            logger.debug('-> Attempting a check operation...')
            threads = self.get_threads()
            t = threads[0]

            if float(t['replies']) > self.settings['min_replies'] and\
               t['rpm'] > self.settings['min_rpm']:
                formatted_thread = self.format_thread(t)
                self.broadcast(formatted_thread)
                self.list_add('broadcast_history', t['no'])
            else:
                perc_rpm = "%.1f" % (t['rpm'] * 100 / self.settings['min_rpm'])
                perc_replies = (int(t['replies']) * 100 /
                                int(self.settings['min_replies']))
                logger.debug('No threads matching requirements, '
                             'closest at {0}/min ({1}%) with {2} posts ({3}%)'
                             ': "{4}"'\
                             .format(t['rpm'], perc_rpm,
                                     t['replies'], perc_replies,
                                     t['text'][:30]))
            logger.debug('-> Check operation complete.')
        except exceptions.Exception as e:
            print e
            logger.error('!!! Check operation failed with error: ', e)


c = Chanogram()
while True:
    c.run()
    time.sleep(30)
