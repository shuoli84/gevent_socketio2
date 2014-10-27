from setuptools import setup
setup(
  name = 'gevent_socketio2',
  packages = ['socketio', 'socketio.engine', 'socketio.event_emitter'],
  version = '0.1.5',
  description = 'A gevent implementation for socketio protocol 1.0',
  author = 'Shuo Li',
  author_email = 'shuoli84@gmail.com',
  url = 'https://github.com/shuoli84/gevent_socketio2',
  keywords = ['socketio', 'gevent', 'realtime'],
  classifiers = [],
  license='MIT',
  install_requires=[
    'greenlet==0.4.4',
    'gevent-websocket==0.9.3',
    'WebOb==1.4',
    'pyee==0.1.0',
  ],
)
