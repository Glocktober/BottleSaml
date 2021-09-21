 
### SAML Service Provider (SamlSP) Class
### saml = SamlSP()
#### Instantiate class
```python
saml = SamlSP(app, sess, saml_config, log=None, **kwargs)

```
- Creates an instance of the SAML service provider.
- Only one instance per-app is supported.
- The **BottleSession** plugin must be installed (or any session module that provides a `dict` as `request.session`)

**`app`**
  * a **Bottle()** class instance. 

**`sess`**
  * a **BottleSession()** class instance. This allows **SamlSP()** to manage it's session.

**`saml_config`**
  * A Python `dict` containing the SAML configuration data.  [This is detailed in the overview document.](READMESP.md)  This is a required argument.

**`log`**
  * This can be a Python `logging` log object. The default is **`None`**. If it is `None`, the module logs to `sys.stderr`.

**`kwargs`**
 * Any keyword argments are currently ignored.
   

### saml.is_authenticated
This is true if the session is authenticated. It will not initiate the IdP login process.

### saml.initiate_login()
```python
return saml.initiate_login(force_reauth=False, userhint=None, **kwargs):
```
Creates a **SAMLRequest** for a GET login to the IdP.  This returns a redirect to the IdP, initiating the IdP login.

**`force_reauth`**:
  * Requests the IdP to require a full username/password authentication (*vs.* a Single Sign On authentication.)  The default is `False` - don't require the full logon.

**`userhint`**:
  * Provides a user hint (string of the UPN) to the IdP. Not all IdP's support this, but on the Microsoft Identity Platform it places the username in the login page. Default is `None` - no hint is provided.

**`kwargs`**:
 * Key-word arguments are combined and sent to the IdP as **`RelayState`**.  With the exception of **`next=URL`** they are ignored.
 * The **`next`** argument is used in the Assertion Control Service to determine where the browser is redirected after the login.

### saml.add_login_hook()
```python
saml.add_login_hook(f)
```
Adds a login hook, which is run after a successfule **SAMLResponse** has been authenticated. [The purpose is to process SAML assertion data.](LOGINHOOKS.md)  This can be used as a decorator for such a function.

**`f`**
* A login hook `f` is a function. This is added to a list of login hooks run after a successful authentication. 
* Login hooks inspect/process/filter/transform the username and attributes provided by the *`assertions`* before they are stored as session attributes.
* Login hooks are of the form:
```python
def login_hook(username, attributes):
        # does processing
        return username, attributes
```
* Login hooks can prevent an authentication from completing by raising an exception
* Login hooks [are discussed here.](LOGINHOOKS.md)

