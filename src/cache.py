import os
import time
import pickle

import log
import logging


class Cache:
    all_url = set()

    def __init__(self, cache_path='./data/cache', interval_s=60):
        self.cache_path = cache_path
        self.interval = 60
        self._running = True

    def terminate(self):
        self._running = False

    def restart(self):
        self._running = True

    def run(self):
        while self._running:
            time.sleep(self.interval)
            self.dump()

    def load(self, path=None):
        if path is None:
            path = self.cache_path

        if os.path.exists(path):
            with open(path, 'rb') as file:
                self.all_url = pickle.load(file)

    def dump(self, path=None):
        if path is None:
            path = self.cache_path
        with open(path, 'wb') as file:
            logging.info(f'Dumping url num={len(self.all_url)}')
            pickle.dump(self.all_url, file)
