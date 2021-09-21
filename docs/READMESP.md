 ## BottleSaml - SAML Service Provider for Bottle

The **BottleSaml.SamlSP** [module](../README.md) implements a SAML Service Provider class for the [Bottle web framework.](https://github.com/bottlepy/bottle) 

This module Implements a SAML v2 [*Service Provider* (SP)](https://en.wikipedia.org/wiki/Service_provider_(SAML)) 
* Creates SAMLRequests, validates SAMLResponses, and adds SAML assertions into to session data.
  
* Establishes an Assertion Control Service (ACS) endpoint '/saml/acs'

* Makes available SAML **assertions** are to other middleware and views as a Python `dict` maintained in the user session data.

* Utilizes [BottleSessions](https://github.com/Glocktober/BottleSessions) to provide simple access to the SAML protocol provided assertion data.

* Uses @HENNGE's excellent [minisaml implementation](https://github.com/HENNGE/minisaml).

* Complies with [Bottle Plugin API v2](https://bottlepy.org/docs/dev/plugindev.html).

**BottleSaml** is the name of the module, **SamlSP** is the bottle plug-in class implementing the SP functionality. My testing has been tested Azure AD and SimpleSamlPHP IdPs.

## Quickstart
> pypi installation:
```bash
# python3 -m pip install BottleSaml
```
This will load required modules, including bottle, BottleSession and minisaml, and their dependencies.
### Initializing SamlSP
> Adding SamlSP to a bottle app:
```python
# Imports
from bottle import Bottle
from BottleSessions import BottleSessions   
from BottleSaml import SamlSP  

# import SAML configuration (see below)
from config import saml_config, cache_config              

# Create a Bottle application context
app = Bottle()                              

# Install session middleware
sess = BottleSessions(app, session_backing=cache_config)     

saml = SamlSP(app,sess=sess, saml_config=saml_config)   # SAML Service Provider
```

The **`saml_config`** is a Python `dict` containing the necessary information to use the [SAML IdP](https://en.wikipedia.org/wiki/Identity_provider_(SAML)) (and a few configuration parameters). The parameters needed for configuring `saml_config` are discussed later. The [SamlSP class is discussed here](SAMLSPCLASS.md), cover some other features, [such as login hooks.](LOGINHOOKS.md)
### Using the SAML data
```python
# require_login decorator initiates SAML IdP login
@app.route('/login')
@saml.require_login         
def hello_user():
    return f"Hello {request.session['username']}"

# is_authenticated indicates login status
@app.route('/')
def index():
    if saml.is_authenticated:
        return "You are authenticated"
    else:
        return "You need to login first"

# simple way to logout (withou a SAML Logout)
@app.route('/logout')
def logout_view():
    request.session.clear()
    return 'OK'

app.run(port=8000, debug=True, reloader=True)
```

## Accessing SAML Attributes from Views and Middleware
The saved attributes and values are accessible to views and other middleware in the users session. For instance, you can pre-populate a form with the authenticated user's name, department, email, and other data you acquire from the IdP.
> Using SAML provided user data
```python
@app.route('/whoami')
@saml.login_required
def whoami():
    return request.session['username']

@app.routes('/allattributes')
@saml.login_required
def allattrs():
    return request.session['attributes']

@app.route('/admins')
@saml.login_required
def admins_only():
    if 'sysadmin' in request.session['attributes']['groups]:
        return 'Welcome to admins only'
    else:
        return 'Restricted access - admins only'

```
### Using SamlSP with BotAuth() Authentication & Authorization middleware
To simplify authentication and authorization of views, a companion module, [ BottleAuth middleware ](https://github.com/Glocktober/BottleAuth) relegating these tasks to middleware, and providing both route-based and path prefix based authorization mechanisms.
> Example using SamlSP with BotAuth:
```python
@app.route('/admins', authz={'groups':'sysadmins'})
def admins_only():
    return 'Welcome to admins only...'
```
for simpler authentication and authorization mechanisms.
### Available Session Attributes  
The attributes you have available and saved in your session from the SAML authorizaiton process depend on:
* The SAML ***assertions*** provided by the IdP. This is set by the IdP configuration. We can't save something we never received. This is all on the IdP end.
* The attributes listed in the ***`assertions`*** key in the **saml_config** options. This `list` is set by you, and filters the assertions you care about from the IdP's `SAMLResponse`. 
* If an **assertion** *name* matches an attribute *name* in the config, the value is added to the users `session['attributes']` dict with the *name* as the key.
* If no ***`assertions`*** list is provided in **saml_config**, the only attribute added to your session will be `username`, set from the `name_id` in the `SAMLResponse`. 
* Multi-value assertions (such as you might find in a `group` or `member_of` parameter) are stored as a Python `list` of values.

#### SAML Attribute Session Layout
This is the structure used by SamlSP to save attributes is presented here: avoid namespace collisions with view or middleware session data.
> SamlSP session data layout:
```
{'username': <username>}
{'attributes':{
                'attr1': value1,    # attribute/value pairs 
                'attr2': value2.    # created from SAML
                ...                 # assertions
                'attrN': valueN,
                '_SAML' : {         # SamlSP's metadata
                    'issuer' : <IdP entity id>
                    'requestid' : <saml 'on behalf of'> 
                    'audience' : <saml response audience>
                    'expires' : <unix time until reauth required>
                }
}
{'request_id': <request-id>}  # temporary during login
... 
```

## SAML Configuation Parameters

Configuration information required to set-up the SAML authentication, and parameters to tune BottleSaml is formed into a `dict` passed as the **`saml_config=`** argument to **`SamlSP()`**.  Typically this is imported from a `config.py` as in the example above.

Collect the necessary information from the IdP (much available from it's metadata) and to select the behavior appropriate for your application.  

This isn't difficult, but it can confusing if you are unfamiliar with SAML.
>SamlSP config file paramters: 

| **parameter**  |**type** | **default** | **description**
|------------------|-----|--------|----------------------|
|**saml_endpoint** |URL|*required*|IdP's SAML auth endpoint|
|**spid** |URI|*required*|Our apps's entity id|
|**issuer** |URI|*required*|IdP's `issuer` identity|
|**force_reauth**|Bool|False| True will request IdP full login|
|**acs_url** |URL|*required*|URL of our Assertion Control Service (ACS) endpoint|
|**user_attr**|string|name_id|SAML assertion providing `username` attribute|
|**assertions**|[string]|[]|A list of SAMLRespons assertions to collect|
|**idp_ok**|Bool|True|Permit IdP initiated logon|
|**auth_duration**|int|3600|Seconds between SAML credentials renewal |
|**certificate**|string|*required*|The IdP's public certificate for signing verification|

* In most cases the "URI's" will be "URL's".
* The SPID must be configured with the IdP. This is how the IdP knows who we are.
* The `acs_url` needs to match what was configured for the app on the IdP.
* If `assertions` is missing or an empty list, only the `username` will be placed in the session.

### Configuring BottleSessions
* It is important to configure BottleSessions to meet the needs of your app.  Considertions include the type of caching your app needs, cookie and cache TTL and cookie name name. Consult the [BottleSessions Documentation](https://github.com/Glocktober/BottleSessions) for more information.

