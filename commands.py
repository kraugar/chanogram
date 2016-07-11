import arrow
import subprocess
import time

def _start(self, from_id):
    if from_id in [sub['from_id'] for sub in self.db['subscribers'].all()]:
        reply = get_msg('already_subscribed')
        self.bot.sendMessage(from_id, reply, parse_mode='Markdown')

    else:
        now = arrow.now().format('YYYY-MM-DD HH:mm:ss')
        self.db['subscribers'].insert(dict(from_id=from_id, time=now))
        reply = get_msg('subscribed').format(
            self.settings['board'],
            str(self.settings['min_rpm']),
            str(self.settings['min_replies']),
            's' if len(self.settings['filter_list']) > 1 else '',
            '; '.join(self.settings['filter_list']))
        self.bot.sendMessage(from_id,
                             reply,
                             parse_mode='Markdown')
        self.logger.info('User with ID {0} subscribed.'.format(from_id))


def _stop(self, from_id):
    if from_id in [sub['from_id'] for sub in self.db['subscribers'].all()]:
        self.db['subscribers'].delete(from_id=from_id)
        self.bot.sendMessage(from_id,
                             get_msg('unsubscribed'),
                             parse_mode='Markdown')
        self.logger.info('User with ID {0} unsubscribed.'.format(from_id))

    else:
        self.bot.sendMessage(from_id,
                             get_msg('already_unsubscribed'),
                             parse_mode='Markdown')


def _log(self, admin_id):
    logtail = subprocess.check_output('tail -n 50 chanogram.log',
                                     shell=True)
    self.bot.sendMessage(admin_id, logtail[-4000:].replace('\n','\n\n'))

def _subs(self, admin_id):
    subs = [sub['from_id'] for sub in self.db['subscribers'].all()]
    reply =  ('''List of {0} subscribers:\n{1}'''
              .format(len(subs), '\n'.join(subs)))
    self.bot.sendMessage(admin_id, reply, parse_mode='Markdown')

def _yell(self, text):
    self.broadcast(text)
