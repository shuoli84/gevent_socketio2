from unittest import TestCase
from socketio_client.client import SocketIOClient


class ClientTest(TestCase):
    def test_example(self):
        client = SocketIOClient(schema="http", host="localhost", port="8080", resource="socket.io", transports=('polling', 'websocket'))
        self.assertIsNotNone(client)

        namespace = client.of("/chat")
        namespace.on('connect', lambda socket: True)
        namespace.on('disconnect', lambda socket: True)

        def on_message(socket, data):
            socket.emit('message', data)

        namespace.on('message', on_message)

        # After the setup, now we wait on the client
        client.join()
