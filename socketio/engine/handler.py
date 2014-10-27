# coding=utf-8
from __future__ import absolute_import

import gevent
from gevent.pywsgi import WSGIHandler
from pyee import EventEmitter
import sys
from webob import Request
from .response import Response
from .socket import Socket
from .transports import WebsocketTransport
import logging

logger = logging.getLogger(__name__)

__all__ = ['EngineHandler']


class EngineHandler(WSGIHandler, EventEmitter):
    """
    The WSGIHandler for EngineServer
    It filters out interested requests and process them, leave other requests to the WSGIHandler
    """
    transports = ('polling', 'websocket')

    def __init__(self, server_context, *args, **kwargs):
        super(EngineHandler, self).__init__(*args, **kwargs)
        EventEmitter.__init__(self)

        self.server_context = server_context

        if self.server_context.transports:
            self.transports = self.server_context.transports

    def handle_one_response(self):
        """
        There are 3 situations we get a new request:
        1. Handshake.
        2. Upgrade.
        3. Polling Request.

        After the transport been upgraded, all data transferring handled by the WebSocketTransport
        """
        path = self.environ.get('PATH_INFO')

        if not path.lstrip('/').startswith(self.server_context.resource + '/'):
            return super(EngineHandler, self).handle_one_response()

        # Create a request and a response
        request = Request(self.get_environ())

        # TODO consider use weakref for all circular reference. Though python's GC handles this
        setattr(request, 'handler', self)
        setattr(request, 'response', Response())

        sid = request.GET.get("sid", None)
        b64 = request.GET.get("b64", False)

        socket = self.server_context.engine_sockets.get(sid, None)

        if socket is None:
            socket = self._do_handshake(b64=b64, request=request)
        elif 'Upgrade' in request.headers:
            # This is the ws upgrade request, here we handles the upgrade
            ws_handler = self.server_context.ws_handler_class(self.socket, self.client_address, self.server)
            ws_handler.__dict__.update(self.__dict__)
            ws_handler.prevent_wsgi_call = True
            ws_handler.handle_one_response()
            # Suppose here we have an websocket connection
            setattr(request, 'websocket', ws_handler.websocket)
            ws_transport = WebsocketTransport(self, {})
            ws_transport.process_request(request)
            socket.maybe_upgrade(ws_transport)
        else:
            # We spawn a new gevent here, let socket do its own business.
            # In current event loop, we will wait on request.response, which is set in socket.set_request
            gevent.spawn(socket.process_request, request)

        # Run framework's wsgi application to hook up framework specific info eg. request
        # This is why we define /socket.io url in web frameworks and points them to a view
        self.environ['engine_socket'] = socket
        try:
            start_response = lambda status, headers, exc=None: None
            self.application(self.environ, start_response)
        except:
            self.handle_error(*sys.exc_info())

        # wait till the response ends
        request.response.join()

        # The response object can be used as a wsgi application which will send out the buffer
        self.application = request.response

        # Call super handle_one_repsponse() to do timing, logging etc
        super(EngineHandler, self).handle_one_response()

        self.emit('cleanup')

    def _do_handshake(self, b64, request):
        """
        handshake with client to build a socket
        :param b64:
        :param request:
        :return:
        """
        transport_name = request.GET.get('transport', None)
        if transport_name not in self.transports:
            raise ValueError("transport name [%s] not supported" % transport_name)

        socket = Socket(request)

        self.server_context.engine_sockets[socket.id] = socket

        def remove_socket(*args, **kwargs):
            self.server_context.engine_sockets.pop(socket.id)
        socket.on('close', remove_socket)

        request.response.headers['Set-Cookie'] = 'io=%s' % socket.id
        socket.open()

        self.emit('connection', socket)
        return socket
