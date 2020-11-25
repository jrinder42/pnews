import platform
import datetime
import random
import time
import subprocess
import json
import toml

import feedparser
import curses

import queue
import argparse
from typing import TypeVar

from screen import Screen



# cannot use .ini as config with ConfigParser because we want to change this


'''

need threading to get all of the recent stories

'''


class News(Screen):
    '''
    News class
    '''

    #Q = TypeVar('Q') # TODO - issue with this a compiling docs types

    def __init__(self, delay: int = 1, **kwargs) -> None:
        '''
        :param delay: sleep time after each story is printed
        :param kwargs: user defined arguments for the program
        '''

        super().__init__(**kwargs)

        # necessary data structures

        # dictionary containing urls and the most recent time
        self.urls_dict = {}
        self.current_stories = {}

        # time delay between website queries
        self.delay = delay # 1 second

        # stories q
        self.stories = queue.Queue()

        # init meta data
        self.meta = {}
        with open('src/meta.json') as f:
            self.meta = json.load(f)


    @staticmethod
    def init_urls() -> list:  # should be a proper getter, setter
        '''
        initializes urls to use

        :return: list of urls
        '''

        urls = []
        with open('src/news.json') as f:
            news = json.load(f)

        for site in news:
            urls += news[site]

        return urls


    def open_url(self, url: str, browser: str = 'chrome') -> None: # TODO - test this after push to github
        '''
        opens story in a browser

        :param url: story url to open
        :param browser: browser to open story in
        :return: nothing
        '''

        curses.def_prog_mode()
        curses.endwin()

        if platform.system() == 'Windows':
            # default subprocess.call(['start', url], shell=True)
            subprocess.call(['start', browser, url], shell=True)
        elif platform.system() == 'Linux':
            # default subprocess.call(['xdg-open', url], shell=True)
            subprocess.call(['google-chrome', url], shell=True) # firefox
        elif platform.system() == 'Darwin': # OSX
            # default subprocess.call(['open', url], shell=True)
            subprocess.call(['open', '-a', 'safari', url], shell=True) # 'Google Chrome'

        self.stdscr.refresh()  # this is curses.noutrefresh() + curses.doupdate()


    def change_params(self, *params) -> None:
        '''
        dynamically change variables based on user input

        :param params: dictionary of self-variables
        :return: nothing
        '''

        for key, value in params:
            self.__setattr__(key, value)


    @staticmethod
    def random_list(n: int) -> list:
        '''
        random list of integers in [1, n]

        :param n: number of elements in the random list
        :return: list in [1, n]
        '''

        return random.sample(range(1, n + 1), n)  # random.shuffle(lst)


    def show(self, window: Screen.cw, entry: dict, width: int = 80, color: int = 4) -> str:
        '''
        adds the story to the proper location on the screen

        :param window: curses window object
        :param entry: story dictionary metadata
        :param width: width that the story displays on the screen
        :param color: story display color
        :return: a string to help end the show function
        '''

        l = len(entry['title'])
        count = 0
        if l > width:
            start = 0
            while l > width:
                last = 0
                if ' ' in entry['title'][start:width + start]:
                    last = entry['title'][start:width + start][::-1].index(' ')
                if entry['title'][width + start - 1] == ' ':
                    last = 0
                y, x = window.getyx()
                if color == self.click_color:
                    y, x = entry['show_l'] + count, 0
                window.addstr(y, x, entry['title'][start:width + start - last] + '\n', curses.color_pair(color))
                start += width - last
                l -= width - last
                count += 1
            y, x = window.getyx()
            if color == self.click_color:
                y, x = entry['show_l'] + count, 0
            window.addstr(y, x, entry['title'][start:] + ' ' * (width - l), curses.color_pair(color))
        else:
            y, x = window.getyx()
            if color == self.click_color:
                y, x = entry['show_l'] + count, 0
            window.addstr(y, x, entry['title'] + ' ' * (width - l), curses.color_pair(color))
        return ''


    def print_story(self, pad: Screen.cw, entry: dict, width: int = 80) -> None: # TODO - make more efficient for next version
        '''
        story printed to the screen

        :param pad: curses window object
        :param entry: stores the link, original story range (lower, upper) and most recent story range
        :param width: how many characters to display on the screen per line
        :return: nothing
        '''

        # show story - compartmentalise this
        full, part = divmod(len(entry['title']), width)
        nlines = full + (1 if part > 0 else 0)

        # move curser to the top
        pad.move(0, 0)  # y, x -- y=0 means this is the top point of the pad window

        # insert line, moving everything else down 1 line
        for nl in range(nlines + 1):
            pad.insertln()

        # stdscr.addstr(recent['title'] + ' | ' + str(stdscr.getyx()) + '\n')
        pad.addstr(self.show(pad, entry) + '\n')
        y, x = pad.getyx()
        pad.addstr(y, 0, ' ' * width + '\n')
        self.pad_update(pad, self.my_pad_pos, 0)

        # this is inefficient, there has to be a better way to do this

        # if there are recent stories, slide them down the display
        if self.current_stories:
            for story in self.current_stories:
                if self.current_stories[story]:
                    self.current_stories[story] = {'l': self.current_stories[story]['l'] + nlines + 1,
                                                   'u': self.current_stories[story]['u'] + nlines + 1,
                                                   'title': self.current_stories[story]['title'],
                                                   'show_l': self.current_stories[story]['show_l'] + nlines + 1,
                                                   'show_u': self.current_stories[story]['show_u'] + nlines + 1}


        self.current_stories[entry['link']] = {'l': 0, 'u': nlines, 'title': entry['title'],
                                               'show_l': 0, 'show_u': nlines}  # inclusive

        # grab lines to delete
        to_delete = []
        for story in self.current_stories:
            #if self.current_stories[story] and self.current_stories[story]['u'] > self.display_buffer - 1: # TODO - original
            if self.current_stories[story] and self.current_stories[story]['u'] > self.buffer - 1:
                # del stories[story] # cannot change dictionary size during iteration
                to_delete.append(story)

        # delete old lines
        for bad_item in to_delete:
            del self.current_stories[bad_item]


    def is_new(self, entry: dict, url: str) -> bool:
        '''
        checks if a story is new

        :param entry: stores the link, original story range (lower, upper) and most recent story range
        :param url: story url to open
        :return: a boolean indicating if the story is new
        '''

        # check if a story is new
        website = self.meta[url.split('www.')[-1].split('.com')[0] + '.com']

        u = entry[website['time']]
        dt = datetime.datetime.strptime(u, website['date'])

        if url in self.urls_dict:
            if dt > self.urls_dict[url]['time']:
                self.urls_dict[url] = {'time': dt, 'entry': entry}
                return True
        else:
            self.urls_dict[url] = {'time': dt, 'entry': entry}
            return True
        return False


    def recent_story(self, entries: list, url: str) -> dict:
        '''
        most recent story

        :param entries: list of story metadata dictionaries
        :return: story dictionary
        '''
        recent = {'time': 0, 'entry': 0}

        website = self.meta[url.split('www.')[-1].split('.com')[0] + '.com']

        for entry in entries:
            u = entry[website['time']]
            dt = datetime.datetime.strptime(u, website['date'])

            if recent['time'] == 0 and recent['entry'] == 0:
                recent['time'] = dt
                recent['entry'] = entry
            else:
                if dt > recent['time']:
                    recent['time'] = dt
                    recent['entry'] = entry

        return recent['entry']


    #def end_nthreads(self, q: "queue.Queue['Q']") -> None: # https://bugs.python.org/issue33315
    def end_nthreads(self, q) -> None:
        '''
        :param q: current screen story queue
        :return: empty queue of items are still in it so the .join() function will work as intended
        '''

        # empty queue to help join with main thread
        while not q.empty():
            q.get()


    def run(self) -> None: # TODO - fix inefficeincy for next version
        '''
        print news stories to the screen as it comes in

        :return: nothing
        '''

        urls = self.init_urls()
        pause = False

        # use priority queue with 2 queues for the urls
        pq = queue.PriorityQueue()  # size of queue
        next_pq = queue.PriorityQueue()  # size of queue

        priority_list = self.random_list(len(urls))

        for i, url in enumerate(urls):
            pq.put((priority_list[i], url))

        start = time.time()
        while True:

            event = self.stdscr.getch()

            if event == ord('q') or event == ord('Q'):
                self.end_nthreads(pq)
                self.end_nthreads(next_pq)
                self.end_nthreads(self.stories)
                break


            elif event == curses.KEY_DOWN:
                if self.my_pad_pos < self.buffer:
                    self.my_pad_pos += 1

                    self.pad_update(self.story_pad, self.my_pad_pos, 0)

                    for story in self.current_stories:
                        self.current_stories[story]['l'] -= 1
                        self.current_stories[story]['u'] -= 1

            elif event == curses.KEY_UP:
                if self.my_pad_pos > 0:
                    self.my_pad_pos -= 1

                    self.pad_update(self.story_pad, self.my_pad_pos, 0)

                    for story in self.current_stories:
                        self.current_stories[story]['l'] += 1
                        self.current_stories[story]['u'] += 1

            elif event == ord(' '):  # space bar event
                if pause:
                    pause = False
                else:
                    pause = True

            elif event == curses.KEY_MOUSE: # story click
                _, mx, my, _, _ = curses.getmouse()

                # super inefficient --> should just be display[line_number] = story
                if mx < self.width and my < self.display_buffer + self.story_start:  # and my > self.story_start - 1:
                    for link, area in self.current_stories.items():
                        if area and ((my - self.story_start) >= area['l'] and (my - self.story_start) <= area['u']):

                            self.show(self.story_pad, area, width=self.width, color=5)
                            self.pad_update(self.story_pad, self.my_pad_pos, 0)

                            self.open_url(link)


            if not pause:
                # grab website content
                _, url = pq.get()

                d = feedparser.parse(url) # time and memory bottleneck in the program, 0.2 - 1 second

                # assume the top entry is the most recent
                entry = self.recent_story(d.entries, url)
                #entry = d.entries[0]
                if self.is_new(entry, url):
                    if url not in self.stories.queue:
                        self.stories.put(url) # will only show the most recent story for each url


                next_pq.put((priority_list[next_pq.qsize()], url))

                if pq.empty():
                    random.shuffle(priority_list)
                    pq, next_pq = next_pq, pq

                if time.time() - start >= self.delay:
                    # print story if one is available
                    if self.stories.qsize() > 0:
                        current_url = self.stories.get()
                        story = [self.story_pad, self.urls_dict[current_url]['entry'], self.width]
                        self.print_story(*story)
                    start = time.time()


