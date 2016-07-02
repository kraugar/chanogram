import json
import sqlite3
import telepot
import time
import logging
from dateutil.relativedelta import relativedelta
from BeautifulSoup import BeautifulSoup
from HTMLParser import HTMLParser
from datetime import datetime
from urllib2 import urlopen

logging.basicConfig(filename='chanogram.log',
                    level=logging.INFO,
                    filemode='w',
                    format='%(asctime)s %(levelname)s %(message)s')

class Chanogram:
    def __init__(self, api_token_file = 'api_token.txt', db_file = 'chanogram.db',
                 settings = {'board': 'pol',
                             'filter_list': ['edition',],
                             'min_replies': 0,
                             'min_rpm': 0}):
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
        logging.debug('Chanogram database init complete.')

        self.settings = settings
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
        if list_name == 'subscribers':
            logging.info('New subscriber with ID {0}'.format(entry))
        else:
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
        if list_name == 'subscribers':
            logging.info('User with ID {0} unsubscribed.'.format(entry))
        else:
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
        from_id = msg['from']['id']
        text = msg['text']
        logging.debug('Attempting to handle message from {0}: "{1}"...'\
                      .format(from_id, text[:20]))


        if text == '/start':
            if str(from_id) in self.list_get('subscribers'):
                self.bot.sendMessage(from_id, '''You are *already subscribed*.\n_Use_ /stop _if you want to unsubscribe._''', parse_mode='Markdown')
            else:
                self.list_add('subscribers', from_id)
                if len(self.settings['filter_list']) > 1:
                    plural_handler = 's'
                else:
                    plural_handler = ''
                self.bot.sendMessage(from_id, '''You have *subscribed*.\n\nYou will receive a *notification* if a *thread* on 4chan's /{0}/ board is attracting *lots of responses in a short time*.\n\nCurrently, a notification is triggered when a thread attracts *more than {1} replies per minute* and does not have the following keyword{2}: "{3}".\n_(since those threads usually aren't related to breaking news but attract lots of replies per minute because of regular posters)_\n\n_Use_ /stop _to unsubscribe._'''\
                .format(self.settings['board'],
                        str(self.settings['min_rpm']),
                        plural_handler,
                        ', '.join(self.settings['filter_list'])),
                parse_mode='Markdown')


        elif text == '/stop':
            if str(from_id) in self.list_get('subscribers'):
                self.list_del('subscribers', from_id)
                self.bot.sendMessage(from_id, '''You have *unsubscribed*.\n_Use_ /start _to subscribe again._''', parse_mode='Markdown')
            else:
                self.bot.sendMessage(from_id, '''You are *already unsubscribed*.\n_Use_ /start _to subscribe again._''', parse_mode='Markdown')


        else:
            self.bot.sendMessage(from_id, 'I *only* know the following commands:\n/start _to subscribe_\n/stop _to unsubscribe._', parse_mode='Markdown')
        logging.debug('Message handled.')


    def broadcast(self, msg):
        logging.debug('Attempting to broadcast message: "{0}"...'.format(msg[:20]))
        subs = self.list_get('subscribers')
        for sub in subs:
            self.bot.sendMessage(sub, msg)
        logging.info('Broadcasted message to {0} subscribers: "{1}".'\
                     .format(len(subs), msg[:20]))


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
                        thread['age_hm'] ='{0}:{1}h'.format(age.hours,age.minutes)
                    else:
                        thread['age_hm'] ='{0}:0{1}h'.format(age.hours,age.minutes)
                else:
                    thread['age_hm'] = '{0}min'.format(age.minutes)

                thread['rpm'] = float("%.1f" % (float(thread['replies']) * 60.0 /
                                                float(thread['age_s'])))

                threads.append(thread)

        threads.sort(key=lambda t: t['rpm'],reverse = True)
        logging.debug('Loaded and processed {0} threads from /{1}/ board.'\
            .format(len(threads), self.settings['board']))

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
        logging.debug('Got {0} threads from board /{1}/ .'\
                      .format(len(threads), self.settings['board']))
        return threads


    def run(self):
        try:
            logging.debug('Attempting a check operation...')
            threads = self.get_threads()
            t = threads[0]

            if float(t['replies']) > self.settings['min_replies'] and\
               t['rpm'] > self.settings['min_rpm']:
                if t['id'] not in self.list_get('broadcast_history'):
                    self.broadcast(str(t['text'])[:200])
                    self.list_add('broadcast_history', str(t['id']))
                else:
                    logging.debug('Already broadcasted message: {0}'\
                                  .format(t['id']))
            else:
                percentage = "%.1f" % (t['rpm'] * 100 / self.settings['min_rpm'])
                logging.debug('No hot threads, closest at {0}/min ({1}%): "{2}"'\
                    .format(t['rpm'], percentage, t['text'][:30]))
            logging.debug('Check operation complete.')
        except:
            logging.error('Check operation failed.')


c = Chanogram()
while True:
    c.run()
    time.sleep(30)
