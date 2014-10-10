# coding=utf-8
from pyee import EventEmitter
from webob.response import Response as WSGIResponse
from gevent.event import Event


class Response(WSGIResponse, EventEmitter):
    """
    The Main reason for this class is make the response waitable. The primary event loop can listen on response
    when end() called anywhere, the main loop activated and it can send the response to client.
    """

    class ResponseAlreadyEnded(Exception):
        pass

    def __init__(self, *args, **kwargs):
        self.event = Event()
        super(Response, self).__init__(*args, **kwargs)
        EventEmitter.__init__(self)

    def end(self, status_code=None, body=None):
        self.emit('pre_end')
        if self.event.is_set():
            raise Response.ResponseAlreadyEnded('response already ended, did you call response.end() several times?')

        if status_code is not None:
            self.status_code = status_code

        if body is not None:
            self.body = body

        self.event.set()
        self.emit('post_end')

    def join(self):
        """
        Wait on the response object
        """
        return self.event.wait()

    @property
    def is_set(self):
        """
        :return:  Whether the response object already ended
        """
        return self.event.is_set()
