import os
import json


import uuid
import re
import time
import datetime
import calendar
import redis

REDIS_HOST = os.getenv('CHAT_REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('CHAT_REDIS_PORT', 6379)
REDIS_DB = os.getenv('CHAT_REDIS_DB', 0)

# some sanity checks
REDIS_CONNECTION = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
REDIS_CONNECTION.ping()
