"""
Engine socket, a abstract layer for all transports internal api. It is created by Engine.handler with proper parameters
and used by socketio.socket.
"""
import json

import random
import logging

import transports
import gevent
from gevent.queue import Queue
from ..event_emitter import EventEmitter


__all__ = ['Socket']

logger = logging.getLogger(__name__)

handler_types = {
    'websocket': transports.WebsocketTransport,
    'polling': transports.XHRPollingTransport,
}


def default_error_handler(socket, error_name, error_message, endpoint,
                          msg_id, quiet):
    """This is the default error handler, you can override this when
    calling :func:`socketio.socketio_manage`.

    It basically sends an event through the socket with the 'error' name.

    See documentation for :meth:`Socket.error`.

    :param quiet: if quiet, this handler will not send a packet to the
                  user, but only log for the server developer.
    """
    pkt = dict(type='event', name='error',
               args=[error_name, error_message],
               endpoint=endpoint)
    if msg_id:
        pkt['id'] = msg_id

    # Send an error event through the Socket
    if not quiet:
        socket.send_packet('event', json.dumps(pkt))

    # Log that error somewhere for debugging...
    logger.error(u"default_error_handler: {}, {} (endpoint={}, msg_id={})".format(
        error_name, error_message, endpoint, msg_id
    ))


