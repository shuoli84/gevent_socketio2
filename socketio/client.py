# coding=utf-8
import parser as Parser
import logging
from engine.socket import Socket as EngineSocket
from .event_emitter import EventEmitter

logger = logging.getLogger(__name__)


class Client(EventEmitter):
    """
    Client represents one client, which holds several socketio sockets, and one engineio socket.
    """
    def __init__(self, server, engine_socket):
        super(Client, self).__init__()

        self.server = server
        self.engine_socket = engine_socket
        self.request = engine_socket.request
        self.id = engine_socket.id
        self.sockets = []  # TODO check whether this introduced performance bottle neck
        self.namespace_socket = {}
        self.connect_buffer = []

        self.decoder = Parser.Decoder()
        self.encoder = Parser.Encoder()
        self.setup()

    def setup(self):
        """
        Setup event listener
        :return:
        """

        self.decoder.on('decoded', self.on_decoded, id(self))
        self.engine_socket.on('message', self.on_data, id(self))
        self.engine_socket.on('close', self.on_close, id(self))

    def connect(self, name):
        """
        Connect the client to a namespace
        :param name:
        :return:
        """

        self.debug('connecting to namespace %s' % name)

        if name not in self.server.namespaces:
            self.packet({
                'type': Parser.ERROR,
                'data': 'Invalid namespace',
                'nsp': name
            })
            return

        namespace = self.server.of(name)

        if '/' != name and '/' not in self.namespace_socket:
            self.connect_buffer.append(name)
            return

        def callback(socket):
            self.sockets.append(socket)
            self.namespace_socket[name] = socket

            if '/' == namespace.name and self.connect_buffer:
                for n in self.connect_buffer:
                    self.connect(n)
                self.connect_buffer = []

        namespace.add(self, callback)

    def disconnect(self):
        """
        Disconnect the client
        """
        while self.sockets:
            socket = self.sockets.pop(0)
            socket.disconnect()
        self.close()

    def remove(self, socket):
        """
        Remove the socket from client
        :param socket:
        :return:
        """
        try:
            index = self.sockets.index(socket)
            nsp = socket.namespace.name
            del self.sockets[index]
            del self.namespace_socket[nsp]
        except ValueError:
            self.debug('ignoring remove for %s' % socket.id)

    def close(self):
        """
        Close the client
        :return:
        """
        if self.engine_socket.ready_state == EngineSocket.STATE_OPEN:
            self.debug('forcing transport close')
            self.engine_socket.close()
            self.on_close('forced server close')

    def packet(self, packet, pre_encoded=False):
        """
        Send out a packet
        :param packet: The packet
        :param pre_encoded: Whether the packet is pre encoded.
        :return:
        """
        if self.engine_socket.ready_state == EngineSocket.STATE_OPEN:
            self.debug('writing packet %s' % str(packet))

            if not pre_encoded:
                encoded_packets = self.encoder.encode(packet)
            else:
                encoded_packets = packet

            for encoded in encoded_packets:
                self.engine_socket.write(encoded)

    def on_data(self, data):
        self.decoder.add(data)

    def on_decoded(self, packet):
        if Parser.CONNECT == packet['type']:
            self.connect(packet['nsp'])
        else:
            if packet['nsp'] not in self.namespace_socket:
                self.debug('The namespace is not connected yet, ignore the incoming message')
                return

            socket = self.namespace_socket[packet['nsp']]

            if socket:
                socket.on_packet(packet)
            else:
                self.debug('no socket for namespace %s' % packet['nsp'])

    def on_close(self, reason, *args, **kwargs):
        self.debug("On Close %s" % reason)
        self.destroy()

        while self.sockets:
            socket = self.sockets.pop()
            socket.on_close(reason)

        self.decoder.destroy()

    def destroy(self):
        self.engine_socket.remove_listeners_by_key(id(self))
        self.decoder.remove_listeners_by_key(id(self))

    def debug(self, message):
        logger.debug("[SocketIOClient][%s] %s" % (self.id, message))