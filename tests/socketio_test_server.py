from socketio.server import serve
from tests.engineio_test_server import EngineIOServerBaseTest
from tests import application


class SocketIOServerBaseTest(EngineIOServerBaseTest):

    def start_server(self):
        self.spawn(serve, application, host=self.host, port=self.port)
