from gevent.monkey import patch_all
patch_all()
import gevent

from socketio_client.client import SocketIOClient
from tests.socketio_test_server import SocketIOServerBaseTest


class ClientTest(SocketIOServerBaseTest):
    def test_client_open(self):
        client = SocketIOClient('http://%s:%s/socket.io/' % (self.host, self.port))

        context = {'flag': False}

        def on_open(err=None):
            context['flag'] = True

        job = gevent.spawn(client.open, on_open)
        gevent.sleep(.5)
        print client.engine_socket.ready_state

        socket = client.socket('chat')
        socket.emit('message', {'what': 'the'})

        gevent.sleep(.2)

        gevent.kill(job)
