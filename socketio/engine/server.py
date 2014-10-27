from __future__ import absolute_import

from gevent.pywsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler
from .handler import EngineHandler
import logging
from socketio.event_emitter import EventEmitter

__all__ = ['Server']

logger = logging.getLogger(__name__)


class Server(object):
    """
    EngineIO Server holds all opened sockets
    """
    ws_handler_class = WebSocketHandler
    config = {
        'heartbeat_timeout': 60,
        'close_timeout': 60,
        'heartbeat_interval': 25,
    }
    engine_sockets = {}

    def __init__(self, *args, **kwargs):
        self.transports = kwargs.pop('transports', None)
        self.resource = kwargs.pop('resource', 'socket.io')

    def on_connection(self, engine_socket):
        """
        Called when there is a new connection, should be implemented by inherited class
        :param engine_socket: The underlying engine_socket
        :return: None
        """
        raise NotImplementedError()
