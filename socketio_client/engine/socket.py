import json
import gevent
from gevent.queue import Queue
from socketio.event_emitter import EventEmitter
from .transports import XHRPollingTransport, WebsocketTransport

import logging
logger = logging.getLogger(__name__)


class Socket(EventEmitter):
    def __init__(self, host, port, path='/socket.io/', transports=("polling", "websocket"), upgrade=True):
        super(Socket, self).__init__()
        self.host = host
        self.port = port
        self.path = path
        self.transports = transports
        self.upgrade = upgrade
        self.ready_state = None
        self.transport = None
        self.write_queue = Queue()
        self.write_callback_queue = Queue()
        self.upgrading = False
        self.ping_job = None
        self.ping_timeout_job = None
        self.jobs = []

    def _set_transport(self, transport):
        transport.on("packet", self.on_packet)
        self.transport = transport

    def open(self):
        if len(self.transports) == 0:
            raise ValueError("There is no transports defined")

        self.ready_state = 'opening'

        transport = self._create_transport(self.transports[0])
        self._set_transport(transport)
        transport.open()

    def _create_transport(self, transport):
        if transport == 'polling':
            transport = XHRPollingTransport(host=self.host, port=self.port, path=self.path)
        elif transport == 'websocket':
            transport = WebsocketTransport(host=self.host, port=self.port, path=self.path)
        else:
            raise ValueError('Unknown transport type: %s', transport)

        return transport

    def on_packet(self, packet):
        if 'open' == self.ready_state or 'opening' == self.ready_state:
            logger.debug('socket receive: type: "%s", data: "%s"', packet['type'], packet['data'])

            self.emit('packet', packet)
            self.emit('heartbeat')

            packet_type = packet['type']

            if packet_type == 'open':
                self._on_handshake(json.loads(packet['data']))
            elif packet_type == 'message':
                self.emit('data', packet['data'])
                self.emit('message', packet['data'])
            elif packet_type == 'pong':
                pass
            elif packet_type == 'error':
                self.emit('error', packet['data'])
        else:
            logger.debug('packet received with socket readyState "%s"', self.ready_state)

    def _on_handshake(self, data):
        self.id = data['sid']
        self.transport.sid = self.id
        self.upgrades = data['upgrades']
        # CHECK WHAT'S HAPPENING HERE
        self.ping_interval = float(data['pingInterval'])
        self.ping_timeout = float(data['pingTimeout'])
        self.on_open()

        if 'closed' == self.ready_state:
            return

        self.set_ping_event()

    def on_open(self):
        logger.debug('socket open')
        self.ready_state = 'open'
        self.emit('open')
        self.flush()

        if 'open' == self.ready_state and self.upgrade and self.transport.pause:
            logger.debug('starting upgrade probes')
            for upgrade in self.upgrades:
                self.probe(upgrade)

    def probe(self, upgrade):
        logger.debug('probing transport %s', upgrade)

    def _ping(self):
        self.transport.send([{
            ''
        }])

    def set_ping_event(self):
        if self.ping_job is not None:
            gevent.kill(self.ping_job)
        if self.ping_timeout_job is not None:
            gevent.kill(self.ping_timeout_job)

        def ping():
            # FIXME PASS
            self.ping_job = gevent.spawn_later(self.ping_interval, ping)

            def ping_timeout():
                pass

            self.ping_timeout_job = gevent.spawn_later(ping_timeout, self.ping_timeout)

        if 'open' == self.ready_state or 'opening' == self.ready_state:
            self.ping_job = gevent.spawn_later(self.ping_interval/1000, ping)

    def connect(self):
        pass

    def packet(self, type, data):
        pass

    def send(self, data):
        self.send_packet('message', data)

    def send_packet(self, packet_type, data=None, callback=None):
        if self.ready_state in ('closing', 'close'):
            return

        packet = {
            'type': packet_type,
            'data': data
        }

        self.write_queue.put(packet)
        self.write_callback_queue.put(callback)
        self.flush(nowait=True)

    def flush(self, nowait=False):
        if 'closed' != self.ready_state and self.transport.writable and not self.upgrading:
            if nowait and self.write_queue.qsize() == 0:
                return

            logger.debug("flushing %d packets", self.write_queue.qsize())
            packets = [self.write_queue.get()]
            print self.transport
            self.transport.send(packets)

    def close(self):
        for job in self.jobs:
            gevent.kill(job)
