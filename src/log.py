import logging

LOG_FORMAT = "%(levelname)s:%(asctime)s:%(name)s[%(filename)s:%(lineno)s]:%(message)s"
DATE_FORMAT = "%Y-%m-%d[%H:%M:%S]"

logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT, datefmt=DATE_FORMAT)
