from __future__ import absolute_import

import logging
from gevent.pywsgi import WSGIServer
from .client import Client
from .namespace import Namespace
from .engine.server import Server as EngineServer
from .engine.handler import EngineHandler

__all__ = ['SocketIOServer']

logger = logging.getLogger(__name__)


class SocketIOServer(EngineServer):
    """
    SocketIOServer holds all server level resources. And it inherit from EngineIO, which handles all incoming connection
    """

    default_server = None

    def __init__(self, *args, **kwargs):
        """
        Initialize an socketio server object.
        :param args:
        :param kwargs:
        :return:
        """
        self.namespaces = {}
        self.root_namespace = self.of('/')
        super(SocketIOServer, self).__init__(*args, **kwargs)

    def of(self, name):
        """
        Create or get a namespace object for name
        :param name: The name
        :return:
        """
        if not name.startswith('/'):
            name = '/' + name

        if name not in self.namespaces:
            logger.debug('initializing namespace %s', name)
            namespace = Namespace(self, name)
            self.namespaces[name] = namespace

        return self.namespaces[name]

    def close(self):
        """
        Close all active socket in this server, and all socket connected to root namespace
        :return: None
        """

        logger.debug('closing socketio server')
        if '/' in self.namespaces:
            for socket in self.namespaces['/'].sockets:
                socket.on_close(reason='the server closed')

    def on_connection(self, engine_socket):
        """
        Called when a new underlying socket connected. It creates a client object and connect it to root namespace
        :param engine_socket:
        :return:
        """
        logger.debug('incoming connection with id %s', engine_socket.id)
        client = Client(self, engine_socket)
        client.connect('/')


SocketIOServer.default_server = SocketIOServer()


class SocketIOWSGIServer(WSGIServer):
    def handle(self, socket, address):
        handler = EngineHandler(SocketIOServer.default_server, socket, address, self)
        handler.on('connection', SocketIOServer.default_server.on_connection)
        handler.handle()


def serve(app, **kw):
    host = kw.pop('host', '127.0.0.1')
    port = int(kw.pop('port', 6543))

    server = SocketIOWSGIServer((host, port),
                                app,
                                **kw)

    print('serving on http://%s:%s' % (host, port))
    server.serve_forever()
