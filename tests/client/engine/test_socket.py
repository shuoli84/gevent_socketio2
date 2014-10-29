import gevent
from gevent.monkey import patch_all
import sys

patch_all()

from socketio_client.engine.socket import Socket
from tests.client.engine.base_server_test import EngineIOServerBaseTest
from socketio.engine.server import Server

import logging

logger = logging.getLogger()
logger.level = logging.DEBUG
stream_handler = logging.StreamHandler(sys.stdout)
logger.addHandler(stream_handler)


class SocketTest(EngineIOServerBaseTest):
    def test_open(self):
        socket = Socket(host=self.host, port=self.port)
        job = gevent.spawn(socket.open)
        gevent.sleep(.5)
        self.assertEqual("open", socket.ready_state)
        gevent.kill(job)

    def test_send(self):
        socket = Socket(host=self.host, port=self.port)
        job = gevent.spawn(socket.open)
        gevent.sleep(.5)
        self.assertEqual(1, len(Server.engine_sockets.items()))
        engine_socket = Server.engine_sockets[socket.id]

        context = {}

        def on_message(message):
            context['message'] = message

        engine_socket.on("message", on_message)
        socket.send('what the')

        gevent.sleep(0.1)

        self.assertTrue('message' in context)
        gevent.kill(job)
