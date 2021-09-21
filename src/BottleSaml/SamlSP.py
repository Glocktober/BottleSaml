"""
SamlSP - SAML2 Service Provider for Bottle 

- Not strictly middlware, SamlSP creates SAMLRequests, validates SAMLResponses,
  and adds SAML assertions to session data.
  
- Requires BottleSessions (or another session manager that provides access to 
  the session via request.session)

- Assertion Control Service endpoint '/saml/acs' by default

"""
import os
import sys
import time
from urllib.parse import urlencode, parse_qs

from cryptography.hazmat.backends import default_backend
from cryptography.x509 import load_pem_x509_certificate
from minisaml.response import validate_response
from minisaml.request import get_request_redirect_url
from bottle import request, response

from .reqID import ReqID

"""
SAML Service Provider module for Bottle

saml = SamlSP(app, saml_config, log=None)

- Creates an instance if the saml service provider authenticator

app - a Bottle() application object

saml_config - Dict of SAML configuration parameters: (Required)

    'saml_endpoint'     URL of iDP endpoint
    'spid'              Our Service Provider entity id
    'issuer'            IdP's issuer identifier (generally a url)
    'force_reauth'      Force username/password on all iDP visits (def: False)
    'acs_url'           URL of our Assertion Control Service endpoint
    'user_attr'         SAML assertion to use for username (def: name_id)
    'auth_duration'     Number of seconds authentication considered valid (def: 3600)
    'assertions'        A list of assertions to collect for attributes (def: None)
    'certificate'        The IdP's public certificate for signing verification

log -   A logger instance (Optional) 
        default log is None - log to stderr
"""

