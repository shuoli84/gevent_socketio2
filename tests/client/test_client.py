from gevent.monkey import patch_all
patch_all()
import gevent

from socketio_client.client import SocketIOClient
from tests.socketio_test_server import SocketIOServerBaseTest


class ClientTest(SocketIOServerBaseTest):
    show_log = False

    def test_client_open(self):
        client = SocketIOClient('http://%s:%s/socket.io/' % (self.host, self.port))

        context = {'flag': False}

        def on_open(err=None):
            context['flag'] = True

        job = gevent.spawn(client.open, on_open)
        gevent.sleep(.5)

        self.assertTrue(context['flag'])

        socket = client.socket('chat')
        socket.emit('message', {'what': 'the'})

        self.assertEqual('websocket', client.engine_socket.transport.name)
        gevent.sleep(2)
        gevent.kill(job)
