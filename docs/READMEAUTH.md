 ## SamlAuth - Authentication and Authorization Middleware

The **BottleSaml** module includes the **SamlAuth()** plugin class for the [Bottle web framework.](https://github.com/bottlepy/bottle):
* **SamlAuth** enhances [SamlSP - SAML Service Provider module](READMESP.md) by providing simplified authentication and authorization schemes for Bottle web apps.
* **SamlAuth** establishes *route-based* and *prefix-based* **authorization** requirements, using attribute/value pairs. These requirements evaluate against the SAML ***assertions***  obtained from the **SamlSP()** for the user.
* **SamlAuth** utilizes [BottleSessions](https://github.com/Glocktober/BottleSessions) to provide persistent session access to SAML as well as other app data.
* **SamlAuth** Complies with [Bottle Plugin API v2](https://bottlepy.org/docs/dev/plugindev.html).
* **BottleSaml** is [the name of the module](../README.md), **SamlAuth** is the bottle plug-in class implementing Authentication/Authorization features for Bottle web apps requiring SAML integration via **SamlSP**.
* My testing has been with Azure AD and SimpleSamlPHP IdP's.

## Quickstart
> pypi installation:
```bash
# python3 -m pip install BottleSaml
```
This will load required modules, including SamlSP, and SamlAuth, bottle, BottleSession and minisaml, and their dependencies.
### Initializing SamlAuth Middlware
> Adding SamlAuth to a bottle app:
```python
from bottle import Bottle
from BottleSessions import BottleSessions   
from BottleSaml import SamlSP, SamlAuth  

# import SAML configuration (see below)
from config import saml_config              

# Create a Bottle application context
app = Bottle()                              

# Install session middleware (Before SAML)
BottleSessions(app)                         

# Create the SAML Service Provider (SP)
# See READMESP.md for details
saml = SamlSP(app, saml_config=saml_config)

# Configure and install SamlAuth middleware
auth = SamlAuth(saml)
app.install(auth)
```
The default **`auth=SamlAuth(saml)`** configuration provides **Opt-Out** authentication on all routes but establishes no authorization requirements. 
## Requiring Authentication
**SamlAuth** provided two modes for requiring Authentication: **Bottle** apps can  **Opt-Out**, or **Opt-In** to authentication.
### Opt-Out Authentication
*By default **SamlAuth** adds an authentication requirement on ***all*** views in the app.* 

An unauthenticated user accessing any view will invoke the SAML authentication process, requiring login to access the page.

This isn't always the desired behavior. There are usually some views in your application that you would like accessible even to unauthenticated users. 

You can **Opt-Out** of authentication on these views using the **`skip=`** argument to the **`@app.route(...)`**, listing the **SamlAuth** plugin instance (**`skip=auth`**) or by plugin name (**`skip='SamlAuth'`**) 
> **Opting-Out** of authentication on a view:
```python
saml = SamlSP(app, saml_config)
auth = SamlAuth(saml, authn_all_routes=True)
app.install(auth)
    ---
@app.route('/help', skip=[auth]) 
def help_view():
    return `This is an unprotected route`
```
The **SamlAuth()** parameter **`authn_all_routes`** set to `True` (the default) establishes the requirement to **Opt-Out**.
### Opt-In Authentication
**SamlAuth** also has an **`Opt-In`** mode. 

Some web apps require authentication on only a few views. For these it is easier to ***`Opt-in`*** those page by adding **`authn=True`** (or **`authz=`**) in the **`app.route(...)`** config options.

> **Opt-In** authentication:
```python
saml = SamlSP(saml_config)
auth = SamlAuth(saml, authn_all_routes=False)
app.install(auth)
    ---
# SET Opt-In mode
auth.authn_all_routes = False
    ---
@app.route('/login', authn=True)
def login_view():
    return 'You are now logged in.'
```
**Opt-In** behavior is established by **SamlAuth** instantiated with **`authn_all_routes`** set to `False`.

To summerize, ***Opt-In***/***Opt-Out*** behavior is set for the whole app by the **SamlAuth()** parameter **`authn_all_routes`**, 
and ***Opt-Out*** is the default behavior.

## Requiring Authorization
**SamlAuth** provides two methods of applying authorization requirements to views in a **Bottle** web app. These are **route-based authorization**, and **path-based authorization**.
### Route-based Authorization
Route authorization restrictions are added to a views with the **`authz={...}`** config option in **`app.route(...)`** decorator.

Route based authorization can be used in either Opt-in or Opt-out mode, and any **`authz`** statement provides implicit **`authn=True`** authentication.

Authorization restrictions of **`authz={attr:value}`** are defined by attribute/value pairs in Python `dict` form. 
> route-based authorization:
```python
@app.route('/alices_page', authz={'username': 'alice})
def alice_only():
    return 'hi Alice'
```
The values and attributes are compared to  attributes acquired from the SAML authentication of the user and stored in the users session.

The **`authz`** requirements are met if the user has the same attribute, and the value for that attribute matches the **authz** statement.  If so, the request reaches the protected view.

Failure to match these required value or not posessing the attribute results in a ***403 Unauthorized error***. 

##### Multiple value (list) matching:
If multiple values for an attribute are specified using a list (*e.g.* **`authz={'username':['bob','alice]}`**), the user **needs to match only one of the list** and the restriction met.  
##### Multiple atttribute matching:
If multiple attributes are specified, (*e.g.* **`authz={'group': ['sysadmin','netadmin'], 'mfa': True}`**) the user must match at least one value **for each** attribute.  The user must have all the attributes, and all the attributes must be satisfied for the restriction to be met.

### Route-based Authorization Examples
Consider these examples:
> Multiple **`authz`** examples:
```python
# Only username bob can access view
@app.route('/bob', authz={'username':'bob'})
def bob_only_view()
    return 'Hi Bob'

# Anyone in the sysadmin group
@app.route('/sysadmins', authz={'groups':'sysadmins'}
)
def sysadmin_view():
    return 'Hi sysadmin!'

# Anyone in sysadmin, netadmin, or cloudadmins
@app.route('/alladmins', authz={'groups': 'sysadmins', 'netadmins', 'cloudadmins']})
def alladmin_view():
    return 'Hi various admins!'

# User alice or bob, but only with MFA authentication
@app.route('/multiple', authz={
    'username' : ['alice', 'bob'],
    'mfa' : True})
def mfaonly():
    return 'You\'ve used your MFA!'
```
***Tip:*** To keep authorizations managable, construct a `dict` for each use-case and apply it `**kwargs` style in `@app.route()`. Reuse them on routes with the same authorization requirement:
> Examlpe of use case authorization:
```python
admin_restricted = {'groups': ['sysadmins', 'netadmins', 'cloudadmins']}
budgets = {'groups': ['project_team','accounting']}
skip_auth = {'skip':[saml]}

@app.rotue('/greeting', **skip_auth)
def greet():
    return 'Hello'

@app.route('/admin', **admin_restricted)
def admin_only():
    return 'Hello admin'

@app.route('/budget/2022', **budgets)
def budget_2022():
    return 'Hello EXCELers'

@app.route('/route53', **admin_restricted)
def r53():
    return 'Hello again admins'
```
This is not required, but makes it a little bit easier to write and read.
### Prefix-based Authorization
Often sites have structured layouts based on paths and formed in a logical tree, say, based on project, department, or customer.  Prefix-based authorization provides an easy way to provide authorization restrictions.
> Example logical tree of Departments:
```
/ --+- helpdesk
    |
    +- infrastructure 
    |       |
    |       +-- Networking
    |       |
    |       +-- Servers
    |       |
    |       +-- Storage
    +- desktop
            |
            +-- PC_support
            |
            +-- MAC_support

```
There are implicit authorization rules that can be created based on the prefix path of views routes:
> Example prefix-based authorization
```python
# config.py segment
it_prefix_auth={
    # The /helpdesk path can be access by department
    '/helpdesk' : {
        'dept':['helpdesk','PC support']
    },
    # /Infrastructure accessed by 3 groups 
    '/infrastructure': {
        'groups':['sysadmin','netadmin', 'storageadmin']
    },
    # The further down the tree, the fewer groups
    '/infrastructure/Networking': {
        'groups':'networking'
    },
    '/infrastructure/Servers': {
        'groups':'sysadmin'
    },
    # Other attributes than groups can be used
    '/infrastructure/Storage': {
        'role': ['emcadmin','pureadmin']
    },
    '/desktop/PC_support':{
        'dept': ['PC support']
    },
    '/desktop/MAC_support': {
        'username': ['bob', 'alice']
    }
}
```
These requirements are attached to views based on their route path.
> Applying prefix-based authorization:
```python
from config import saml_config, it_prefix_auth

saml = SamlSP(saml_config=saml_config)
auth = SamlAuth(saml, authz_by_prefix=it_prefix_auth)
    ...
@app.route('/desktop/MAC_support')
def hello_mac():
    return 'Hello Alice or Bob'
```
Again, best practice may be to have this in a config.py file.
#### Excluding views from path-based authorization:
Routes can be excluded from path-based authorization requirements using the **`skip=[auth]`** method. 
#### Using route-based with path-based authorization:
Additional requirements can be placed individual views using the **`authz={...}`** route config.  Both the path-based requirements and the authz requirements must be met for access to the view to be granted.
#### Opt-out is required for path-based authorization:
Path-based routes only function in **Opt-Out** mode (*i.e.* **auth_all_routes=True**) This better matches intent of path-based restrictions.

### Available Attributes for Authorization 
The attributes you have available to **SamlAuth** are saved in your session from the SAML authorizaiton process. These depend on the configuration of **SamlSP()**: [Refer to the documentation on SamlSP for details.](READMESP.md)
