import json
import dataset, sqlalchemy
import telepot
import time, arrow
import exceptions, traceback
import subprocess
import logging, logging.handlers
from urllib2 import urlopen
from commands import _start, _stop, _log, _subs, _yell
from chanapi import Board


def get_msg(msg):
    with open('messages/{0}'.format(msg), 'r') as f:
        msg = f.read()
        return msg

class Chanogram:
    def __init__(self,
                 api_token_file = 'api_token',
                 admin_id_file = 'admin_id',
                 settings = {'db_file': 'sqlite:///chanogram.db',
                             'board': 'pol',
                             'filter_list': ['edition', 'thread'],
                             'min_replies': 150,
                             'min_rpm': 5.0}):

        with open(admin_id_file, 'r') as f:
            self.admin_id = f.read()

        with open(api_token_file, 'r') as f:
            self.api_token = f.read()

        self.settings = settings

        self.db = dataset.connect(self.settings['db_file'],
                                  engine_kwargs={'poolclass':
                                                 sqlalchemy.pool.NullPool})

        logger = logging.getLogger('chanogram')
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter(\
                            '%(asctime)s - %(levelname)s - %(message)s')
        fh = logging.handlers.TimedRotatingFileHandler(\
                        'chanogram.log', when='H',interval=24,backupCount=7)
        ch = logging.StreamHandler()
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        logger.addHandler(fh)
        self.logger = logger

        self.bot = telepot.Bot(self.api_token)
        self.bot.message_loop(self.handle_input)
        deplmsg = 'Deployed with last update:\n{0}'.format(
                            subprocess.check_output('git log -1', shell=True))
        self.logger.info(deplmsg)
        self.bot.sendMessage(self.admin_id, deplmsg)


    def handle_input(self, msg):
        try:
            text = msg['text']
            if msg['chat']['type'] == 'group'\
               or msg['chat']['type'] == 'supergroup':
                from_id = str(msg['chat']['id'])
            else:
                from_id = str(msg['from']['id'])

            if text == '/start':
                    _start(self, from_id)

            elif text == '/stop':
                _stop(self, from_id)

            elif text == '/ping':
                self.bot.sendMessage(from_id, '''Pong.''')

            elif text == '/log' and from_id == self.admin_id:
                _log(self, self.admin_id)

            elif text == '/debug' and from_id == self.admin_id:
                _debug(self, self.admin_id)

            elif text == '/subs' and from_id == self.admin_id:
                _subs(self, self.admin_id)

            elif text.startswith('/yell ') and from_id == self.admin_id:
                _yell(self, text[len('/yell '):])


            else:
                if msg['chat']['type'] not in ['group', 'supergroup']:
                    self.bot.sendMessage(
                        from_id,
                        get_msg('commands_admin') if from_id == self.admin_id
                        else get_msg('commands_nonadmin'),
                        parse_mode='Markdown')
            self.logger.debug('Message handled from {0}: {1}'\
                              .format(from_id, text[:100]))
        except Exception as e:
            self.logger.error(e)



    def broadcast(self, msg):
        subs = [sub['from_id'] for sub in self.db['subscribers'].all()]
        successes = 0
        failures = 0
        for sub in subs:
            try:
                try:
                    self.bot.sendMessage(sub, msg, parse_mode='Markdown')
                    self.latest = msg
                    successes += 1
                except:
                    self.bot.sendMessage(sub, msg)
                    self.latest = msg
                    successes += 1
            except Exception as e:
                e = traceback.format_exc()
                self.logger.error('Failed to send message to {0}, '
                                  'got this error: {1}'.format(sub, e))
                failures += 1
        self.logger.info(
            'Broadcasted message to {0} subscribers ({1} failed): "{2}".'
            .format(successes,
                    failures,
                    msg[:100].replace('\n', ' // ')))

    def broadcast_photo(self, photo, ext, caption):
        subs = [sub['from_id'] for sub in self.db['subscribers'].all()]
        tpl = ('photo{0}'.format(ext), photo)
        successes = 0
        failures = 0
        for sub in subs:
            try:
                self.bot.sendPhoto(sub, tpl, caption=caption)
                successes += 1
            except Exception as e:
                e = traceback.format_exc()
                failures += 1
                self.logger.error('Failed to send message to {0}, '
                                  'got this error: {1}'.format(sub, e))
        self.logger.info(
            'Broadcasted photo to {0} subscribers ({1} failed): "{2}".'
            .format(successes,
                    failures,
                    caption[:100]))


    def run(self):
        try:
            self.logger.debug('Attempting a check operation...')
            try:
                history = [h['no'] for h in self.db['history'].all()]
            except Exception as e:
                e = traceback.format_exc()
                self.logger.debug(e)
                history = []
            b = Board(board = self.settings['board'],
                      filter_list = self.settings['filter_list'],
                      history=history,
                      sort='rpm',
                      reverse=True,
                      logger=self.logger)
            t = b.threads[0]

            if (float(t['replies']) > self.settings['min_replies']
                and t['rpm'] > self.settings['min_rpm']):
                self.broadcast(t['formatted'])
                now = arrow.now().format('YYYY-MM-DD HH:mm:ss')
                self.db['history'].insert(dict(no=str(t['no']), time=now))
            else:
                perc_rpm = "%.1f" % (t['rpm'] * 100 / self.settings['min_rpm'])
                perc_replies = (int(t['replies']) * 100 /
                                int(self.settings['min_replies']))
                self.logger.debug('No threads matching requirements, '
                             'closest at {0}/min ({1}%) with {2} posts ({3}%)'
                             ': "{4}"'\
                             .format(t['rpm'], perc_rpm,
                                     t['replies'], perc_replies,
                                     t['text'][:100]))
            self.logger.debug('...check operation complete.')
        except:
            e = traceback.format_exc()
            self.logger.error('Check operation failed with error: {0}'
                              .format(e))


c = Chanogram()
while True:
    c.run()
    time.sleep(30)
