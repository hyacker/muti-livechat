#from __future__ import print_function
# coding=UTF-8

# General modules.
import os, os.path
import uuid
import logging
import re
import json
import argparse
import struct
import sys
import time
from threading import Timer
import string
import random

# Tornado modules.
import tornado.auth
import tornado.options
import tornado.escape

####

import tornado.httpserver
import tornado.web
import tornado.websocket
import tornado.ioloop
import tornado.gen
from tornado.util import bytes_type
from tornado.iostream import StreamClosedError
###
import tornadoredis
import redis
# Import application modules.
from base import BaseHandler
from auth import LoginHandler
from auth import LogoutHandler

MAX_ROOMS = 100
MAX_USERS_PER_ROOM = 3

singleclient = tornadoredis.Client()
singleclient.connect()

class RoomHandler(object):

    def __init__(self):

        # Create a Redis connection.
        self.redis_cli = redis_connect('redis')

    def add_room(self, room,nick):
        """Add nick to room. Return generated client_id"""
        room_info = self.redis_cli.smembers('members-rooms')
        if not room in room_info:
            if len(room_info) > MAX_ROOMS:
                log.error("MAX_ROOMS_REACHED")
                return -1
            self.redis_cli.sadd('members-rooms',room)
            log.debug("ADD_ROOM - ROOM_NAME:%s" % room)


        log.info("room name %s" % (room_info))
        room_user = self.redis_cli.smembers('members-%s-users' % (room))

        if room in room_info :
            if len(room_user) >= MAX_USERS_PER_ROOM:
                log.error("MAX_USERS_PER_ROOM_REACHED")
                return -2
        roomvalid = re.match(r'[\w-]+$', room)
        nickvalid = re.match(r'[\w-]+$', nick)
        if roomvalid == None:
            log.error("INVALID_ROOM_NAME - ROOM:%s" % (room,))
            return -3
        if nickvalid == None:
            return -4
            log.error("INVALID_NICK_NAME - NICK:%s" % (nick,))
        client_id = uuid.uuid4().int  # generate a client id.
        self.redis_cli.set('%s-%s' % (client_id,'room'),room)

        c = 1
        name = nick
        nicks = self.nicks_in_room(room)
        while True:
            if name in nicks:
                name = nick + str(c)
            else:
                break
            c += 1
        self.redis_cli.set('%s-%s' % (client_id,'nick'),name)
        self.redis_cli.sadd('members-%s-users' % (room),name)
        return client_id

    def nicks_in_room(self, room):
        """Return a list with the nicknames of the users currently connected to the specified room."""
        return self.redis_cli.smembers('members-%s-users' % (room))



class MainHandler(BaseHandler):

    def initialize(self, room_handler):
        self.room_handler = room_handler

    def get(self, action=None):
        if not action:
            try:
                self.room = self.get_argument("room")
                nick = self.get_argument("nick")
                client_id = self.room_handler.add_room(self.room, nick)
                emsgs = ["The nickname provided was invalid. It can only contain letters, numbers, - and _.\nPlease try again.",
                         "The room name provided was invalid. It can only contain letters, numbers, - and _.\nPlease try again.",
                         "The maximum number of users in this room (%d) has been reached.\n\nPlease try again later." % MAX_USERS_PER_ROOM,
                         "The maximum number of rooms (%d) has been reached.\n\nPlease try again later." % MAX_ROOMS]
                if client_id == -1 or client_id == -2:
                    self.render("maxreached.html",
                                emsg=emsgs[client_id])
                else:
                    if client_id < -2:
                        self.render("main.html",
                                    emsg=emsgs[client_id])
                    else:
#                        self._get_current_user(callback=self.on_auth)
                        self.set_cookie("ftc_cid", str(client_id))
                        self.render("chat.html", room_name=self.room)
            except tornado.web.MissingArgumentError:
                self.render("main.html", emsg="")
        else:
            if action == "drop":
                client_id = self.get_cookie("ftc_cid")
                if client_id:
                    self.render("nows.html")


