import logging
from pyramid.exceptions import ConfigurationError
from pyramid.httpexceptions import HTTPNotFound, HTTPBadRequest

from pyramid_sockjs import transports
from pyramid_sockjs.session import Session, SessionManager
from pyramid_sockjs.websocket import HandshakeError
from pyramid_sockjs.websocket import init_websocket

log = logging.getLogger('pyramid_sockjs')

handler_types = {
    'websocket'    : (True, transports.WebSocketTransport),

    'xhr'          : (True, transports.XHRPollingTransport()),
    'xhr_send'     : (False, transports.XHRSendPollingTransport()),
    'xhr_streaming': (True, transports.XHRStreamingTransport),

    'jsonp'        : (True, transports.JSONPolling),
    'jsonp_send'   : (False, transports.JSONPolling),

    'htmlfile'     : (True, transports.HTMLFileTransport()),
    'iframe'       : (True, transports.IFrameTransport()),
}


def add_sockjs_route(cfg, name='', prefix='/__sockjs__',
                     session=Session, session_manager=None):
    # set session manager
    if session_manager is None:
        session_manager = SessionManager(name, cfg.registry, session=session)

    if not hasattr(cfg.registry, '__sockjs_managers__'):
        cfg.registry.__sockjs_managers__ = {}

    if name in cfg.registry.__sockjs_managers__:
        raise ConfigurationError("SockJS '%s' route is already registered"%name)

    cfg.registry.__sockjs_managers__[name] = session_manager

    # register routes
    sockjs = SockJSRoute(name, session_manager)

    if prefix.endswith('/'):
        prefix = prefix[:-1]

    route_name = 'sockjs-%s'%name
    cfg.add_route(route_name, '%s/{server}/{session}/{transport}'%prefix)
    cfg.add_view(route_name=route_name, view=sockjs.handler)

    route_name = 'sockjs-info-%s'%name
    cfg.add_route(route_name, '%s/info'%prefix)
    cfg.add_view(route_name=route_name, view=sockjs.info)

    route_name = 'sockjs-iframe-%s'%name
    cfg.add_route(route_name, '%s/iframe{version}.html')


class SockJSRoute(object):

    def __init__(self, name, session_manager):
        self.name = name
        self.session_manager = session_manager

    def handler(self, request):
        matchdict = request.matchdict

        # lookup transport
        tid = matchdict['transport']

        if tid not in handler_types:
            return HTTPNotFound()

        create, transport = handler_types[tid]

        # session
        manager = self.session_manager

        session = manager.acquire(matchdict['session'], create)
        if session is None:
            return HTTPNotFound()

        request.environ['sockjs'] = session

        # websocket
        if tid == 'websocket':
            try:
                init_websocket(request)
            except Exception as exc:
                return HTTPBadRequest(str(exc))

        try:
            return transport(session, request)
        except Exception as exc:
            log.exception('Exception in transport: %s'%tid)
            return HTTPBadRequest(str(exc))

    def info(self, request):
        request.response.body = str(map(str, []))
        return request.response

    def iframe(self, request):
        return request.response