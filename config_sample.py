sample_saml_config = {
      "saml_endpoint": 'required',  # URL of Idp's authentication endpoint
      "issuer": 'required',         # The Idp's 'issuer' URN imprimatur
      "spid": 'required',           # Your applications URN identifier registered with the Idp
      "acs_url" : "required",       # Your Assertion control service URL registered with the Idp
      "user_attr": "name_id",       # The claim used to set the username in the session 
      "auth_duration": 3600,        # number of seconds authentication considered valid
      "assertions": [],             # claims to add to session attributes ["uid", "givenname", ...]
      "force_reauth" : False,       # True forces a full, non-SSO login
      "certificate" : 'required'     # The Idp's X509 signing certificate, PEM
}