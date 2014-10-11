# coding=utf-8
from unittest import TestCase
from socketio import has_bin
import socketio.parser as Parser


class ParserTest(TestCase):

    def _test_packet(self, packet):
        encoded = Parser.Encoder.encode(packet)

        decoder = Parser.Decoder()

        def decoded(p):
            self.assertEqual(p['type'], packet['type'])
            if 'nsp' in packet:
                self.assertEqual(p['nsp'], packet['nsp'])
            if 'data' in packet:
                self.assertEqual(p['data'], packet['data'])

        decoder.on('decoded', decoded)
        decoder.add(encoded[0])

    def _test_bin_packet(self, packet):
        encoded = Parser.Encoder.encode(packet)
        decoder = Parser.Decoder()

        def decoded(p):
            self.assertEqual(p['type'], packet['type'])
            if 'nsp' in packet:
                self.assertEqual(p['nsp'], packet['nsp'])
            if 'data' in packet:
                self.assertEqual(p['data'], packet['data'])

        decoder.on('decoded', decoded)

        for i in encoded:
            decoder.add(i)

    def test_has_bin(self):
        self.assertFalse(has_bin([{'text':'hello'}]))
        self.assertTrue(has_bin([bytearray('abc')]))
        self.assertTrue(has_bin([{
            'data': bytearray('abc')
        }]))
        self.assertFalse(has_bin([{
            'data': "a",
            'dict': {
                'what': 'the'
            }
        }]))

    def test_encode(self):
        self._test_packet({
            'type': Parser.types['CONNECT'],
            'nsp': '/woot',
        })

        self._test_packet({
            'type': Parser.types['CONNECT'],
            'nsp': '/',
            'data': ['a', 1, {}]
        })

        self._test_packet({
            'type': Parser.types['EVENT'],
            'data': ['a', 1, {}],
            'id': 1,
            'nsp': '/test'
        })

        self._test_packet({
            'type': Parser.types['ACK'],
            'data': ['a', 1, {}],
            'id': 123,
            'nsp': '/t'
        })

        self._test_bin_packet({
            'type': Parser.types['BINARY_EVENT'],
            'data': bytearray([1,2,3]),
        })

        self._test_packet({
            'type': Parser.types['CONNECT'],
            'nsp': '/',
            'data': {
                'message': 'what the hell',
                'content': 'I have no idea'
            }
        })