class SamlSP:

    name = 'SamlSP'     # Bottle Plugin API v2 required
    api = 2             # Bottle Plugin API v2 required

    def __init__(self, app, sess, saml_config=None, log=None, **kwargs):

        config = saml_config

        # session manager
        self.sess = sess
        
        self.saml_endpoint = config['saml_endpoint']
        self.saml_audience = config['spid']
        self.saml_issuer = config['issuer']

        # Optional 'ForceAuth' to IdP
        self.force_reauth = config.get('force_reauth', False)

        # This is SAML claim we use to set 'username'
        self.attr_uid = config.get('user_attr', 'name_id')
        
        # A list of the SAML claims we will add to the session attribute
        temp_attrs = config.get('assertions', [])
        # Convert these all to lower case...
        self.saml_attrs = [attr.lower() for attr in temp_attrs ]

        # What our ACS URL is registered as with the IdP
        self.acs_url = os.environ.get('ACS_ENDPOINT', config.get('acs_url'))

        # Load IdP (public) certificate - use to validate assertions
        self.saml_certificate = load_pem_x509_certificate(
            config['certificate'].encode('utf-8'), default_backend())

        self.authn_all_routes = config.get('authn_all_routes', True)

        # how long till we expire the auth?
        self.auth_duration = config.get('auth_duration',3600)

        self.log = log if log else _Log()

        # login hooks - build_attrs_list must be first
        self.login_hooks = [self.__build_attrs_list]

        # Accept responses from IDP initiated requests
        self.idp_ok = config.get('idp_ok', True)
        
        # Request ID generator/validator
        self.reqid = ReqID(idpok=self.idp_ok, ttl=config.get('reqid_life',60))

        # Install the Assertion Control Service (ACS) endpoint
        app.route('/saml/acs', name='ACS', 
                callback=self.finish_saml_login, 
                method=['POST'], 
                skip=True)    # No middleware on this route
    

    @property
    def is_authenticated(self):
        """
        is_authenticated() (Property)
        - Return True iff:
            - request.session has a username
            - && the session has not expired
        """
        sess = request.session

        try:
            if sess['username'] and sess['attributes']['_saml']['expires'] >= int(time.time()):
                return True
        except:
            pass   

        return False
    

    @property
    def my_attrs(self):
        """ Return collected assertions for the current session. """

        return request.session['attributes'] if self.is_authenticated else {'status': 'unauthenticated'}


    def initiate_login(self, force_reauth=False, userhint=None, **kwargs):
        """
        saml.initiate_login(next, force_reauth, userhint, **kwargs) => Response
        
        - Builds and returns a SAMLRequest redirect to iDP to initiate login

        - parameters:
            force_reauth - When true, the IdP is requested to demand a full login
                        (i.e. not an SSO session) (optional)

            userhint - provides the IdP with username hint (optional)

            **kwargs - arguments added to relay state
        """

        # Create a request id
        request_id = self.reqid.new_requestID()

        # encode relay state
        relay_state = urlencode(kwargs, doseq=True) if kwargs else None
        
        # Build the URL with SAMLRequest
        url = get_request_redirect_url(
                saml_endpoint=self.saml_endpoint,
                expected_audience = self.saml_audience,
                acs_url = self.acs_url,
                force_reauthentication = self.force_reauth or force_reauth,
                request_id= request_id,
                relay_state= relay_state
            )

        if userhint:
            sep = '&' if '?' in url else '?'
            url = url + sep + 'login_hint=' + userhint
        
        self.log.info(f'SAML: SP created authentication request {request_id}')

        # Redirect user to IdP
        response.status = 302
        response.set_header('Location', url)
        set_no_cache_headers()
        return ''


    # /saml/acs
    def finish_saml_login(self):
        """
        Wrap session context for assertion control service
        """
        session = self.sess.open_session()

        ret = self.finish_saml_login_work(session)
        
        self.sess.close_session(session)
        
        return ret


    def finish_saml_login_work(self, session):
        """             
        Assertion Control Service endpoint (/saml/acs):

            Post to saml._finish_saml_login()

        - invoked as POST by browser on response from IdP
        - SAML response signing verified with IdP cert
        - Issuer verified
        - Claims gathered as attributes and optionally massaged with login_hooks
        - first login hook moves attributes from saml_response to a dict
        - attributes and username set into session object
        - redirect user to 'next' in RelayState or '/' if missing

        """ 
        
        if self.is_authenticated:
            return AppError('ACS invoked for authenticated user')

        relay_state = parse_qs(request.forms.get('RelayState',b''))

        try:
            raw_saml_resp = request.forms["SAMLResponse"]

            saml_resp = validate_response(
                    data=raw_saml_resp, 
                    certificate = self.saml_certificate, 
                    expected_audience = self.saml_audience
                )
            
        except Exception as e:
            msg = f'SAML: response_validation failed: {str(e)}'
            self.log.info(msg)
            #session.clear()
            return BadRequestError(msg)
            
        self.log.info(f'SAML: ACS received SAMLResponse to {saml_resp.in_response_to}')

        if self.reqid.validate_requestID(saml_resp.in_response_to) is False:
            msg = f'SAML: Invalid Request: "{saml_resp.in_response_to}"'
            self.log.info(msg)

            # If we're not allowing IdP initiated login,issue BadRequest
            return BadRequestError(msg)

        # Validate this was from where we requested it
        if saml_resp.issuer != self.saml_issuer:
            msg = f'SAML: Issuer mismatch: rcvd "{saml_resp.issuer}" expected "{self.saml_issuer}"'
            self.log.info(msg)
            return ConflictError(msg)

        # First login hook will convert saml_resp to dict
        username = saml_resp.name_id
        attrs = saml_resp

        try: 
            # Run all the login hooks.
            for login_hook in self.login_hooks:
                username, attrs = login_hook(username, attrs)

            # set the actual session values
            session['attributes'] = attrs
            session['username'] = username

            self.log.info(f'SAML: User "{saml_resp.name_id}" authenticated')
            
        except Exception as e:
            # failed hooks also fail the login
            msg = f'SAML: login_hooks failed: {str(e)}'
            self.log.info(msg)
            session.clear()
            return ForbiddenError(msg)

        # Quo vidas?
        if 'next' in relay_state:
            url = relay_state['next'][0]
        else:
            url = '/'

        self.log.info(f'SAML: Authenticated user {username} redirected to {url}')

        # Redirect back to the url that initiated the login           
        response.status = 302
        response.add_header('Location', url)
        set_no_cache_headers()
        return ''


    def add_login_hook(self, f):
        """ Add login hook Decorator """
        
        self.login_hooks.append(f)           
        return f


    def require_login(self, f):
        """ Require Login Decorator """

        def wrapper(*args, **kwargs):
            if self.is_authenticated:
                return f(*args, **kwargs)
            else:
                return self.initiate_login(next=request.url)
    
        wrapper.__name__ = f.__name__
        return wrapper


    def __build_attrs_list(self, username, saml_resp):
        """
        Build attribute list from SAML response.
        
        - This needs to be the first login hook
        - creates dict to replace minisaml.SamlResponse
        - items in self.attributes list are saved in the dict
        - sets username to attribute self.attr_uid, or response 'nameid' 
        - adds [_SAML] dict with authentication information
        - returns updated username and atttribute dict
        """

        attrs = {}
        for attr in saml_resp.attributes:
            # we can deliver singles and lists 
            # from what minisaml parsed

            if attr.name in self.saml_attrs:
                
                if len(attr.values)==1:
                    # single value
                    attrs[attr.name] = attr.values[0]

                elif len(attr.values)>1:
                    # list of values 
                    attrs[attr.name] = attr.values

                else:
                    # no values found
                    attrs[attr.name] = None

        # prefered username or use the name_id
        if self.attr_uid in attrs:
            username = attrs[self.attr_uid]
        
        if not 'username' in attrs:
            attrs['username'] = username

        attrs['_saml'] = {
            'name_id': saml_resp.name_id,
            'request_id': saml_resp.in_response_to,
            'issuer': saml_resp.issuer,
            'audience': saml_resp.audience,
            'expires': int(time.time()) + self.auth_duration
        }
            
        return username, attrs

def set_no_cache_headers():
    """
    Set various "no cache" headers for this response
    """

    # MDN recommended for various browsers
    response.add_header('Cache-Control', 'no-cache')
    response.add_header('Cache-Control', 'must-revalidate')
    response.add_header('Pragma', 'no-cache')
    response.add_header('Expires', 'Sun, 25 Jul 2021 15:42:14 GMT')


def response_error(status=401, body='', hdrs=None):
        response.status = status
        response.headers.update({
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Expires': 'Sun, 25 Jul 2021 15:42:14 GMT'
        })
        return body

def UnauthorizedError(body):
    return response_error(status=401, body=body)

def BadRequestError(body):
    return response_error(status=400, body=body)

def AppError(body):
    return response_error(status=400, body=body)

def ConflictError(body):
    return response_error(status=400, body=body)

def ForbiddenError(body):
    return response_error(status=403, body=body)

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

