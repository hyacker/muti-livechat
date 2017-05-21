import os
import json


import uuid
import re
import time
import datetime
import calendar
import redis
import config

MAX_ROOM = 100
MAX_USER_PER_ROOM = 100
config.REDIS_CONNECTION.set('live-chat-sys-max-room',MAX_ROOM)
config.REDIS_CONNECTION.set('live-chat-sys-max-room-users',MAX_USER_PER_ROOM)
