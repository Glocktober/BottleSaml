# BottleSaml

**BottleSaml** is a Python module for the [Bottle web framework.](https://github.com/bottlepy/bottle) providing **SamlSP()** - [an implementation of a SAML *Service Provider* for **Bottle** web apps](docs/READMESP.md). This permits bottle apps to authenticated with a SAML Identity Provider (IdP).  

This module can be used on it's own, or combined with [BottleAuth](https://github.com/Glocktober/BottleAuth). BottleAuth provides path and route authentication and authorization tools. 

Both modules in **BottleSaml** rely on persistent *session* data in the form of a Python `dict` accessed off the Bottle **`request`** object (*i.e.* `request.session`). By default **BottleSaml** will use the [BottleSessions module](https://github.com/Glocktober/BottleSessions) to provide this - but any session middleware that can add a `session` dict to the `request` object can be used.

The goal of this module is to provide easy to use tools for using SAML identity management platforms in Bottle apps.
