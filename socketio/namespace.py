# coding=utf-8
from __future__ import absolute_import
import logging
from . import has_bin
from .adapter import Adapter
from .socket import Socket
from .engine.socket import Socket as EngineSocket
from . import parser as SocketIOParser
from .event_emitter import EventEmitter

logger = logging.getLogger(__name__)


class Namespace(EventEmitter):
    # TODO Add middleware support which able to do auth

    def __init__(self, server, name):
        self.name = name
        self.server = server
        self.sockets = []
        self.connected = {}
        self.ids = 0
        self.acks = {}
        self.rooms = {}
        self.rooms_send_to = []
        self.jobs = []
        self.adapter = Adapter(self)

        super(Namespace, self).__init__()

    def to(self, name):
        if name not in self.rooms_send_to:
            self.rooms_send_to.append(name)

        return self

    def add(self, client, callback=None):
        self.debug('adding client to namespace %s' % self.name)

        socket = Socket(self, client)

        if client.engine_socket.ready_state == EngineSocket.STATE_OPEN:
            self.sockets.append(socket)
            socket.on_connect()

            if callback:
                callback(socket)

            self.emit('connect', socket)
            self.emit('connection', socket)
        else:
            self.debug('Client was closed, ignore socket')

        return socket

    def remove(self, socket):
        self.debug("Removing socket %s from namespace" % socket.id)
        if socket in self.sockets:
            self.debug("Found socket, remove it")
            self.sockets.remove(socket)
            super(Namespace, self).emit('disconnect', socket)
            self.debug("Socket removed")
        else:
            self.debug('ignoring remove for %s' % socket.id)

    def emit(self, event, *args):
        if event in ['connect', 'connection']:
            super(Namespace, self).emit(event, *args)
        else:
            _type = SocketIOParser.EVENT

            if has_bin(args):
                _type = SocketIOParser.BINARY_EVENT

            packet = {'type': _type, 'data': [event] + list(args)}

            self.adapter.broadcast(packet, {
                'rooms': self.rooms,
            })
            self.rooms = {}

        return self

    def send(self, *args):
        self.emit('message', *args)

        return self

    write = send

    def get_id(self, increment=False):
        """
        Get id for this namespace
        :param increment:
        :return:
        """
        result = self.ids

        if increment:
            self.ids += 1

        return result

    def debug(self, message):
        logger.debug("[Namespace][id:%d] %s" % (self.ids, message))
