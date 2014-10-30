import gevent
from gevent.monkey import patch_all
import sys

patch_all()

from socketio_client.engine.socket import Socket
from tests.engineio_test_server import EngineIOServerBaseTest
from socketio.engine.server import Server


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
        message = 'test message'
        socket.send(message)

        gevent.sleep(0.1)

        self.assertTrue('message' in context)
        self.assertEqual(message, context['message'])
        gevent.kill(job)

    def test_upgrade(self):
        socket = Socket(host=self.host, port=self.port)
        self.spawn(socket.open)
        gevent.sleep(2)
        self.assertEqual('websocket', socket.transport.name)

        engine_socket = Server.engine_sockets[socket.id]

        context = {}

        def on_message(message):
            context['message'] = message

        engine_socket.on("message", on_message)

        message = 'test message'
        socket.send(message)

        gevent.sleep(.2)

        self.assertEqual(context['message'], message)
