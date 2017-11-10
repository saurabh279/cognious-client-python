"""
Cognious API Python Client
"""
import os
import time
import re
import json
import copy
import base64 as lib_base64
import logging
import requests
import platform
from io import BytesIO
from pprint import pformat
from configparser import ConfigParser
from posixpath import join as urljoin
from PIL import Image as PILImage
try:
    from urlparse import urlparse
except:
    from urllib.parse import urlparse

from .utils import get_user_data_dir, is_url_image

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
    self.models = Models(self.api)

  def getModel(self, model, data, stringresponse=False):
    '''
    **DEPRICATED**
    scheme = 'https' if parsed.scheme == '' else parsed.scheme
    base_url = parsed.path if not parsed.netloc else parsed.netloc
    self.base_url = base_url
    self.scheme = scheme
    '''
    apiurl = urljoin(self.api.scheme + '://', COGNIOUS_API_BASEURL, 'v1.0', model)
    headers = self.api.headers
    #print(apiurl, headers, data)
    res = requests.post(apiurl, headers=headers, data=data)
    if res.status_code == 200:
      self.answer = res.json()['result']
      self.response = res.json()
    elif res.status_code == 403:
      raise TokenError("Invalid Token: %s", str(res))
    elif res.status_code == 404:
      raise ModelError("Invalid Model: %s", str(res))
    elif res.status_code == 500:
      raise ModelError("Server Error", str(res))
    else:
      raise ModelError("Invalid request: %s", str(res))
    return res.json()


class Models(object):

  def __init__(self, api):
    self.api = api

  def get(self, model_id=None):
    if model_id is None:
      raise ModelError('No model specified')

    model = None
    if model_id is not None:
      if model_id == 'ImageRecognition':
        model = ImageRecognition(api=self.api, model_id=model_id)
      if model_id == 'SentimentAnalysis':
        model = SentimentAnalysis(api=self.api, model_id=model_id)

    if model is None:
      raise UserError("Invalid model: %s" % model_id)

    return model


class ImageRecognition(object):

  def __init__(self, api, model_id=None):
    self.api = api
    self.model_id = model_id
    self.response = None
    self.result = None

  def predict_by_url(self, url):
    self.clear_previous()
    if is_url_image(url):
      img = Image(url=url)
      self.make_call({'image': img.get_base64()})
    else:
      raise UserError("Given url doesn't seem to be an image")
 
  def predict_by_imagefile(self, filename):
    self.clear_previous()
    img = Image(filename=filename)
    self.make_call({'image': img.get_base64(), 'top': 5})

  def make_call(self, data):
    result = self.api.make_call('imagerecog', data)
    self.response = result.json()
    self.result = self.response['result']['prediction']

  def clear_previous(self):
    self.response = None
    self.result = None

class SentimentAnalysis(object):

  def __init__(self, api, model_id=None):
    self.api = api
    self.model_id = model_id
    self.response = None
    self.result = None

  def analyze_sentence(self, sentence):
    self.clear_previous()
    self.make_call({'text': sentence})

  def analyze_each_sentence(self, paragraph, splitby='. ', splitby_regex=None):
    #self.clear_previous()
    result = []
    if splitby_regex is None:
      for text in paragraph.split(splitby):
        self.clear_previous()
        self.make_call({'text': text})
        result.append([text, self.result])
    else:
      for text in re.compile(splitby_regex).split(paragraph):
        self.clear_previous()
        self.make_call({'text': text})
        result.append([text, self.result])
    self.result = result

  def analyze_text(self, text):
    result = []
    if type(text) is list:
      self.clear_previous()
      self.make_call({'text': text})
    elif type(text) is str:
      self.analyze_sentence(text)
    else:
      raise UserError('Input should be of type "str" or "list"')

  def make_call(self, data):
    response = self.api.make_call('sentimentanalysis', data)
    self.response = response.json()
    self.result = self.response['result']

  def clear_previous(self):
    self.response = None
    self.result = None
    

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

class Image(object):

  def __init__(self, url=None, file_obj=None, base64=None, filename=None):
    '''
      url: the url to a publically accessible image.
      file_obj: a file-like object in which read() will give you the bytes.
      filename: the full image file path.
    '''

    self.url = url
    self.filename = filename
    self.file_obj = file_obj
    self.base64 = base64
    self.file_data = None


    # override the filename with the fileobj as file_obj
    if self.filename is not None:
      if not os.path.exists(self.filename):
        raise UserError("Invalid file path \"%s\". Please check!" % self.filename)
      elif not os.path.isfile(self.filename):
        raise UserError("Not a regular file \"%s\". Please check!" % self.filename)

      # check if file is an image
      try:
        PILImage.open(self.filename)
      except IOError:
        raise UserError("Not a regular Image file. Please check!")

      self.file_obj = open(self.filename, 'rb')
      self.filename = None

    if self.file_obj is not None:
      if not hasattr(self.file_obj, 'getvalue') and not hasattr(self.file_obj, 'read'):
        raise UserError("Not sure how to read your file_obj")

      if hasattr(self.file_obj, 'mode') and self.file_obj.mode != 'rb':
        raise UserError(("If you're using open(), then please read bytes using the 'rb' mode. "
                         "For example: open(filename, 'rb')"))

      self.file_data = self.file_obj.read()

    if self.url is not None:
      if is_url_image(self.url):
        self.file_data = requests.get(url).content
      else:
        raise UserError("Not a regular image file")

    if self.file_data is not None:
      self.base64 = lib_base64.b64encode(self.file_data)

  def get_base64(self):
    ''' Returns the base64 encoded string of the image
    '''
    return self.base64

        
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

  def make_call(self, model, data, stringresponse=False):
    '''
    scheme = 'https' if parsed.scheme == '' else parsed.scheme
    base_url = parsed.path if not parsed.netloc else parsed.netloc
    self.base_url = base_url
    self.scheme = scheme
    '''
    apiurl = urljoin(self.scheme + '://', COGNIOUS_API_BASEURL, 'v1.0', model)
    headers = self.headers
    res = requests.post(apiurl, headers=headers, data=data)
    if res.status_code == 200:
      self.answer = res.json()['result']
      self.response = res.json()
    elif res.status_code == 403:
      raise TokenError("Invalid Token: %s" % res.json()['error']['message'])
    elif res.status_code == 404:
      raise ModelError("Invalid Model: %s" % res.json()['error']['message'])
    elif res.status_code == 500:
      try:
        error_message = res.json()['error']['message']
      except:
        raise ServerError("Server Error: %s - Something unexpected happened" % res.status_code)
      raise ServerError("Server Error: %s" % error_message)
    else:
      error_message = res.json()['error']['message']
      if error_message:
        raise ApplicationError("Invalid request: %s" % error_message)
      else:
        raise ApplicationError("Unhandled error occured - Code: %s" % res.status_code)
    return res


class ApplicationError(Exception):
  """ Application Error """
  pass

class UserError(Exception):
  """ User Error """
  pass

class ModelError(Exception):
  """ ModelError """
  pass

class TokenError(Exception):
  """ Token Error """
  pass

class ServerError(Exception):
  """  ServerError """
  pass
