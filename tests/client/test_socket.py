from gevent.monkey import patch_all
from socketio.server import SocketIOServer

patch_all()
import gevent

from socketio_client.client import SocketIOClient
from tests.socketio_test_server import SocketIOServerBaseTest


class ClientTest(SocketIOServerBaseTest):
    show_log = False

    def setUp(self):
        super(ClientTest, self).setUp()
        # Setup a chat namespace

        ns = SocketIOServer.default_server.of('chat')
        ns.on('message', ClientTest.on_message)

        def message(socket):
            socket.on('message', ClientTest.on_message)

        ns.on('connection', message)


    @classmethod
    def on_message(cls, data):
        print data

    def test_client_open(self):
        client = SocketIOClient('http://%s:%s/socket.io/' % (self.host, self.port))
        job = gevent.spawn(client.open)
        gevent.sleep(.5)

        socket = client.socket('chat')
        socket.emit('message', {'what': 'the'})

        self.assertEqual('websocket', client.engine_socket.transport.name)
        gevent.sleep(2)
        gevent.kill(job)
