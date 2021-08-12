# BottleSaml

**BottleSaml** is a Python module for the [Bottle web framework.](https://github.com/bottlepy/bottle) in two parts:

* **SamlSP()** - [an implementation of a SAML *Service Provider* implementation for **Bottle** web apps](docs/READMESP.md). This permits bottle apps to authenticated with a SAML Identity Provider (IdP).  This module can be used on it's own, or combined with **SamlAuth**. 

* **SamlAuth()** - [is a middleware plugin offering simplified authentication and authorization](docs/READMEAUTH.md) mechanisms utilizing **SamlSP** in **Bottle** framework apps. 

Both modules in **BottleSaml** rely on persistent *session* data in the form of a Python `dict` accessed off the Bottle **`request`** object (*i.e.* `request.session`). By default **BottleSaml** will use the [BottleSessions module](https://github.com/Glocktober/BottleSessions) to provide this - but any session middleware that can add a `session` dict to the `request` object can be used.

In both components the goal is to provide easy to use tools for using SAML identity management platforms in Bottle apps.