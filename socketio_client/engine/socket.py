import requests
from socketio.event_emitter import EventEmitter
from .transports import XHRPollingTransport


class Socket(EventEmitter):
    def __init__(self, host, port, transports=("polling", "websocket")):
        super(Socket, self).__init__()
        self.host = host
        self.port = port
        self.transports = transports

        self.transport = XHRPollingTransport(hostname=host, port=port)

    def connect(self):
        pass

    def packet(self, type, data):
        pass

    def send(self, data):
        pass

    def close(self):
        pass

    def handshake(self):
        response = requests.get()