class ClientWSConnection(tornado.websocket.WebSocketHandler):

    def __init__(self, *args, **kwargs):
        super(ClientWSConnection, self).__init__(*args, **kwargs)
        self.nclient = redis_connect('redis')
        self.client_id = int(self.get_cookie("ftc_cid", 0))
        self.room = (self.nclient.get('%s-%s' % (self.client_id,'room'))).decode()
        self.nick = (self.nclient.get('%s-%s' % (self.client_id,'nick'))).decode()
        self.listen()

    @tornado.gen.engine
    def listen(self):
        """
        Called when socket is opened. It will subscribe for the given chat room based on Redis Pub/Sub.
        """
        self.client = tornadoredis.Client()
        self.client.connect()
        self.new_message_send = False
        yield tornado.gen.Task(self.client.subscribe, self.room)
        self.subscribed = True
        self.client.listen(self.on_message_publish)
        logging.info('New user connected to chat room ' + str(self.room))
        self.post_msg(self.client_id,msg_type="join")

    def on_message_publish(self, message):
        logging.debug('===message===[%s]==' % (str(message)))
        if message.kind == 'message':
            data = json.loads(message.body)
            self.write_message(str(message.body))


    def on_message(self, message):
        """
        Callback when new message received vie the socket.
        """
        logging.debug('===message===[%s]==' % (str(message)))

        data = json.loads(message)
        self.post_msg(self.client_id,msg_type=data['msgtype'],message=data['payload'])


    def post_msg(self, client_id,msg_type="join", message=None):

        data = dict(time='%10.6f' % time.time(),
                        msg_type=msg_type)

        data['username'] = self.nick
        if msg_type.lower() == 'join':
            data['payload'] = 'joined the chat room'
        elif msg_type.lower() == 'leave':
            data['payload'] = 'left the chat room'
        elif msg_type.lower() == 'nick_list':
            data['payload'] = self.nclient.smembers('members-%s-users' % (room))
        elif msg_type.lower() == 'text':
            data['payload'] = message
        pmessage = json.dumps(data)
        singleclient.rpush(self.room,pmessage)
        singleclient.publish(self.room,pmessage)


    def on_close(self):
        """
        Callback when the socket is closed. Frees up resource related to this socket.
        """
        logging.info("socket closed, cleaning up resources now")
        if self.client.subscribed:
            self.client.unsubscribe(self.room)
            self.post_msg(self.client_id,msg_type="leave")
            self.client.disconnect()

class Application(tornado.web.Application):
    """
    Main Class for this application holding everything together.
    """
    def __init__(self, room_handler):
        self.room_handler = room_handler
        # Handlers defining the url routing.
        handlers = [
            (r"/(|drop)", MainHandler,{'room_handler': room_handler}),
            (r"/login", LoginHandler),
            (r"/logout", LogoutHandler),
            (r"/ws", ClientWSConnection),
        ]

        # Settings:
        settings = dict(
            cookie_secret = "43osdETzKXasdQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            weibo_api_key = "868483214",
            weibo_api_secret = "da9d5027adec1da4449ee5de0dd31c94",
            login_url = "/login",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies= True,
            autoescape="xhtml_escape",
            # Set this to your desired database name.
            db_name = 'chat',
            # apptitle used as page title in the template.
            apptitle = 'Chat example: Tornado, Redis, brukva, Websockets',
        )

        # Call super constructor.
        tornado.web.Application.__init__(self, handlers, **settings)

        # Stores user names.
        self.usernames = {}

        # Connect to Redis.
        self.client = redis_connect('tornadoredis')


def redis_connect(redis_type='tornadoredis'):
    """
    Established an asynchronous resi connection.
    """

    redistogo_url = os.getenv('REDISTOGO_URL', None)
    if redistogo_url == None:
        REDIS_HOST = 'localhost'
        REDIS_PORT = 6379
        REDIS_PWD = None
        REDIS_USER = None
    else:
        redis_url = redistogo_url
        redis_url = redis_url.split('redis://')[1]
        redis_url = redis_url.split('/')[0]
        REDIS_USER, redis_url = redis_url.split(':', 1)
        REDIS_PWD, redis_url = redis_url.split('@', 1)
        REDIS_HOST, REDIS_PORT = redis_url.split(':', 1)

    if redis_type == 'redis':
        client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PWD)
        client.ping()
    elif redis == 'tornadoredis':
        client = tornadoredis.Client()
        client.connect()
    else:
        return None
    return client

def setup_cmd_parser():
    p = argparse.ArgumentParser(
        description='Simple WebSockets-based text chat server.')
    p.add_argument('-i', '--ip', action='store',
                   default='127.0.0.1', help='Server IP address.')
    p.add_argument('-p', '--port', action='store', type=int,
                   default=9696, help='Server Port.')
    p.add_argument('-g', '--log_file', action='store',
                   default='logsimplechat.log', help='Name of log file.')
    p.add_argument('-f', '--file_log_level', const=1, default=0, type=int, nargs="?",
                   help="0 = only warnings, 1 = info, 2 = debug. Default is 0.")
    p.add_argument('-c', '--console_log_level', const=1, default=3, type=int, nargs="?",
                   help="0 = No logging to console, 1 = only warnings, 2 = info, 3 = debug. Default is 0.")
    return p

def setup_logging(args):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)   # set maximum level for the logger,
    formatter = logging.Formatter('%(asctime)s | %(thread)d | %(message)s')
    loglevels = [0, logging.WARN, logging.INFO, logging.DEBUG]
    fll = args.file_log_level
    cll = args.console_log_level
    fh = logging.FileHandler(args.log_file, mode='a')
    fh.setLevel(loglevels[fll])
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    if cll > 0:
        sh = logging.StreamHandler()
        sh.setLevel(loglevels[cll])
        sh.setFormatter(formatter)
        logger.addHandler(sh)
    return logger


if __name__ == "__main__":
    parse = setup_cmd_parser()
    args = parse.parse_args()
    log = setup_logging(args)
    room_handler = RoomHandler()
    application = Application(room_handler)
    application.listen(args.port, args.ip)
    tornado.ioloop.IOLoop.instance().start()
