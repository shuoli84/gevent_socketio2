Introduction
============================================

SocketIO Server implementation under gevent, at first I tried to make a pull to gevent-socketio to support 1.0, but the code changed
dramatically, and it is better to start as a new project and rewrite all the codes. 

Now the library is still in development.

Sample Project
================

**sample project** [https://github.com/shuoli84/django_socketio_test]

Installation
============================================

pip install gevent_socketio2

Features
===========

Most of socketio 1.0 features but ACK, BINARY_ACK. The reason why those not supported yet is I didn't use them in my project,
if you need this, open a issue or make a pull request, I am more than happy to merge it.

Usage
===========

Django + gevent
--------------

After installation
```
add 'socketio' to INSTALLED_APPS
create a custom command "run.py" under rootapp/management/commands/
```

```python
# coding=utf-8
import os
from socketio.server import serve

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_socketio_test.settings")
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **options):
        from django.core.wsgi import get_wsgi_application
        application = get_wsgi_application()
        serve(application, host='127.0.0.1', port='8001')  # Use our server to hook things up
```

In your urls.py, add 
```python
url(r'^socket\.io/', include(urls)),  # Used to attach framework specific request to socket
```

in any app, create a file "sockets.py"
```python
from socketio.decorators import namespace

@namespace('/echo')
class EchoNamespace(object):
    clients = {}

    @classmethod
    def on_connect(cls, socket):
        print 'on connect'
        if socket.id not in cls.clients:
            cls.clients[socket.id] = socket

        if cls.job is None:
            cls.job = gevent.spawn(cls.send_picture)

    @classmethod
    def on_disconnect(cls, socket):
        cls.clients.pop(socket.id, None)

    @classmethod
    def on_message(cls, socket, message):
        print 'received new message %s' % message
        logger.info('received new message %s', message)
        socket.namespace.emit('message', message)
```

run
```python
python manage.py run
```


Server supports
===========

Gevent

Gunicorn

[Other wsgi based server could be added easily]
