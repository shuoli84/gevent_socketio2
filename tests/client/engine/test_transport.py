import gevent
from gevent.monkey import patch_all
patch_all()

import json
from socketio_client.engine.transports import XHRPollingTransport, WebsocketTransport
from tests.engineio_test_server import EngineIOServerBaseTest
from socketio.engine.server import Server


class PollingTest(EngineIOServerBaseTest):

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

        transport.pause(nowait=True)
        # The transport state should be 'pausing', but since it is still polling, the state not able to reach
        # paused

        self.assertEqual('pausing', transport.ready_state)

        gevent.kill(job)

    def test_websocket(self):
        transport = WebsocketTransport(host="127.0.0.1", port=self.port, path="/socket.io/")
        transport.open()
        transport.send([{
            'type': 'message',
            'data': 'hello world'
            }])

        transport.send([{
            'type': 'message',
            'data': bytearray('hahaha')
        }])

        context = {}
        def on_packet(packet):
            context['packet'] = packet

        transport.on('packet', on_packet)
        gevent.sleep(.2)

        # Send data from server
        socket = Server.default_server.engine_sockets.values()[0]
        """:type : socketio.engine.socket.Socket"""

        socket.send('hello')
        gevent.sleep(.2)

        self.assertEqual('hello', context['packet']['data'])

        socket.send(bytearray([1, 2, 3]))
        gevent.sleep(.2)

        self.assertEqual(context['packet']['data'], bytearray([1, 2, 3]))
