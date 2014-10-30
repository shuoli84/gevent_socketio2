import json
import gevent
from gevent.queue import Queue
from socketio.event_emitter import EventEmitter
from .transports import available_transports, Transport

import logging
logger = logging.getLogger(__name__)


class Socket(EventEmitter):
    def __init__(self, host, port, path='/socket.io/', transports=("polling", "websocket"), upgrade=True):
        super(Socket, self).__init__()
        self.host = host
        self.port = port
        self.path = path
        self.id = None
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

    def _create_transport(self, name):
        if name not in available_transports:
            raise ValueError("Unknown transport [%s]", name)

        transport_class = available_transports[name]
        assert issubclass(transport_class, Transport)
        transport = transport_class(
            host=self.host,
            port=self.port,
            path=self.path,
        )

        assert isinstance(transport, Transport)
        if self.id is not None:
            transport.sid = self.id

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
        self.flush(nowait=True)

        if 'open' == self.ready_state and self.upgrade and self.transport.pause:
            logger.debug('starting upgrade probes')
            for upgrade in self.upgrades:
                self.probe(upgrade)

    def probe(self, upgrade):
        logger.debug('probing transport %s for sid: %s', upgrade, self.id)
        transport = self._create_transport(upgrade)
        assert isinstance(transport, Transport)

        context = {
            'failed': False
        }

        def on_transport_open():
            logger.debug('probe transport [%s]', upgrade)
            transport.send({
                'type': 'ping',
                'data': 'probe'
            })

            def packet_back(packet):
                if context['failed']:
                    return

                if 'pong' == packet['type'] and 'probe' == packet['data']:
                    logger.debug('probe transport [%s] pong', upgrade)
                    self.upgrading = True
                    self.emit('upgrading', transport)

                    self.prior_websocket_success = 'websocket' == transport.name

                    logger.debug('pause current transport [%s]', self.transport.name)

                    # FIXME possible data loss
                    self.transport.pause(nowait=True)

                    if context['failed']:
                        return

                    if 'closed' == self.ready_state:
                        return

                    logger.debug('changing transport and sending upgrade packet')
                    clean_transport(transport)

                    self._set_transport(transport)
                    transport.send({
                        'type': 'upgrade'
                    })
                    self.emit('upgrade', transport)
                    self.upgrading = False
                    self.flush(nowait=True)

                else:
                    logger.debug('probe transport [%s] failed', upgrade)
                    self.emit('upgrade_error', {
                        'transport': upgrade
                    })

            transport.once('packet', packet_back)

        def on_error(reason):
            context['failed'] = True
            clean_transport(transport)
            transport.close()

            self.emit('upgrade_error', {
                'transport': upgrade,
                'reason': reason
            })

        def on_transport_close():
            on_error('transport closed')

        def on_close():
            on_error('socket closed')

        def on_upgrade(to):
            """
            When the socket is upgraded while we're probing,
            Stop probing and continue with upgraded transport
            :param to: Transport upgrade to
            """
            if transport.name != to.name:
                logger.debug('[%s] works - aborting [%s]', to.name, self.transport.name)
                context['failed'] = True
                clean_transport(transport)
                transport.close()

        def clean_transport(trans):
            trans.remove_listener('open', on_transport_open)
            trans.remove_listener('error', on_error)
            trans.remove_listener('close', on_transport_close)

            self.remove_listener('close', on_close)
            self.remove_listener('upgrading', on_upgrade)

        transport.once('open', on_transport_open)
        transport.once('error', on_error)
        transport.once('close', on_transport_close)

        self.once('close', on_close)
        self.once('upgrading', on_upgrade)

        transport.open()

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

    def send(self, data):
        self.send_packet('message', data)

    def send_packet(self, packet_type, data=None, callback=None):
        if self.ready_state in ('closing', 'close'):
            return

        packet = {
            'type': packet_type,
            'data': data
        }

        self.packet(packet, callback)

    def packet(self, packet, callback=None):
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
        # FIXME do a graceful close
        for job in self.jobs:
            gevent.kill(job)
