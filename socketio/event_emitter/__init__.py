from collections import defaultdict


class EventEmitter(object):
    def __init__(self):
        """
        Initializes the EE.
        """
        self._events = defaultdict(lambda: [])
        self._keys = defaultdict(lambda: [])

    def on(self, event, f=None, key=None):
        """
        Returns a function that takes an event listener callback
        """
        def _on(f):
            # Add the necessary function
            self._events[event].append(f)

            if key is not None:
                self._keys[key].append((event, f))

        if f is None:
            return _on
        else:
            return _on(f)

    def emit(self, event, *args, **kwargs):
        """
        Emit `event`, passing *args to each attached function.
        """

        # Pass the args to each function in the events dict
        for fxn in self._events[event]:
            fxn(*args, **kwargs)

    def once(self, event, f=None, key=None):
        def _once(f):
            def g(*args, **kwargs):
                f(*args, **kwargs)
                self.remove_listener(event, g)
            return g

        if f is None:
            return lambda f: self.on(event, _once(f), key)
        else:
            self.on(event, _once(f), key)

    def remove_listener(self, event, function):
        """
        Remove the function attached to `event`.
        """
        if function in self._events[event]:
            self._events[event].remove(function)

    def remove_all_listeners(self, event):
        """
        Remove all listeners attached to `event`.
        """
        self._events[event] = []

    def listeners(self, event):
        return self._events[event]

    def remove_listeners_by_key(self, key, event=None):
        """
        Remove all listeners attached with key
        :param key: The unique id. Normally id(sender)
        :param event: The event name, None as remove all
        """

        # TODO Clean the _keys dict
        events = event if event is not None else self._events.keys()

        if key in self._keys:
            for event, f in self._keys[key]:
                if event in events:
                    self.remove_listener(event, f)
