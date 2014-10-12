import logging

log = logging.getLogger(__name__)


def has_bin(arg):
    """
    Helper function checks whether args contains binary data
    :param args:
    :return: (bool)
    """
    if type(arg) is list or type(arg) is tuple:
        return reduce(lambda has_binary, item: has_binary or has_bin(item), arg, False)
    if type(arg) is bytearray or hasattr(arg, 'read'):
        return True
    if type(arg) is dict:
        return reduce(lambda has_binary, item: has_binary or has_bin(item), [v for k, v in arg.items()], False)

    return False
