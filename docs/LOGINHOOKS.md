## SamlSP Login Hooks
* A login hook is a function that is run after a successful authentication is received from the IdP, but before the username and attributes are added to the session data. 
* Login hooks can inspect/process/filter/transform the username and attributes provided by the SAML *`assertions`*. 
> Login hooks take in and return a username, attribute tuple:
```python
def my_login_hook(username, attributes):
        # does processing
        return username, attributes
```
* Login hooks can prevent an authentication from completing by raising an exception
* Add a login hook using the **`add_login_hook()`** method:
> Adding a login hook:
```python
saml.add_login_hook(my_login_hook)
```
* Multiple login hooks can be used, and are processed in the order they are added.

### Example Uses
* **Map Namespaces** An IdP can provide names as full URN's, which are unwieldy to use in apps.  A login hook can transform the names to something easier to use.
For example, this changes the URN key to a more managable `object_id` than the full `http://schema..../objectidentifier`. 
> Example name space transformation:
```python
msft_objid = "http://schemas.microsoft.com/identity/claims/objectidentifier"
def fix_objid(u, attr):
    if msft_objid in attr:
        attr['object_id'] = attr[msft_objid]
        del attr[msft_objid]
    return u , attr

saml.add_login_hook(fix_objid)
```

* **Authentication Limitations** An app may want to impose it's own restrictions for authentication using the data provided by the IdP. A login hook can enforce it. For example, group membership can be checked before even authorizing the login.
> Example raises an Exception to thwart login:
```python
# protected site
def admin_check(username, attributes):
    if 'sysadmin' not in attributes['groups']:
        raise Exception('Only sysadmins can use this site.')
    return username, attributes

saml.add_login_hook(admin_check)
``` 
* **Flaten assertion hierarchy** In this example, the list of microsoft `authmethodsreverence` structure contains indicators of `password` and `multifactor` methods used for authentications. The contained items can't be used in `authz` logic. A login hook can flatened the namespace (while renaming them) so they can be used in `authz` .
> Example login hook that flatens namespace:
```python
def msft_mfa_hook(user, attrs):
    """Determine if Azure used MFA"""

    msft_methods = 'http://schemas.microsoft.com/claims/authnmethodsreferences'
    msft_mfa = 'http://schemas.microsoft.com/claims/multipleauthn'
    msft_pwd = 'http://schemas.microsoft.com/ws/2008/06/identity/authenticationmethod/password'

    attrs['msft_mfa'] = False
    attrs['msft_pwd'] = False

    if msft_methods in attrs:
        # flatten these values
        if msft_mfa in attrs[msft_methods]:
            attrs['msft_mfa'] = True

        if msft_pwd in attrs[msft_methods]:
            attrs['msft_pwd'] = True

        # don't need this anymore
        del attrs[msft_methods]

    return user, attrs

saml.add_login_hook(msft_mfa_hook)
```
>Now a route could require mfa:
```
@app.route('/mfaonly', authz={'msft_mfa' : True})
def mfa_view():
    ....
```

