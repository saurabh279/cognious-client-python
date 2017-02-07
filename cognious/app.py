"""
Cognious API Python Client
"""

import os
import time
import json
import copy
import base64
import logging
import requests
import platform
from io import BytesIO
from pprint import pformat
from configparser import ConfigParser
from posixpath import join as urljoin
try:
    from urlparse import urlparse
except:
    from urllib.parse import urlparse

from utils import get_user_data_dir

logger = logging.getLogger('cognious')
logger.handlers = []
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

logging.getLogger("requests").setLevel(logging.WARNING)

CLIENT_VERSION = '1.0'
OS_VER = os.sys.platform
PYTHON_VERSION = '.'.join(map(str, [os.sys.version_info.major, os.sys.version_info.minor, \
                                    os.sys.version_info.micro]))
COGNIOUS_BASEURL = 'cognious.com'
COGNIOUS_API_BASEURL = 'api.cognious.com'

class CogniousApp(object):

  """ Cognious Application
	This class acts as a constructor for your application
  """

  def __init__(self, app_id=None, app_secret=None, base_url='', quiet=True):

    self.api = ApiClient(app_id=app_id, app_secret=app_secret, base_url=COGNIOUS_BASEURL, quiet=quiet)
    self.auth = Auth(self.api)

  def getModel(self, model, data, stringresponse=False):
    '''
    parsed = urlparse(base_url)
    scheme = 'https' if parsed.scheme == '' else parsed.scheme
    base_url = parsed.path if not parsed.netloc else parsed.netloc
    self.base_url = base_url
    self.scheme = scheme
    '''
    apiurl = urljoin(self.api.scheme + '://', self.api.base_url, 'v1.0', model)
    headers = self.api.headers
    res = requests.post(apiurl, headers=headers, data=data)
    if res.status_code == 200:
      self.answer = res.json()['answer']
      self.response = res.json()
    else:
      raise TokenError("Could not get the model: %s", str(res))
    return res.json()

class Auth(object):

  """ Cognious Authentication
      This class is initialized as an attirbute of the cognious application object
      with app.auth
  """

  def __init__(self, api):
    self.api = api

  def get_token(self):
    ''' get token string
    Returns:
      The token as a string
    '''

    res = self.api.get_token()
    token = res['access_token']
    return token

"""
class Image(Input):

  def __init__(self, url=None, file_obj=None, base64=None, filename=None):
    '''
      url: the url to a publically accessible image.
      file_obj: a file-like object in which read() will give you the bytes.
    '''

    self.url = url
    self.filename = filename
    self.file_obj = file_obj
    self.base64 = base64

    # override the filename with the fileobj as fileobj
    if self.filename is not None:
      if not os.path.exists(self.filename):
        raise UserError("Invalid file path %s. Please check!")
      elif not os.path.isfile(self.filename):
        raise UserError("Not a regular file %s. Please check!")

      self.file_obj = open(self.filename, 'rb')
      self.filename = None

    if self.file_obj is not None:
      if not hasattr(self.file_obj, 'getvalue') and not hasattr(self.file_obj, 'read'):
        raise UserError("Not sure how to read your file_obj")

      if hasattr(self.file_obj, 'mode') and self.file_obj.mode != 'rb':
        raise UserError(("If you're using open(), then you need to read bytes using the 'rb' mode. "
                         "For example: open(filename, 'rb')"))
"""
class ApiClient(object):
  """ Handles auth and making requests for you.
  The constructor for API access. You must sign up at www.cognious.com and create 
  an application to obtain app_id and app_secret
  """

  def __init__(self, app_id=None, app_secret=None, base_url=None, quiet=True):
    self.app_id = app_id
    self.app_secret = app_secret

    if quiet:
      logger.setLevel(logging.INFO)
    else:
      logger.setLevel(logging.DEBUG)

    parsed = urlparse(base_url)
    scheme = 'https' if parsed.scheme == '' else parsed.scheme
    base_url = parsed.path if not parsed.netloc else parsed.netloc
    self.base_url = base_url
    self.scheme = scheme
    self.basev2 = urljoin(scheme + '://', base_url)
    logger.debug("Base url: %s", self.basev2)
    self.token = None
    self.headers = None

    # Make sure when you create a client, it's ready for requests.
    self.get_token()
    # save the token to user data directory to reuse the same token

  def get_token(self):
    ''' Get an access token using your app_id and app_secret.
    You shouldn't need to call this method yourself. If there is no access token yet, this method
    will be called when a request is made. If a token expires, this method will also automatically
    be called to renew the token.
    '''
    data_dir = get_user_data_dir(self.app_id)
    data_file = os.path.join(data_dir, 'token.txt')
    if os.path.isfile(data_file):
        f= open(data_file,"r")
        if f.mode == 'r':
            test_token=f.read()
            test_header = {'Authorization': "Bearer %s" % test_token}
            test_result = requests.get('https://cognious.com/protected', headers=test_header)
            if test_result.status_code == 200:
                self.token = test_token
                self.headers = {'Authorization': "Bearer %s" % self.token}
                return
        f.close()

    data = {'grant_type': 'client_credentials'}
    auth = (self.app_id, self.app_secret)
    logger.debug("get_token: %s data: %s", self.basev2 + '/accounts/token', data)

    authurl = urljoin(self.scheme + '://', self.base_url, 'accounts', 'token')
    res = requests.post(authurl, auth=auth, data=data)
    if res.status_code == 200:
        logger.debug("Got token: %s", res.json())
        self.token = res.json()['access_token']
        self.headers = {'Authorization': "Bearer %s" % self.token}

        f= open(data_file,"w+")
        f.write(self.token)
        f.close
    else:
      raise TokenError("Could not get a new token: %s", res)
    return res.json()

  def set_token(self, token):
    ''' manually set the token to this client
    You shouldn't need to call this unless you know what you are doing, because the client handles
    the token generation and refersh for you. This is only intended for debugging purpose when you
    want to verify the token got from else where.
    '''
    self.token = token

  def delete_token(self):
    ''' manually reset the token to empty
    You shouldn't need to call this unless you know what you are doing, because the client handles
    the token generation and refersh for you. This is only intended for debugging purpose when you
    want to reset the token.
    '''
    self.token = None

class ApplicationError(Exception):
  """ Application Error """
  pass

class UserError(Exception):
  """ User Error """
  pass

class TokenError(Exception):
  """ Token Error """
  pass

