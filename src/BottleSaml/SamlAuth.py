"""
SamlSP - Authentication/Authorization middleware for Bottle

- provides route based authentication and authorization

- provides path prefix based authentication and authroization

- Two authentication modes: (determined by authn_all_routes)
    - Opt-Out mode: authenticates all routes unless they opt-out
    - Opt-In mode: routes requiring authentication or authorization must opt-in 

- Bottle Plugin API v2

"""
import sys
from bottle import request, response, PluginError


class SamlAuth:
    """
SAML Authentication Middleware

auth = SamlAuth(saml, authn_all_routes, authz_by_prefix, log=None)

'saml'              SamlSP() instance

'authn_all_routes'  [Bool] Require login for all routes e.g. Opt-Out(def: True)

'authz_by_prefix'    [dict] dict of path prefix to authz requirements

'log'               A logger instance (Optional)  default log is None - log to stderr

"""

    name = 'SamlAuth'       # Bottle Plugin API v2 required
    api = 2                 # Bottle Plugin API v2 required

    def __init__(self, saml, authn_all_routes=True, authz_by_prefix={}, log=None, **kwargs):

        self.saml = saml
        
        self.authn_all_routes = authn_all_routes

        self.log = log if log else _Log()

        # Authorization requirements based on path prefix  
        # authz_by_prefix = {'/path': {attr:val,...}}, '/path2': {attr:val,...}}, ...]
        self.authz_by_prefix = authz_by_prefix

        # list of apply checks - ORDER MATTERS for decorators 
        self.apply_checks = [
            self.__apply_require_attrs, 
            self.__apply_prefix_attrs,
            self.__apply_require_authn   # the last shall be first in request path
            ]

        if 'app' in kwargs:
            kwargs['app'].install(self)


    def setup(self, app):   # Bottle Plugin API v2 
        """
        setup(app)

        - verify this is the only instance
        """
        # Only one instance of SamlSP per app
        for plugin in app.plugins:

            if plugin == self:
                # loading ourself more than once is ignored
                return

            if isinstance(plugin, SamlAuth):
                # more than one instance of SamlAuth is not supported.
                emsg = f'\n\nError: Can not install a second instance of SamlAuth\n'
                raise PluginError(emsg)

        # report installed
        self.log.info(f"SAMLAuth: Authenticating in OPT-{'OUT' if self.authn_all_routes else 'IN'} mode")
    

    def apply(self, f, route):
        """
        apply() - Bottle Plubin API v2 required

        - apply decorators for f based on route.config
        - run through self.apply_checks list
        - the lowest in the request stack is the last applied (ORDER MATTERS)
        """

        nextf = f

        for apply_check in self.apply_checks:
            nextf = apply_check(nextf, route)  
        return nextf            


    def close(self):
        """
        close() - Bottle Plugin API v2 
        - no action placeholder
        """
        pass


    def __apply_require_authn(self, f, route):
        """
        __apply_requier_authn()

        Apply authentication (authn) requirement for a route

        - applied to all routes 
        - if 'authn_all_routes' is True (Opt-Out mode):
                apply to all routes
        - else (authn_all_routes is False) (Opt-In mode)
                apply if 'authz' or 'authn' decorator is found
        - skipped if 'authn=False' is set in route.config
        - if user is not authenticated, call inititate_logon()

        """

        if route.config.get('authn') is False:
            # authn is neither True nor None - set explicity False
            self.log.info(f'SAMLAuth: Skipping authn (explict) on {route.rule}')

        elif self.authn_all_routes or \
            route.config.get('authn', False) or \
            route.config.get('authz', False):
            
            # install the force authen decorator
            def auth_required(*args, **kwargs):
                """ Require authenticated user """

                if self.saml.is_authenticated: 

                    return f(*args, **kwargs)
                    
                else:
                    return self.saml.initiate_login(next = request.url)

            self.log.info(f'SAMLAuth: Applying authn required to {route.rule}')
            
            auth_required.__name__ = f.__name__
            return auth_required

        # this decorator not applied.
        return f
    
 
    def __apply_require_attrs(self, f, route):
        """ 
        __apply_require_attrs()

        Apply attribute (authz) restriction on a route

        - apply if route contains 'authz' restriction
        - multiple attributes can be provided
        - multiple test values can be provided
        - all attribute requirements must be met
        - needs only one value match is required to match
        - raises UnauthorizedError (403 Permission not granted) on match failure 
        """
        
        req_attrs = route.config.get('authz', False)
        if req_attrs:
            # apply attribute requirements on a specific route
            
            def authz_required(*args, **kwargs):
                """ Require attribute match """

                session = request.session
                my_attrs = self.saml.my_attrs

                # check each attribute to test
                for attr in req_attrs:
                    value = req_attrs[attr]

                    # if session.attributes doesn't have the attr 
                    #   or none of its values matches one we're looking for
                    #     Return Unauthorized 
                    if attr not in my_attrs or \
                        not test_attrs(session['attributes'][attr], value):

                        return UnauthorizedError('Permission not granted')
                
                # all tests have passed to get here
                return f(*args, **kwargs)

            self.log.info(f'SAMLAuth: Applying route authz to {route.rule}')

            authz_required.__name__ = f.__name__
            return authz_required

        else:
            return f


    def __apply_prefix_attrs(self, f, route):
        """
        __apply_prefix_attrs()

        Apply required attributes (authz) by prefix match to route.path
        (Currently undocumented)

        - only add restrictions if authn_all_routes==True (authn OPT-OUT mode)
        - use self.authz_by_prefix   {'/prefix': {attr:val,..},..}
        - if the route.rule (path) matches prefix, add those required attributes
        """
        req_attrs={}

        # prefix authorization is opt-out mode only
        if self.authn_all_routes:

            for prefix in self.authz_by_prefix:

                if route.rule.startswith(prefix):
                    # add/replace in req_attrs list
                    req_attrs.update(self.authz_by_prefix[prefix])
        
        if not req_attrs:
            # no path-based attribute checks
            return f
        
        # Adding wrapper for path-based attribute checks
        def authz_required_path(*args, **kwargs):
            """ Require Attribute match """

            session = request.session
            my_attrs = self.saml.my_attrs
            
            # check each attribute to test
            for attr in req_attrs:
                value = req_attrs[attr]

                # if session.attributes doesn't have the attr 
                #   or none of its values matches one we're looking for
                #     Return Unauthorized 
                if attr not in my_attrs or \
                    not test_attrs(session['attributes'][attr], value):

                    return UnauthorizedError('Permission not granted')
            
            # all tests have passed to get here
            return f(*args, **kwargs)

        self.log.info(f'SAMLAuth: Applying prefix authz to {route.rule}')

        authz_required_path.__name__ = f.__name__
        return authz_required_path
#
# Helper routines
#
def test_attrs(challenge, standard):
    """
    test_attrs()

    Compare list or val the standard.
    
    - return True if at least one item from chalange list is in standard list
    - False if no match
    """

    stand_list = standard if type(standard) is list else [standard]
    chal_list = challenge if type(challenge) is list else [challenge]

    for chal in chal_list:
        if chal in stand_list:
            return True
    return False


def UnauthorizedError(body, hdrs=None):
        response.status = 401
        response.body = body
        response.headers.update({
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Expires': 'Sun, 25 Jul 2021 15:42:14 GMT'
        })
        return response


class _Log:
    """
    Mock logger - mocks flask's logger.
    """
    level = 'info'

    def info(self, *args, **kwargs):
        if self.level in ['info']:
            print('INFO - ', *args, **kwargs, file=sys.stderr)

    def warn(self, *args, **kwargs):
        print('WARN', *args, **kwargs, file=sys.stderr)

    def debug(self, *args, **kwargs):
        print('DEBUG', *args, **kwargs, file=sys.stderr)

    def error(self, *args, **kwargs):
        print('ERROR', *args, **kwargs, file=sys.stderr)

