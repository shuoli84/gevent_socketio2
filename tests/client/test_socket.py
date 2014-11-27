from gevent.monkey import patch_all
patch_all()
import gevent
from socketio.server import SocketIOServer
from socketio_client.client import SocketIOClient
from tests.socketio_test_server import SocketIOServerBaseTest


def callback(event, data=None):
    print 'callback' + unicode(data)

class SocketTest(SocketIOServerBaseTest):
    show_log = True

    def setUp(self):
        super(SocketTest, self).setUp()

        ns = SocketIOServer.default_server.of('chat')
        ns.on('message', SocketTest.on_message)

        def message(socket):
            socket.on('message', SocketTest.on_message)
            socket.emit('message', {'hello': 'world'}, callback=callback)
            socket.emit('message', {'hello': True, 'world': bytearray('world')}, callback=callback)

        ns.on('connection', message)


    @classmethod
    def on_message(cls, data):
        print data

    @classmethod
    def on_socket_message(cls, data, **kwargs):
        print "Client Socket: " + str(data) + str(kwargs)

    def test_socket(self):
        client = SocketIOClient('http://%s:%s/socket.io/' % (self.host, self.port))
        job = gevent.spawn(client.open)
        gevent.sleep(.5)

        socket = client.socket('chat')
        socket.emit('message', {'what': 'the'}, callback=callback)

        socket.on('message', self.on_socket_message)

        self.assertEqual('websocket', client.engine_socket.transport.name)
        gevent.sleep(.2)

        # Test sending message from server
        namespace = SocketIOServer.default_server.of('chat')
        namespace.emit("message", {"hell": "!"})
        gevent.sleep(1)
        gevent.kill(job)