def main() -> None:
    '''
    :return: handle optional program arguments based on the config.toml file in the src/ folder
    '''

    # init config data
    with open('src/config.toml') as f:
        config = toml.load(f)

    parser = argparse.ArgumentParser(description='process news program arguments')

    colors = {'black': curses.COLOR_BLACK, 'blue': curses.COLOR_BLUE, 'green': curses.COLOR_GREEN,
              'red': curses.COLOR_RED, 'white': curses.COLOR_WHITE, 'yellow': curses.COLOR_YELLOW,
              'cyan': curses.COLOR_CYAN, 'magenta': curses.COLOR_MAGENTA}
    parser.add_argument('--click_color', help='story color after user clicks a story',
                        default=config['click_color'], type=int, choices=list(colors.keys()))
    parser.add_argument('--story_color', help='story color when it is printed to the cli',
                        default=config['story_color'], type=int, choices=list(colors.keys()))
    parser.add_argument('--news_file', help='text file that contains the websites to parse',
                        default=config['news_file'], type=str)
    parser.add_argument('--meta_file', help='metadata file that contains information about each website',
                        default=config['meta_file'], type=str)
    parser.add_argument('--width', help='width of each story title on the cli',
                        default=config['width'], type=int, choices=list(range(1, curses.COLS)))
    parser.add_argument('--delay', help='delay between each story being output to the cli in seconds',
                        default=config['delay'], type=float)
    parser.add_argument('--buffer', help='number of story lines to store in the display buffer',
                        default=config['buffer'], type=int)
    parser.add_argument('--display_buffer', help='number of story lines to appear on the cli',
                        default=config['display_buffer'], type=int) # change choices
    parser.add_argument('--browser', help='browser to open the stories in',
                        default=config['browser'], type=str, choices=['chrome', 'safari', 'edge', 'firefox'])
    parser.add_argument('--topic', help='stories about this specific topic',
                        default=config['topic'], type=str)

    args = parser.parse_args()

    news = News(**vars(args))
    news.run()



if __name__ == '__main__':

    import tracemalloc
    tracemalloc.start()

    main()

    current, peak = tracemalloc.get_traced_memory()
    print(f"Current memory usage is {current / 10 ** 6}MB; Peak was {peak / 10 ** 6}MB")
    tracemalloc.stop()








