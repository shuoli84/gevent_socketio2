import logging
from unittest import TestCase
import gevent
import sys
from socketio.engine.server import serve
from tests import application


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

    def setUp(self):
        self.job = gevent.spawn(serve, application, host=self.host, port=self.port)
        logging.basicConfig(stream=sys.stderr)

    def tearDown(self):
        print "Killing [%d] jobs" % len(self.jobs)
        gevent.killall(self.jobs)
        gevent.sleep(.5)

    def spawn(self, *args, **kwargs):
        self.jobs.append(gevent.spawn(*args, **kwargs))