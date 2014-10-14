def application(environ, start_response):
    """
    default test wsgi application
    :param environ:
    :param start_response:
    :return:
    """
    body = 'ok'
    headers = [('Content-Type', 'text/html; charset=utf8'),
               ('Content-Length', str(len(body)))]
    start_response('200 OK', headers)
    return [body]
