# coding=utf-8
"""
The fork of socketio-adapter, which keeps track of all the sockets and able to broadcast packets
"""
import parser


class Adapter(object):
    """
    Adapter provides broadcast support
    """

    def __init__(self, namespace):
        super(Adapter, self).__init__()

        self.namespace = namespace
        self.rooms = {}
        self.sids = {}

    def add(self, id, room, callback=None):
        """
        Add the id to room
        :param id:
        :param room:
        :param callback:
        :return:
        """
        self.sids[id] = self.sids.get(id, {})
        self.sids[id][room] = True
        self.rooms[room] = self.rooms.get(room, {})
        self.rooms[room][id] = True

        if callback:
            callback()

    def remove(self, id, room, callback=None):
        """
        Remove the socket identified by id from room
        :param id:
        :param room:
        :param callback:
        :return:
        """
        self.sids[id] = self.sids.get(id, {})
        self.rooms[room] = self.rooms.get(room, {})
        del self.sids[id][room]
        del self.rooms[room][id]

        if not self.rooms[room]:
            del self.rooms[room]

        if callback:
            callback()

    def remove_all(self, id):
        """
        Remove the socket with id from this adapter, quit all rooms
        :param id:
        :return:
        """
        rooms = self.sids.get(id, None)
        if rooms:
            for room, flag in rooms.items():
                if room in rooms:
                    del rooms[room]

                if not self.rooms[room]:
                    del self.rooms[room]

        if id in self.sids:
            del self.sids[id]

    def broadcast(self, packet, options):
        """
        Broadcast a packet to all rooms passed by options['rooms'], if no rooms, then broadcast to all
        :param packet:
        :param options:
        :return:
        """
        rooms = options.get('rooms', [])

        # TODO what if exceptions list is long, should we use set
        exceptions = options.get('except', [])

        # ids set used to track which socket already send
        ids = set()

        packet['nsp'] = self.namespace.name

        # Encode once for all sockets
        encoded = parser.Encoder.encode(packet)

        if len(rooms) > 0:
            for room in rooms:
                if room not in self.rooms:
                    continue
                for id in self.rooms[room].keys():
                    if id in ids or id in exceptions:
                        continue
                    socket = self.namespace.connected[id]
                    if socket:
                        socket.packet(encoded, pre_encoded=True)
                        ids.add(socket.id)
        else:
            for id in self.sids.keys():
                if id in exceptions:
                    continue
                socket = self.namespace.connected[id]
                if socket:
                    socket.packet(encoded, pre_encoded=True)
