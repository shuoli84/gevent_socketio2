import gevent
import urlparse
from socketio.event_emitter import EventEmitter
import socketio.parser as Parser
from .engine.socket import Socket as EngineSocket
from socketio_client.socket import Socket
import logging

logger = logging.getLogger(__name__)


class SocketIOClient(EventEmitter):
    def __init__(self, uri, transports=('polling', 'websocket'),
                 auto_connect=False, reconnect=True, reconnect_attempts=None, reconnect_delay=1, reconnect_delay_max=5,
                 timeout=20, **kwargs):
        super(SocketIOClient, self).__init__()

        self._set_uri(uri)
        self.transports = transports
        self.ready_state = 'closed'
        self.auto_connect = auto_connect
        self.nsps = {}
        self.connected = set()
        self.reconnection = reconnect
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.reconnect_delay_max = reconnect_delay_max
        self.timeout = timeout
        self.open_reconnect = None
        self.reconnecting = False
        self.attempts = 0
        self.engine_socket = None
        self.decoder = Parser.Decoder()
        self.encoder = Parser.Encoder()
        self.skip_reconnect = False
        self.reconnect_job = None
        self.config = kwargs

    def _set_uri(self, uri):
        result = urlparse.urlparse(uri)
        self.uri = uri
        self.host = result.hostname
        self.path = result.path
        self.port = result.port
        self.secure = result.scheme == 'https' or result.scheme == 'wss'

    def emit_all(self, *args, **kwargs):
        self.emit(*args, **kwargs)

        for _, nsp in self.nsps.items():
            nsp.emit(*args, **kwargs)

    def maybe_reconnect_on_open(self):
        if not self.open_reconnect and not self.reconnecting and self.reconnection and self.attempts == 0:
            self.open_reconnect = True
            self.reconnect()

    def open(self, callback=None):
        logger.debug('ready_state %s', self.ready_state)
        if self.ready_state == 'open' or self.ready_state == 'opening':
            return

        logger.debug('opening %s', self.uri)

        engine_socket = EngineSocket(
            host=self.host, path=self.path, port=self.port,
            transports=self.transports, **self.config)
        self.engine_socket = engine_socket
        self.ready_state = 'opening'

        def on_open():
            self.on_open()
            if callback:
                callback()
        engine_socket.on('open', on_open, id(self))

        def on_error(error):
            logger.debug('connect_error')
            self.cleanup()
            self.ready_state = 'closed'
            self.emit_all('connect_error', error)

            if callback:
                callback(error)

            self.maybe_reconnect_on_open()

        engine_socket.on('error', on_error, id(self))

        if self.timeout is not None:
            timeout = self.timeout
            logger.debug('connect attempt will timeout after %d', timeout)

            def timeout_func():
                logger.debug('connect attempt timed out after %d', timeout)
                engine_socket.remove_listener('open', on_open)
                engine_socket.close()
                self.emit('error', 'timeout')
                self.emit_all('connect_timeout', timeout)

            gevent.spawn_later(timeout, timeout_func)

        engine_socket.open()

    def _clean_socket(self):
        self.engine_socket.remove_listeners_by_key(id(self))

    def on_open(self):
        logger.debug('open')
        self.cleanup()

        self.ready_state = 'open'
        self.emit('open')

        engine_socket = self.engine_socket
        engine_socket.on('data', self.on_data, id(self))
        self.decoder.on('decoded', self.on_decoded, id(self))
        engine_socket.on('error', self.on_error, id(self))
        engine_socket.on('close', self.on_close, id(self))

    def on_data(self, data):
        self.decoder.add(data)

    def on_decoded(self, packet):
        self.emit('packet', packet)

    def on_error(self, err):
        logger.debug('error %s', str(err))
        self.emit_all('error', err)

    def socket(self, nsp):
        """
        Creates a new socket for the given namespace
        :param nsp: string
        :return: Socket
        """
        if nsp in self.nsps:
            return self.nsps[nsp]

        socket = Socket(self, nsp, self.auto_connect)
        self.nsps[nsp] = socket

        def on_connect():
            if socket not in self.connected:
                self.connected.add(socket)

        socket.on('connect', on_connect, id(self))
        socket.open()

        return socket

    def destroy(self, socket):
        """
        Called upon a socket close
        :param socket: Socket
        :return: None
        """
        if socket in self.connected:
            self.connected.pop(socket)
            socket.remove_listeners_by_key(id(self))

        if len(self.connected) == 0:
            self.close()

    def packet(self, packet):
        logger.debug('writing packet %s', str(packet))

        encoded_packets = self.encoder.encode(packet)
        for encoded_packet in encoded_packets:
            self.engine_socket.write(encoded_packet)

    def cleanup(self):
        if self.reconnect_job is not None:
            gevent.kill(self.reconnect_job)

        self._clean_socket()
        self.decoder.remove_listeners_by_key(id(self))
        self.decoder.destroy()

    def close(self):
        self.ready_state = 'closed'
        if self.engine_socket:
            self.engine_socket.close()

        self.skip_reconnect = True

    def on_close(self, reason=''):
        logger.debug('close')
        self.cleanup()
        self.ready_state = 'closed'
        self.emit('close', reason)

        if self.reconnection and not self.skip_reconnect:
            self.reconnect()

    def reconnect(self):
        if self.reconnecting or self.skip_reconnect:
            return

        self.attempts += 1

        if self.attempts > self.reconnect_attempts:
            logger.debug('reconnect failed')
            self.emit_all('reconnect_failed')
            self.reconnecting = False

        else:
            delay = self.attempts * self.reconnect_delay
            delay = min(delay, self.reconnect_delay_max)

            logger.debug('will wait %d seconds before reconnect', delay)
            self.reconnecting = True

            def reconnect_func():
                if self.skip_reconnect:
                    return
                logger.debug('attemping to reconnect')
                self.emit_all('reconnecting', self.attempts)

                # Check again
                if self.skip_reconnect:
                    return

                def on_open(err=None):
                    if err is not None:
                        logger.debug('reconnect attemp error')
                        self.reconnecting = False
                        self.reconnect()
                        self.emit_all('reconnect_error', err)
                    else:
                        logger.debug('reconnect success')
                        self.on_reconnect()

                self.open(on_open)

            self.reconnect_job = gevent.spawn_later(delay, reconnect_func)

    def on_reconnect(self):
        self.emit_all('reconnect', self.attempts)
        self.reconnecting = False
        self.attempts = 0
