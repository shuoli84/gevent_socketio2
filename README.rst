Introduction
============================================

We love socketio. `gevent_socketio <https://github.com/abourget/gevent-socketio>`_ 
implements socketio 0.7, this project intend to bring socketio 1.0 to python(gevent) world. It started as a fork of gevent_socketio. This project
mainly is a port of socketiojs project, so you can see EventEmitter in code. Some code not that clean due to the port, which needs 
further refine. 

Now the library is still in development. But you can get a working chat following `chat sample <https://github.com/shuoli84/django_socketio_test>`_

Installation
============================================

pip install gevent_socketio2

Some key technical points:
============================================

* WSGI Handler and WSGI Server
* Event loops
  In EngineHandler, the handle_one_response waits on Response. Response holds a gevent Event, which will be set when response.end() called.
    By doing this, we can end the response at any point, cleaner code.
  In Websocket transport, we spawn a read loop, which reads frame from websocket and call transport.on_data, which feeds data to engine socket.


Current stage:

engineiojs

- Parser (Done)
- Transports (XHRPolling done, websocket done, JSONP Polling in progress) 
- Server (Done)
- Socket (Done)

socketiojs:

- Middleware (Not started)
- Namespace (Done)
- Server (Done)
- Client (Implemented, not tested)
- Adapter (Implemented, not tested)
- Text message (Done)
- Binary message (Done)
- ........


I created a `chat sample <https://github.com/shuoli84/django_socketio_test>`_, tested on safari, chrome. 



.. toctree::
   :maxdepth: 2

Contribution
==============================================

Any contribution welcomed, bug fix, sample, blog. Lets make python more realtime.
