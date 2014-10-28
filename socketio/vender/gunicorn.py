from __future__ import absolute_import
from gevent.pywsgi import WSGIHandler
from gunicorn.workers.ggevent import GeventPyWSGIWorker
from socketio.server import SocketIOWSGIServer


# Avoid the attribute error on log
def log_request(self):
    log = self.server.log
    if log:
        if hasattr(log, "info"):
            log.info(self.format_request() + '\n')
        else:
            log.write(self.format_request() + '\n')

WSGIHandler.log_request = log_request


class Worker(GeventPyWSGIWorker):
    server_class = SocketIOWSGIServer