class Socket(EventEmitter):
    """
    Socket is the interface which provides following features:
    1. send packet out
    2. emit 'packet' when new packet arrived

    Naming Convention
    ===============
    on_xxx are event handlers. It is better not being called directly.
    _xxx are private methods.

    States
    ===============
    STATE_NEW: The socket object just created
    STATE_OPEN: The socket is open, ready for send and receive message
    STATE_CLOSING: The socket is closing, cleaning up
    STATE_CLOSED: The socket closed

    Events
    ===============
    Socket is an EventEmitter, following events can be listened on:

    open: the socket is set up, transport is ready to send data
    packet: received a packet from underlying transport
    message: received a message packet from underlying transport
    close: the socket closed

    Event Loop
    ===============
    It creates several event loops:
        heartbeat timeout checking
        Server message handling
        Client message handling

    Close
    ================
    There are 2 situations:
    1. Client send out a close message. Transport get the message and close itself, then emit 'close', socket call
    on_close which close the socket directly
    2. Server invoke socket.close(), then socket state change to CLOSING and call transport.close(), which involve
    sending out buffered data etc. Then the transport will emit event 'close' and the socket object's on_close be
    invoked
    """

    STATE_NEW = "NEW"
    STATE_OPEN = "OPEN"
    STATE_CLOSING = "CLOSING"
    STATE_CLOSED = "CLOSED"

    def __init__(self, request, ping_interval=5000, ping_timeout=10000, upgrade_timeout=30):
        super(Socket, self).__init__()

        self.request = request

        self.id = str(random.random())[2:]
        self.ready_state = self.STATE_NEW
        self.upgraded = False

        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.upgrade_timeout = upgrade_timeout

        self.write_buffer = Queue()  # queue for messages to client
        self.server_queue = Queue()  # queue for messages to server

        self.wsgi_app_greenlet = None
        self.jobs = []
        self.error_handler = default_error_handler
        self.ping_timeout_eventlet = None
        self.check_eventlet = None
        self.upgrade_eventlet = None

        self.context = {} # Holder for framework specific data.

        transport_name = request.GET.get("transport", None)

        if transport_name not in handler_types:
            raise Exception('transport name not in query string')

        handler_class = handler_types[transport_name]
        if issubclass(handler_class, transports.BaseTransport):
            transport = handler_class(request.handler, {})
            self._set_transport(transport)
        else:
            raise Exception('Not able to construct transport class')

        self.process_request(request)

    def _set_transport(self, transport):
        self.transport = transport
        self.transport.once('error', self.on_error)
        self.transport.on('packet', self.on_packet)
        self.transport.on('drain', self.flush_nowait)
        self.transport.once('close', self.on_close)

    def _clear_transport(self):
        self.transport.remove_listener('close', self.on_close)
        self.transport.remove_listener('drain', self.on_packet)
        self.transport.remove_listener('packet', self.on_packet)
        self.transport.remove_listener('error', self.on_error)
        self.transport.on('error', lambda: logger.debug('error triggered by discarded transport'))
        self.transport = None

    def open(self):
        """
        The socket is ready to go
        :return:
        """
        self.ready_state = self.STATE_OPEN
        self.send_packet(
            "open",
            json.dumps({
                "sid": self.id,
                "upgrades": ["websocket"],  # FIXME don't hard code this
                "pingInterval": 30000,
                "pingTimeout": 60000})
        )
        self.emit("open")
        self._set_ping_timeout_eventlet()

    def process_request(self, request):
        """
        Process the incoming request
        """
        self.transport.process_request(request)

    def on_packet(self, packet):
        """
        Invoked when underlying transport received a new packet
        :param packet:
        """
        if self.STATE_OPEN == self.ready_state:
            self.emit("packet", packet)
            self._set_ping_timeout_eventlet()

            packet_type = packet["type"]

            if packet_type == 'ping':
                logger.debug("got ping, send pong")
                self.send_packet('pong')

            elif packet_type == 'message':
                self.emit("message", packet['data'])

            elif packet_type == 'error':
                self.on_close("Parse error")

        else:
            logger.debug("Packet received with closed socket")

    def on_error(self, error=None):
        """
        Invoked when an error message received from transport
        """
        logger.debug("transport error: %s" % error)
        self.on_close('transport error', error)

    def on_close(self, *args, **kwargs):
        """
        When transport closed, this method will be called. It will remove all jobs, and do cleanup
        """
        if self.STATE_CLOSED != self.ready_state:
            if self.ping_timeout_eventlet:
                self.ping_timeout_eventlet.kill()
                self.ping_timeout_eventlet = None

            if self.check_eventlet:
                self.check_eventlet.kill()
                self.check_eventlet = None

            if self.upgrade_eventlet:
                self.upgrade_eventlet.kill()
                self.upgrade_eventlet = None

            self._clear_transport()
            self.ready_state = self.STATE_CLOSED
            self.emit("close", "received close message", *args, **kwargs)
            self.write_buffer = None

    def maybe_upgrade(self, transport):
        logger.debug("might upgrade from %s to %s" % (self.transport.name, transport.name))

        def fail_upgrade():
            logger.debug('client did not complete upgrade - closing transport')

            if self.check_eventlet:
                self.check_eventlet.kill()
                self.check_eventlet = None

            if 'open' == transport.ready_state:
                transport.close()

        self.upgrade_eventlet = gevent.spawn_later(self.upgrade_timeout, fail_upgrade)

        def check():
            if 'polling' == self.transport.name and self.transport.writable:
                logger.debug("writing a noop packet to polling for fast upgrade")
                self.transport.send([{
                                         "type": "noop"
                                     }])

        def on_packet(packet):
            if "ping" == packet["type"] and "probe" == packet["data"]:
                transport.send([{
                                    "type": "pong",
                                    "data": "probe"
                                }])

                if self.check_eventlet is not None:
                    self.check_eventlet.kill()

                def loop():
                    while True:
                        gevent.sleep(1)
                        check()

                self.check_eventlet = gevent.Greenlet.spawn(loop)

            elif 'upgrade' == packet["type"] and self.ready_state == self.STATE_OPEN:
                logger.debug("got upgrade packet - upgrading")

                transport.remove_listener('packet', on_packet)

                self._clear_transport()
                self._set_transport(transport)

                self.upgraded = True
                self._set_ping_timeout_eventlet()
                self.upgrade_eventlet.kill()
                self.flush_nowait()
            else:
                transport.close()

        transport.on("packet", on_packet)

    def _set_ping_timeout_eventlet(self):
        """
        set the ping timeout eventlet, which will close the socket if no packets received in timeout
        :return:
        """
        if self.ping_timeout_eventlet:
            self.ping_timeout_eventlet.kill()

        def time_out():
            self.on_close('ping timeout')
        self.ping_timeout_eventlet = gevent.spawn_later(self.ping_interval + self.ping_timeout, time_out)

    def __str__(self):
        result = ['sessid=%r' % self.id]
        if self.ready_state == self.STATE_OPEN:
            result.append('open')
        return ' '.join(result)

    def send(self, data):
        """
        Shortcut for send message packet
        :param data: The data to be send
        :return: None
        """
        self.send_packet('message', data)

    # shortcut
    write = send

    def send_packet(self, packet_type, data=None):
        """
        the primary send_packet method
        """
        logger.debug('send_packet in socket data [%s]' % data)
        packet = {
            "type": packet_type
        }

        if data is not None:
            packet["data"] = data

        if self.ready_state != self.STATE_CLOSING:
            self.put_client_msg(packet)
            self.flush()

    def flush_nowait(self):
        """
        Non-blocking flush
        :return:
        """
        self.flush(nowait=True)

    def flush(self, nowait=False):
        """
        Flush write buffer, if buffer is empty, wait on it.
        :param nowait: Whether wait on write buffer or return directly
        """
        logger.debug("entering flushing buffer to transport " + str(self.transport.writable) + " " + str(self.write_buffer.qsize()))
        if self.ready_state != self.STATE_CLOSED and self.transport.writable:
            if nowait and self.write_buffer.qsize() == 0:
                return

            logger.debug('wait for the queue %s' % self.write_buffer.qsize())
            msg = [self.write_buffer.get()]
            while self.write_buffer.qsize():
                msg.append(self.write_buffer.get())

            logger.debug("flushing buffer to transport")
            self.transport.send(msg)

    def close(self):
        """
        Close the socket. The ready_state change from STATE_OPEN -> STATE_CLOSING.
        When transport closed, the on_close be called and STATE_CLOSING -> STATE_CLOSED.
        :return:
        """
        if self.STATE_OPEN == self.ready_state:
            self.ready_state = self.STATE_CLOSING
            self.transport.close()
            self.on_close('closed by server')

    def put_client_msg(self, msg):
        """Writes to the client's pipe, to end up in the browser"""
        self.write_buffer.put(msg)

    def error(self, error_name, error_message, endpoint=None, msg_id=None,
              quiet=False):
        """Send an error to the user, using the custom or default
        ErrorHandler configured on the [TODO: Revise this] Socket/Handler
        object.

        :param error_name: is a simple string, for easy association on
                           the client side

        :param error_message: is a human readable message, the user
                              will eventually see

        :param endpoint: set this if you have a message specific to an
                         end point

        :param msg_id: set this if your error is relative to a
                       specific message

        :param quiet: way to make the error handler quiet. Specific to
                      the handler.  The default handler will only log,
                      with quiet.
        """
        handler = self.error_handler
        return handler(
            self, error_name, error_message, endpoint, msg_id, quiet)
