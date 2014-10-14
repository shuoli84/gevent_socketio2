from gevent.monkey import patch_all
patch_all()

from tests.engine.base_server_test import SocketIOServerBaseTest
import json
import gevent

import requests
from socketio.server import serve, SocketIOServer
from socketio.engine.parser import Parser as EngineParser
import socketio.parser as SocketIOParser


class ServerTest(SocketIOServerBaseTest):
    def test_server(self):
        gevent.sleep(0.5)
        result = {'socket': None}

        def message(socket):
            result['socket'] = socket

            def onevent(packet_data):
                result['packet'] = packet_data

            socket.on('message', onevent)

        SocketIOServer.global_server.namespaces['/'].on('connection', message)

        response = requests.get(self.root_url + '?transport=polling')

        sid = None
        for p, i, t in EngineParser.decode_payload(bytearray(response.content)):
            data = json.loads(p['data'])
            sid = data['sid']
            break

        self.assertIsNotNone(sid)
        self.assertIsNotNone(result['socket'])

        socket_encoded = SocketIOParser.Encoder.encode({
            'type': SocketIOParser.EVENT,
            'data': ['message', 'hello']
        })

        engine_encoded = EngineParser.encode_payload({
            'type': 'message',
            'data': socket_encoded[0]
        })

        # Work around the bug which not sending pre buffered message
        response = requests.post(self.root_url + ('?transport=polling&sid=%s' % sid),
                                 data=engine_encoded,
                                 headers={'Content-Type': 'application/octet-stream'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, 'ok')

        self.assertEqual(result['packet'], 'hello')
