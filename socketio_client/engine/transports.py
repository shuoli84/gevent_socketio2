import time
import datetime
import urllib
import urlparse
import requests
from socketio.engine import parser
from socketio.event_emitter import EventEmitter
import logging

logger = logging.getLogger(__name__)


class Transport(EventEmitter):
    timestamps = 0
    protocol_version = 3

    def __init__(self, path, host, port,
                 secure=False, query=None, agent=None,
                 support_xdr=True):
        self.path = path
        self.hostname = host
        self.port = port
        self.secure = secure
        self.query = query
        self.ready_state = None
        self.agent = agent
        self.writable = False
        super(Transport, self).__init__()

    def on_error(self, msg, desc):
        self.emit("error", msg, desc)

    def open(self):
        if 'closed' == self.ready_state or self.ready_state is None:
            self.ready_state = 'opening'
            self.do_open()

    def close(self):
        if 'opening' == self.ready_state or 'open' == self.ready_state:
            self.do_close()
            self.on_close()

    def send(self, packets):
        if 'open' == self.ready_state:
            self.write(packets)

        else:
            raise ValueError("Transport not open")

    def write(self, packets):
        raise NotImplementedError()

    def on_open(self):
        self.ready_state = 'open'
        self.writable = True
        self.emit('open')

    def on_data(self, data):
        packet = parser.Parser.decode_packet(data)
        self.on_packet(packet)

    def on_packet(self, packet):
        self.emit('packet', packet)

    def on_close(self):
        self.ready_state = 'closed'
        self.emit('close')

    def do_close(self):
        raise NotImplementedError()

    def do_open(self):
        raise NotImplementedError()


class PollingTransport(Transport):
    name = "polling"

    def __init__(self, force_base64=False, *args, **kwargs):
        self.force_base64 = force_base64
        self.supports_binary = not self.force_base64
        self.polling = False
        self.sid = None
        super(PollingTransport, self).__init__(*args, **kwargs)

    def pause(self, on_pause):
        """
        Pause polling
        :param on_pause: callback when transport paused
        :return:
        """
        self.ready_state = 'pausing'
        context = {"total": 0}

        def pause():
            logger.debug("paused")
            self.ready_state = 'paused'
            on_pause()

        if self.polling or not self.writable:
            context["total"] = 0

            def on_poll_complete():
                    logger.debug("pre-pause polling complete")
                    context["total"] -= 1

                    if not context["total"]:
                        pause()

            if self.polling:
                logger.debug("we are currently polling - waiting to pause")
                context["total"] += 1
                self.once("poll_complete", on_poll_complete)

            if not self.writable:
                logger.debug("we are currently writing - waiting to pause")
                context["total"] += 1
                self.once("drain", on_poll_complete)
        else:
            pause()

    def poll(self):
        logger.debug("polling")
        self.polling = True
        self.do_poll()
        self.emit("poll")

    def do_poll(self):
        raise NotImplementedError()

    def on_data(self, data):
        logger.debug("polling got data %s", data)

        for packet, index, total in parser.Parser.decode_payload(data):
            if 'opening' == self.ready_state:
                self.on_open()

            if 'close' == packet['type']:
                self.on_close()
                return False

            # bypass and handle the message
            self.on_packet(packet)

        if 'closed' != self.ready_state:
            self.polling = False
            self.emit("poll_complete")

            if 'open' == self.ready_state:
                self.poll()
            else:
                logger.debug('ignoring polling - transport state "%s"', self.ready_state)

    def on_close(self):
        """
        Send a close packet
        :return:
        """
        def close():
            logger.debug('writing close packet')
            self.write([{"type": "close"}])

        if 'open' == self.ready_state:
            logger.debug("transport open - closing")
            close()
        else:
            logger.debug("transport not open - deferring close")
            self.once("open", close)

    def write(self, packets):
        self.writable = False
        encoded = parser.Parser.encode_payload(packets, self.supports_binary)
        self.do_write(encoded)
        self.writable = True
        self.emit('drain')

    def do_write(self, data):
        raise NotImplementedError()

    def uri(self):
        schema = 'https' if self.secure else 'http'
        port = ''
        query = {
            'EIO': self.protocol_version,
            'transport': self.name,
            't': time.mktime(datetime.datetime.now().timetuple()) * 1000
        }

        if not self.supports_binary and self.sid is None:
            query["b64"] = 1

        query = urllib.urlencode(query)

        if self.port is not None and (('https' == schema and self.port != 443) or ('http' == schema and self.port != 80)):
            port = ':' + str(self.port)

        if len(query) > 0:
            query = '?' + query

        return urlparse.urljoin(schema + '://' + self.hostname + port, self.path) + query


class XHRPollingTransport(PollingTransport):
    def __init__(self, *args, **kwargs):
        super(XHRPollingTransport, self).__init__(force_base64=False, **kwargs)

        self.supports_binary = True
        self.data_response = None
        self.poll_response = None

    def do_write(self, data):
        response = self.request(method='POST', data=data)

        if 300 > response.status_code >= 200:
            self.on_load(response)
        elif response.status_code >= 400:
            self.on_error('xhr request failed', response.content)

    def do_poll(self):
        logger.debug('xhr poll')
        response = self.request()

        if 300 > response.status_code >= 200:
            self.on_load(response)
        elif response.status_code >= 400:
            self.on_error('xhr request failed', response.content)

    def request(self, data=None, method='GET'):
        """
        :param data: The data to be send
        :param method: GET or POST
        :return:
        """

        content_type = None
        if method == 'POST':
            # TODO Use the has_bin func to check?
            is_binary = type(data) is bytearray
            if is_binary:
                content_type = "application/octet-stream"
            else:
                content_type = "text/plain;charset=UTF-8"

        if method == 'GET':
            request_func = requests.get
        else:
            request_func = requests.post

        uri = self.uri()
        return request_func(uri, data=data, headers={"Content_Type": content_type})

    def on_load(self, response):
        content_type = response.headers["content-type"]
        if content_type == 'application/octet-stream':
            data = bytearray(response.content)
        else:
            if not self.supports_binary:
                data = response.content
            else:
                data = 'ok'

        self.on_data(data)
