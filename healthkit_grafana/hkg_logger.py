import datetime
import logging
from logging.handlers import RotatingFileHandler
import os
import sys

LOGGER = logging.getLogger(__name__)
env_level = os.environ.get('LOG_LEVEL', "INFO")
level = logging.getLevelName(env_level)
LOGGER.setLevel(level)

DEFAULT_LOG_NAME = os.path.splitext(
    os.path.basename(sys.argv[0])
)[0]

fh = RotatingFileHandler('%s.log' % DEFAULT_LOG_NAME,
                         maxBytes=10000000,
                         backupCount=3)
fh.setLevel(level)

ch = logging.StreamHandler()
ch.setLevel(level)

formatter = logging.Formatter(
    fmt='time=%(created)f level=%(levelname)s ' 
    'method=%(funcName)s:%(lineno)s msg="%(message)s"',
    datefmt='%d-%b-%Y %H:%M:%S %z %Z')

fh.setFormatter(formatter)
ch.setFormatter(formatter)
LOGGER.addHandler(fh)
LOGGER.addHandler(ch)
