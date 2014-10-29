from gevent.monkey import patch_all
patch_all()

from socketio_client.engine.transports import XHRPollingTransport
from tests.engine.base_server_test import SocketIOServerBaseTest


class PollingTest(SocketIOServerBaseTest):

    def test_polling(self):
        transport = XHRPollingTransport(host="127.0.0.1", port=self.port, path="/socket.io/")

        context = {}

        def on_packet(packet):
            context['packet'] = packet

        transport.on('packet', on_packet)
        transport.poll()

        # We should has the handshake packet back
        self.assertIsNotNone(context['packet'])

