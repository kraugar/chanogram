import json
from urllib2 import urlopen
from BeautifulSoup import BeautifulSoup
from dateutil.relativedelta import relativedelta
from HTMLParser import HTMLParser
from datetime import datetime

class Board:
    def __init__(self,
                 board='pol',
                 filter_list=[],
                 sort='rpm',
                 reverse=True,
                 logger=None):
        self.board = board
        self.filter_list = filter_list
        self.sort = sort
        self.reverse = reverse
        self.logger = logger
        self.threads = []

        api = urlopen('https://a.4cdn.org/{0}/catalog.json'\
                           .format(self.board)).read()
        api = json.loads(api)
        if self.logger:
            self.logger.debug('Got API file for /{0}/.'
                              .format(self.board))

        for page in api:
            for thread in page['threads']:
                self.threads.append(self.prep_thread(thread))
        self.remove_read_threads()
        self.filter_threads()
        self.threads.sort(key=lambda t: t[self.sort], reverse = self.reverse)

        if self.logger:
            self.logger.debug(
                'Finally arrived at {0} threads from board /{1}/ .'
                .format(len(self.threads), self.board))


    def remove_read_threads(self):
        try:
            history = [h['no'] for h in self.db['history'].all()]
        except:
            history = []
        unread = [t for t in self.threads if t['no'] not in history]

        if self.logger:
            self.logger.debug('Removed {0} threads already broadcasted.'
                              .format(len(self.threads) - len(unread)))
        self.threads = unread


    def filter_threads(self):
        i = 0
        r = 0
        threads = self.threads
        while i < len(threads):
            if 'sub' in threads[i]\
            and any(w in threads[i]['sub'].lower() for w in self.filter_list):
                del threads[i]
                r = r + 1
            else:
                i = i + 1
        if self.logger:
            self.logger.debug('Removed {0} threads matching filter list.'
                              .format(r))
        self.threads = threads


    def prep_thread(self, thread):
        # board, url, no ###
        thread['board'] = self.board
        thread['url'] = 'http://boards.4chan.org/{0}/thread/{1}'\
                        .format(self.board, thread['no'])
        thread['no'] = str(thread['no'])
        ####################

        # text ############
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
        ###################

        # age_s ###########
        thread['age_s'] = (datetime.now() -
                        datetime.fromtimestamp(thread['time'])).seconds
        ###################

        # age_hm ##########
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
        ###################

        # rpm #############
        thread['rpm'] = float("%.1f" % (float(thread['replies']) * 60/
                                        float(thread['age_s'])))
        ###################

        thread['formatted'] =(
            '*{0}/min ({1}r in {2})*\n{3}\n\n(from {4})\n{5}'
            .format(thread['rpm'],
                    thread['replies'],
                    thread['age_hm'],
                    thread['text'],
                    thread['country_name'],
                    thread['url']))

        return thread
