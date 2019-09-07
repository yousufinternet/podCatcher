#!/usr/bin/env python

from collections import defaultdict
from datetime import datetime
from time import mktime
import pandas as pd
import feedparser
import subprocess
import argparse
import urllib
import pipes
import os
import re


class podCatcher:

    USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.230 Safari/537.36"

    def __init__(self):
        # TODO : more download methods
        parser = argparse.ArgumentParser(
            prog='PodCatcher',
            description='List and download podcasts',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Examples:
    # update local versions of remote feeds
    podcatcher --update-cache

    # list the latest episode for all podcasts
    podcatcher --latest

    # list the latest episode for podcast1 and podcast2
    podcatcher --latest podcast1 podcast2

    # list episodes from all podcasts after 01-01-2019
    podcatcher --after 01-01-2019

    # download episodes published after 01-01-2019 from podcast1 and podcast2
    podcatcher --download --after 01-01-2019 podcast1 podcast2

    # download episode 5 from podcast3
    podcatcher --download --exact-episode 5 podcast3

    # download the first ten episodes from podcast4
    podcatcher --download --before-episode 10 podcast4

    # list all episodes from all podcasts matching the regex '.*apple.*'
    podcatcher --list --regex '.*apple.*'
            """)
        self.parser = parser

        # self explanatory options
        self.actions = ['list', 'download', 'update-cache']  # TODO play action
        # TODO option to filter already played episodes
        self.podcasts = ['all', 'latest']  # ,'unplayed']

        # make this options mutually exclusive
        command_group = parser.add_mutually_exclusive_group()
        select_group = parser.add_mutually_exclusive_group()
        for action in self.actions:
            command_group.add_argument('--'+action, action='store_true')
        for selection in self.podcasts:
            select_group.add_argument('--'+selection, action='store_true')

        parser.add_argument('--regex', help='filter episodes using a regex')

        # filters by date
        parser.add_argument(
            '--after', type=lambda x: datetime.strptime(x, '%d-%m-%Y').date(),
            help='Episodes after a certain date only format:d-m-Y')
        parser.add_argument(
            '--before', type=lambda x: datetime.strptime(x, '%d-%m-%Y').date(),
            help='Episodes before a certain date only format:d-m-Y')
        parser.add_argument('--exact-episode', type=int,
                            help='episode number you would like to download')
        parser.add_argument('--after-episode', type=int,
                            help='only download episodes carrying a number'
                            ' larger than the provided')
        parser.add_argument('--before-episode', type=int,
                            help='only download episodes carrying a number'
                            ' smaller than the provided')

        parser.add_argument(
            '--config', help='path to config file, by default'
            ' config are read from ~/.config/podcatcher/urls',
            type=lambda x: os.path.abspath(x),
            default=os.path.expanduser('~/.config/podcatcher/urls'))

        parser.add_argument(
            'podcast_names', nargs='*',
            help='Put here names of podcasts -as defined in your '
            'config file- to apply actions to them')

        self.args = parser.parse_args()
        self.prepare_args()
        if self.args.update_cache:
            self.cache_feeds()
        else:
            self.grab_episodes()
            self.apply_action()

    def prepare_args(self):
        if not os.path.exists(self.args.config):
            raise FileNotFoundError(
                'Could not find the config file specified')

        # before should not be before after argument!
        if not any(date is None for date in
                   (self.args.before, self.args.after)):
            if self.args.before < self.args.after:
                self.parser.error("before date can't be before the after date!")

        # Errors accompanied with episode flags
        either_afterbefore_on = any(ep is not None for ep in
                                    (self.args.before_episode,
                                     self.args.after_episode))
        any_epflag = any(ep is not None for ep in
                         (self.args.before_episode, self.args.after_episode,
                          self.args.exact_episode))
        if self.args.latest and any_epflag:
            self.parser.error("Can't use latest flag with any of episode "
                              "range flags")
        if self.args.exact_episode is not None and either_afterbefore_on:
            self.parser.error('You can\'t pass exact-episode with either'
                              ' before and after episode flags')
        if all(ep is not None for ep in (self.args.before_episode,
                                         self.args.after_episode)):
            if self.args.after_episode > self.args.before_episode:
                self.parser.error('after-episode can\'t be larger than'
                                  ' before-episode')

        # all podcasts by default
        if len([s for s in self.podcasts if getattr(self.args, s)]) == 0:
            self.args.all = True

        # list by default
        if len([s for s in self.actions if getattr(
                self.args, s.replace('-', '_'))]) == 0:
            self.args.list = True

        self.urls_df = pd.read_csv(self.args.config)

        if len(self.args.podcast_names) == 0:
            self.args.podcast_names = self.urls_df.Name.tolist()

        bad_pods = [pod for pod in self.args.podcast_names
                    if pod not in self.urls_df.Name.tolist()]
        if len(bad_pods) > 0:
            raise ValueError(
                f'podcasts: {", ".join(bad_pods)} not defined in urls file')

    def cache_feeds(self):
        '''
        store feeds locally
        '''
        urls_df_fil = self.urls_df[self.urls_df.Name.isin(
            self.args.podcast_names)]
        print('Please wait while feeds are being cached')
        header = {}
        header['User-Agent'] = self.USER_AGENT
        for row in urls_df_fil.iterrows():
            pod_name = row[1].Name
            pod_url = row[1].url
            req = urllib.request.Request(pod_url, headers=header)
            response = urllib.request.urlopen(req)
            response_str = response.read().decode('utf-8')
            response_store_path = os.path.join(
                os.path.split(self.args.config)[0], 'Cache', pod_name)
            with open(response_store_path, 'w+') as f_obj:
                f_obj.write(response_str)

    def grab_episodes(self):
        '''
        read feeds files and filter episodes according to options
        '''
        urls_df_fil = self.urls_df[self.urls_df.Name.isin(
            self.args.podcast_names)]
        self.results = defaultdict(lambda: pd.DataFrame())
        for row in urls_df_fil.iterrows():
            pod_name = row[1].Name
            pod_cache_path = os.path.join(
                os.path.split(self.args.config)[0], 'Cache', pod_name)
            feed_dict = feedparser.parse(pod_cache_path)
            for i, episode in enumerate(feed_dict.entries):
                ep_no = len(feed_dict.entries)-i  # episode number
                title = episode.title

                # if we only need the latest
                latest_flag = False
                if self.args.latest and i > 0:
                    latest_flag = True

                # filter by episode number
                if self.args.exact_episode is not None:
                    if ep_no != self.args.exact_episode:
                        continue
                if self.args.after_episode is not None:
                    if ep_no < self.args.after_episode:
                        continue
                if self.args.before_episode is not None:
                    if ep_no > self.args.before_episode:
                        continue

                # filter episodes by date
                date = datetime.fromtimestamp(mktime(episode.published_parsed))
                date = date.date()  # just so our line is shorter than 80 chars
                if self.args.after is not None:
                    if date < self.args.after:
                        continue
                if self.args.before is not None:
                    if date >= self.args.before:
                        continue
                if self.args.regex is not None:
                    if not re.match(self.args.regex, title,
                                    flags=re.IGNORECASE):
                        continue
                if latest_flag:
                    break
                for link in episode.links:
                    if link['type'] != 'text/html':
                        audio_link = link.href
                        break
                epd_dict = {'Title': title, 'Date': date, 'Link': audio_link}
                self.results[pod_name] = self.results[pod_name].append(
                    pd.DataFrame(epd_dict, index=[ep_no]))

    def apply_action(self):
        if self.args.download:
            urls = []
            for pod_name in self.args.podcast_names:
                for row in self.results[pod_name].iterrows():
                    ep_no = row[0]
                    date = row[1].Date
                    title = row[1].Title
                    url = row[1].Link
                    destination = os.path.expanduser(f'~/Podcasts/{pod_name}')
                    output_file = f'#{ep_no} {title}-{date.strftime("%d-%m-%Y")}.mp3'
                    urls.append(url)
                    urls.append(f'  dir={destination}')
                    urls.append(f'  out={output_file}')

            with open('temp_urls', 'w+') as f_obj:
                # for some reason writelines does not write each item on
                # a separate line
                for line in urls:
                    f_obj.write(line + '\n')
            # TODO : add the ability to add options to aria2c command
            download_cmd = ('aria2c --max-concurrent-downloads=3 '
                            '--continue=true --check-integrity=true --split=5 '
                            '--input-file=temp_urls --deferred-input=true'
                            ' --file-allocation=falloc')
            subprocess.Popen(download_cmd, shell=True)
        elif self.args.list:
            for pod_name in self.args.podcast_names:
                print('\nShowing epsiodes for', pod_name, ':')
                for row in self.results[pod_name].iterrows():
                    ep_no = row[0]
                    date = row[1].Date
                    title = row[1].Title
                    url = row[1].Link
                    print(f'Episode #{ep_no}:', date.strftime('%d-%m-%Y'),
                          title)


if __name__ == '__main__':
    podcatcher = podCatcher()
