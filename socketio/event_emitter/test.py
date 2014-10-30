from unittest import TestCase
from socketio.event_emitter import EventEmitter


class Emitter(EventEmitter):
    pass


class EventEmitterTest(TestCase):
    def test_remove_by_key(self):
        e = Emitter()
        context = {
            'john': 0,
            'lily': 0,
        }

        def john():
            context['john'] += 1

        def lily():
            context['lily'] += 1

        e.on('event1', john, 1)
        e.on('event1', lily, 1)
        e.on('event2', john, 1)

        e.emit('event1')
        e.emit('event2')

        self.assertEqual(2, context['john'])
        self.assertEqual(1, context['lily'])

        e.remove_listeners_by_key(2)
        e.remove_listeners_by_key(1, 'event2')

        e.emit('event1')
        e.emit('event2')

        self.assertEqual(3, context['john'])

