from gevent.monkey import patch_all
patch_all()

import gevent
from socketio_client.socket import Socket
from tests.socketio_test_server import SocketIOServerBaseTest
from socketio_client.engine.socket import Socket as EngineSocket


class SocketTest(SocketIOServerBaseTest):
    def test_socket_open(self):
        pass

