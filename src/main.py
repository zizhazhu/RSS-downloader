import os
import time
import pickle
import logging

import you_get
import requests
import feedparser


LOG_FORMAT = "%(levelname)s:%(asctime)s:%(name)s[%(filename)s:%(lineno)s]:%(message)s"
DATE_FORMAT = "%Y-%m-%d[%H:%M:%S]"


def get_code(website, path='/', token=''):
    import hashlib
    md5 = hashlib.md5()
    before = path + token
    md5.update(before.encode('UTF-8'))
    code = md5.hexdigest()
    return f"{website}{path}?code={code}"


def main(url, token):
    if os.path.exists('./data/cache'):
        with open('./data/cache', 'rb') as file:
            all_url = pickle.load(file)
    else:
        all_url = set()

    import json
    with open('./data/config.json', 'r') as file:
        json_file = json.load(file)
    website = json_file['website']
    feed_url = get_code(website, url, token)
    max_reties = 3
    retry = 1
    while retry <= max_reties:
        try:
            logging.info(f"try get feed={feed_url} {retry}<={max_reties} times")
            xml = requests.request('GET', feed_url)
        except requests.exceptions.ConnectionError as e:
            logging.warning(f"Get feed={feed_url} Error({e}), wait 10 secs")
            time.sleep(10)
            retry += 1
            continue
        else:
            break
    else:
        logging.error(f"Can't get feed={feed_url}")
        return

    feed = feedparser.parse(xml.text)
    entries = feed.entries
    logging.info(f"{len(entries)} rss")

    for entry in entries:
        link = entry.link
        if link in all_url:
            logging.debug(f"Ignore {link}, because exists")
        logging.info(f"Processing {link}")
        all_url.add(entry.link)

    with open('./data/cache', 'wb') as file:
        pickle.dump(all_url, file)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('url', type=str)
    parser.add_argument('token', type=str)
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT, datefmt=DATE_FORMAT)
    main(args.url, args.token)
