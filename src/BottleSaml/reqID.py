import os
from secrets import token_urlsafe

from cryptography.fernet import Fernet

DEBUG = os.getenv('DEBUG',False)


class ReqID:
    """ 
    Create and validate request ID's
    """

    def __init__(self, idpok=False, id='ReqID', ttl=30):

        if not idpok:
            # Not accepting IDP initiated Logon
            self.key = Fernet.generate_key()
            self.f = Fernet(self.key)
            self.id = id.encode('utf-8')
            self.ttl = ttl

            self.new_requestID = self.__noidp_new_requestID
            self.validate_requestID = self.__noidp_validate_requestID
        else:
            # Accepting IDP initiated Logon
            self.new_requestID = self.__idpok_new_requestID
            self.validate_requestID = self.__idpok_validate_requestID


    def __idpok_new_requestID(self):
        """ Create a new request ID """

        return 'ID' + token_urlsafe(8)
    

    def __idpok_validate_requestID(self, reqid):
        """ IDP OK so anything goes """

        return True

#
# For NoIDP accepted, Request ID is Frenet encrypted
#
    def __noidp_new_requestID(self):
        """ Create a new request ID """

        reqid = self.f.encrypt(self.id).decode()
        # Azure AD particulars: can't start with a digit
        # and barfs on '=' padding
        return 'Id' + reqid[:reqid.find('=')]
    

    def __noidp_validate_requestID(self,reqid):
        """ Validate request ID """
        try:
            if not reqid.startswith('Id'):
                raise Exception('Invalid Request ID')
            
            # remove 'Id' prefix
            reqid = reqid[2:]
            # replace base64 padding
            reqid = reqid + (4 - len(reqid) % 4 ) * '='
            # convert to bytes
            reqid = reqid.encode('utf-8')

            if mess := self.f.decrypt(reqid, self.ttl):
                if mess == self.id:
                    return True
        
        except Exception as e:
            if DEBUG:
                raise e
            pass
        
        return False


