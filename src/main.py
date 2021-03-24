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

import cache


class YOUGETDownloader:

    def __init__(self, path='./output', debug=False, caption=True, playlist=False, **kwargs):
        self.output_dir = path
        self.debug = debug
        self.caption = caption
        self.playlist = playlist
        self._running = True

    def exit(self):
        self._running = False

    def __call__(self, url, wait_s=0, dry_run=False):
        if not self._running:
            return
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
            ret = subprocess.run(command, shell=True, timeout=300)
            ret = ret.returncode
        logging.info(f'Get ret code {ret}')
        return ret


CACHE = cache.Cache()
downloader_mapping = {
    'you-get': YOUGETDownloader,
}
LOG_FORMAT = "%(levelname)s:%(asctime)s:%(name)s[%(filename)s:%(lineno)s]:%(message)s"
DATE_FORMAT = "%Y-%m-%d[%H:%M:%S]"


class Agent:

    def __init__(self, name, website, downloader, token='', thread_num=1, max_retry=3, wait_s=0, enable=True,
                 intervals=600, **kwargs):
        self.name = name
        self.url = get_code(website, token)
        self.executor = ThreadPoolExecutor(max_workers=thread_num)
        self.downloader = downloader_mapping[downloader['name']](**downloader)
        self.enable = enable
        self.wait = wait_s
        self.max_retry = max_retry
        self.intervals = intervals
        self._running = True

    def loop(self):
        while self._running:
            logging.info(f'Agent {self.name} is working.')
            self.run()
            time.sleep(self.intervals)
        logging.info(f'Agent {self.name} is exiting.')

    def exit(self):
        self._running = False
        self.downloader.exit()
        self.executor.shutdown()
        logging.info(f"Agent {self.name} is shut.")

    def run(self):
        if not self.enable:
            logging.warning(f"{self.name} enable is {self.enable!s}.")
            return

        feed_url = self.url
        max_reties = self.max_retry
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
            else:
                logging.info(f"Processing {link}")
                future_result.put((link, 1, self.executor.submit(self.downloader, link, self.wait)))

        while not future_result.empty():
            link, retry, future = future_result.get()
            future = list(concurrent.futures.as_completed([future]))[0]
            result = future.result()
            if self._running is False:
                return
            if result == 0:
                logging.info(f"Finish {link} in {retry} times")
                CACHE.all_url.add(link)
            else:
                logging.warning(f"Task {link} retry {retry} get result {result}")
                if retry < max_reties:
                    logging.info(f"Retry {link} ...")
                    future_result.put((link, retry + 1, self.executor.submit(self.downloader, link, retry * self.wait)))
                else:
                    logging.error(f'Retry {link} {retry} times. All are failed. Please try manually.')


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
    parser.add_argument('--log', type=str, default='./data/log.txt')
    parser.add_argument('-i', '--input', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT, datefmt=DATE_FORMAT)

    import json
    agents = []
    agent_threads = []
    with open(args.config, 'r') as config:
        config = json.load(config)
        for agent_config in config['agents']:
            agents.append(Agent(**agent_config))

    CACHE.cache_path = args.cache
    CACHE.load()
    cache_t = threading.Thread(target=CACHE.run)
    cache_t.start()

    for agent in agents:
        agent_threads.append(threading.Thread(target=agent.loop))

    for agent_thread in agent_threads:
        agent_thread.start()

    if args.input:
        while True:
            cmd = input(">>")
            if cmd == 'e':
                logging.info("Exiting...")
                break

        for agent in agents:
            agent.exit()

        CACHE.terminate()
        CACHE.dump()

        logging.info("Waiting all thread done.")


if __name__ == '__main__':
    main()
