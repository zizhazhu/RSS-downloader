import os
import time
import queue
import logging
import subprocess
import threading
import concurrent
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests
import feedparser

import log
import cache


class TwitterDownloader:

    def __init__(self, output_dir='./output'):
        self.output_dir = output_dir

    def __call__(self, url):
        ret = subprocess.run(f"you-get -d -o {self.output_dir} {url}", shell=True)


class YOUGETDownloader:

    def __init__(self, path='./output', debug=False, caption=True, playlist=False, **kwargs):
        self.output_dir = path
        self.debug = debug
        self.caption = caption
        self.playlist = playlist

    def __call__(self, url, wait_s=0, dry_run=False):
        if not os.path.exists(self.output_dir):
            os.mkdir(self.output_dir)
        time.sleep(wait_s)
        flags = []
        if self.debug:
            flags.append("-d")
        if self.playlist:
            flags.append("--playlist")
        if not self.caption:
            flags.append("--no-caption")
        command = f"you-get {' '.join(flags)} -o {self.output_dir} {url}"
        logging.info(f'Running {command}')
        if dry_run:
            ret = 0
        else:
            ret = subprocess.run(command, shell=True)
            ret = ret.returncode
        logging.info(f'Get ret code {ret}')
        return ret


CACHE = cache.Cache()
downloader_mapping = {
    'you-get': YOUGETDownloader,
}


class Agent:

    def __init__(self, name, website, downloader, token='', enable=True, **kwargs):
        self.name = name
        self.url = get_code(website, token)
        self.downloader = downloader_mapping[downloader['name']](**downloader)
        self.enable = enable

    def run(self, executor=None):
        if not self.enable:
            logging.warning(f"{self.name} enable is {self.enable!s}.")
            return

        feed_url = self.url
        max_reties = 3
        retry = 1
        while retry <= max_reties:
            try:
                logging.info(f"try get feed={feed_url} {retry}<={max_reties} times")
                xml = requests.request('GET', feed_url)
            except requests.exceptions.ConnectionError as e:
                logging.warning(f"Get feed={feed_url} Error({e}), wait 10 secs")
                time.sleep(retry * 10)
                retry += 1
            else:
                break
        else:
            logging.error(f"Can't get feed={feed_url}")
            return
        feed = feedparser.parse(xml.text)
        entries = feed.entries
        logging.info(f"{len(entries)} rss")

        future_result = queue.Queue()
        for entry in entries:
            link = entry.link
            if link in CACHE.all_url:
                logging.debug(f"Ignore {link}, because exists")
            logging.info(f"Processing {link}")
            if executor is None:
                if self.downloader:
                    self.downloader(link)
                    CACHE.all_url.add(link)
            else:
                future_result.put((link, 0, executor.submit(self.downloader, link)))

        while not future_result.empty():
            link, retry, future = future_result.get()
            future = list(concurrent.futures.as_completed([future]))[0]
            result = future.result()
            if result == 0:
                logging.info(f"Finish {link} in {retry} times")
                CACHE.all_url.add(link)
            else:
                logging.warning(f"Task {link} retry {retry} get result {result}")
                if retry < max_reties:
                    logging.info(f"Retry {link}...")
                    future_result.put((link, retry + 1, executor.submit(self.downloader, link, (retry + 1) * 10)))


def get_code(url, token=''):
    parse_url = urlparse(url)
    route = parse_url.path
    if token != '':
        import hashlib
        md5 = hashlib.md5()
        before = route + token
        md5.update(before.encode('UTF-8'))
        code = md5.hexdigest()
        result = f"{url}?code={code}"
    else:
        result = url
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default='./config/agents.json')
    parser.add_argument('--cache', type=str, default='./data/cache')
    args = parser.parse_args()

    CACHE.cache_path = args.cache
    CACHE.load()
    cache_t = threading.Thread(target=CACHE.run)
    cache_t.start()

    import json
    agents = []
    with open(args.config, 'r') as config:
        config = json.load(config)
        for agent_config in config['agents']:
            agents.append(Agent(**agent_config))

    download_executor = ThreadPoolExecutor(max_workers=config.get('thread_num', 5))

    for agent in agents:
        agent.run(download_executor)

    CACHE.terminate()
    CACHE.dump()

    logging.info("Waiting all thread done.")


if __name__ == '__main__':
    main()

