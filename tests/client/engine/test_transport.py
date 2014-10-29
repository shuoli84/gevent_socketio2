import gevent
from gevent.monkey import patch_all
patch_all()

import json
from socketio_client.engine.transports import XHRPollingTransport
from tests.engine.base_server_test import SocketIOServerBaseTest


class PollingTest(SocketIOServerBaseTest):

    def test_polling(self):
        transport = XHRPollingTransport(host="127.0.0.1", port=self.port, path="/socket.io/")

        context = {}

        def on_packet(packet):
            context['packet'] = packet

        transport.on('packet', on_packet)
        job = gevent.spawn(transport.poll)
        gevent.sleep(.5)
        self.assertIsNotNone(context['packet'])
        gevent.kill(job)

    def test_b64_polling(self):
        transport = XHRPollingTransport(host="127.0.0.1", port=self.port, path="/socket.io/", force_base64=True)

        context = {}

        def on_packet(packet):
            context['packet'] = packet
            data = json.loads(packet['data'])
            transport.sid = data['sid']
            transport.remove_listener('packet', on_packet)

        transport.on('packet', on_packet)
        job = gevent.spawn(transport.open)
        gevent.sleep(0.2)
        self.assertIsNotNone(context['packet'])
        gevent.kill(job)
