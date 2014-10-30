from unittest import TestCase
import gevent
import sys
from socketio.engine.server import serve
from tests import application
import logging

logger = logging.getLogger()
logger.level = logging.DEBUG
stream_handler = logging.StreamHandler(sys.stdout)
logger.addHandler(stream_handler)


class EngineIOServerBaseTest(TestCase):
    def __init__(self, *args, **kwarg):
        self.host = '127.0.0.1'
        self.port = 3030
        self.root_url = 'http://%(host)s:%(port)d/socket.io/' % {
            'host': self.host,
            'port': self.port
        }
        self.jobs = []
        super(EngineIOServerBaseTest, self).__init__(*args, **kwarg)

    def start_server(self):
        self.spawn(serve, application, host=self.host, port=self.port)

    def setUp(self):
        logging.basicConfig(stream=sys.stderr)
        self.start_server()

    def tearDown(self):
        print "Killing [%d] jobs" % len(self.jobs)
        gevent.killall(self.jobs)
        gevent.sleep(.5)

    def spawn(self, *args, **kwargs):
        self.jobs.append(gevent.spawn(*args, **kwargs))