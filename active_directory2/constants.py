# -*- coding: iso-8859-1 -*-
import fnmatch
import re

from win32com import adsi
from win32com.adsi import adsicon

from . import utils

class _Unset (object):
  def __repr__ (self):
    return "<Unset>"
Unset = _Unset ()

def from_pattern (pattern, name):
  ur"""Helper function to find the common pattern among a group
  of like-named constants. eg if the pattern is FILE_ACCESS_*
  then the part of the name after FILE_ACCESS_ will be returned.
  """
  if pattern is None:
    return name
  else:
    return re.search (pattern.replace ("*", r"(\w+)"), name).group (1)

#
# For ease of presentation, ms-style constant lists are
# held as Enum objects, allowing access by number or
# by name, and by name-as-attribute. This means you can do, eg:
#
# print GROUP_TYPES[2]
# print GROUP_TYPES['GLOBAL']
# print GROUP_TYPES.GLOBAL
#
# The first is useful when displaying the contents
# of an AD object; the other two when you want a more
# readable piece of code, without magic numbers.
#
class Enum (object):

  #
  # By aliasing the UNSET object here, we can give
  # formal parameter definitions of, eg, ADS_SYSTEMFLAG.Unset
  # indicating clearly what flags are expected while allowing
  # it to be tested against Constants.Unset
  #
  Unset = Unset

  def __init__ (self, **kwargs):
    self._name_map = {}
    self._number_map = {}
    for k, v in kwargs.items ():
      self._name_map[k] = utils.i32 (v)
      self._number_map[utils.i32 (v)] = k

  def __getitem__ (self, item):
    try:
      return self._name_map[item]
    except KeyError:
      return self._number_map[utils.i32 (item)]

  def __getattr__ (self, attr):
    try:
      return self._name_map[attr]
    except KeyError:
      raise AttributeError

  def __repr__ (self):
    return repr (self._name_map)

  def __str__ (self):
    return str (self._name_map)

  @classmethod
  def from_pattern (cls, pattern=u"*", excluded=[], namespace=adsicon):
    u"""Factory method to return a class instance from a wildcard name pattern. This is
    the most common method of constructing a list of constants by passing in, eg,
    FILE_ATTRIBUTE_* and the win32file module as the namespace.
    """
    d = dict (
      (from_pattern (pattern, key), getattr (namespace, key)) for \
        key in dir (namespace) if \
        fnmatch.fnmatch (key, pattern) and \
        key not in excluded
    )
    return cls (**d)

  def item_names (self):
    return self._name_map.items ()

  def item_numbers (self):
    return self._number_map.items ()

ADS_SEARCHPREF = Enum.from_pattern ("ADS_SEARCHPREF_*")

ADS_SYSTEMFLAG = Enum (
  DISALLOW_DELETE             = 0x80000000,
  CONFIG_ALLOW_RENAME         = 0x40000000,
  CONFIG_ALLOW_MOVE           = 0x20000000,
  CONFIG_ALLOW_LIMITED_MOVE   = 0x10000000,
  DOMAIN_DISALLOW_RENAME      = 0x08000000,
  DOMAIN_DISALLOW_MOVE        = 0x04000000,
  CR_NTDS_NC                  = 0x00000001,
  CR_NTDS_DOMAIN              = 0x00000002,
  ATTR_NOT_REPLICATED         = 0x00000001,
  ATTR_IS_CONSTRUCTED         = 0x00000004
)

GROUP_TYPES = Enum (
  GLOBAL = 0x00000002,
  DOMAIN_LOCAL = 0x00000004,
  LOCAL = 0x00000004,
  UNIVERSAL = 0x00000008,
  SECURITY_ENABLED = 0x80000000
)

AUTHENTICATION_TYPES = Enum (
  SECURE_AUTHENTICATION = utils.i32 (0x01),
  USE_ENCRYPTION = utils.i32 (0x02),
  USE_SSL = utils.i32 (0x02),
  READONLY_SERVER = utils.i32 (0x04),
  PROMPT_CREDENTIALS = utils.i32 (0x08),
  NO_AUTHENTICATION = utils.i32 (0x10),
  FAST_BIND = utils.i32 (0x20),
  USE_SIGNING = utils.i32 (0x40),
  USE_SEALING = utils.i32 (0x80),
  USE_DELEGATION = utils.i32 (0x100),
  SERVER_BIND = utils.i32 (0x200),
  AUTH_RESERVED = utils.i32 (0x800000000)
)
AUTHENTICATION_TYPES.DEFAULT = 0

SAM_ACCOUNT_TYPES = Enum (
  DOMAIN_OBJECT = 0x0 ,
  GROUP_OBJECT = 0x10000000 ,
  NON_SECURITY_GROUP_OBJECT = 0x10000001 ,
  ALIAS_OBJECT = 0x20000000 ,
  NON_SECURITY_ALIAS_OBJECT = 0x20000001 ,
  USER_OBJECT = 0x30000000 ,
  NORMAL_USER_ACCOUNT = 0x30000000 ,
  MACHINE_ACCOUNT = 0x30000001 ,
  TRUST_ACCOUNT = 0x30000002 ,
  APP_BASIC_GROUP = 0x40000000,
  APP_QUERY_GROUP = 0x40000001 ,
  ACCOUNT_TYPE_MAX = 0x7fffffff
)

USER_ACCOUNT_CONTROL = Enum (
  SCRIPT = 0x00000001,
  ACCOUNTDISABLE = 0x00000002,
  HOMEDIR_REQUIRED = 0x00000008,
  LOCKOUT = 0x00000010,
  PASSWD_NOTREQD = 0x00000020,
  PASSWD_CANT_CHANGE = 0x00000040,
  ENCRYPTED_TEXT_PASSWORD_ALLOWED = 0x00000080,
  TEMP_DUPLICATE_ACCOUNT = 0x00000100,
  NORMAL_ACCOUNT = 0x00000200,
  INTERDOMAIN_TRUST_ACCOUNT = 0x00000800,
  WORKSTATION_TRUST_ACCOUNT = 0x00001000,
  SERVER_TRUST_ACCOUNT = 0x00002000,
  DONT_EXPIRE_PASSWD = 0x00010000,
  MNS_LOGON_ACCOUNT = 0x00020000,
  SMARTCARD_REQUIRED = 0x00040000,
  TRUSTED_FOR_DELEGATION = 0x00080000,
  NOT_DELEGATED = 0x00100000,
  USE_DES_KEY_ONLY = 0x00200000,
  DONT_REQUIRE_PREAUTH = 0x00400000,
  PASSWORD_EXPIRED = 0x00800000,
  TRUSTED_TO_AUTHENTICATE_FOR_DELEGATION = 0x01000000
)

ADS_PROPERTY = Enum (
  CLEAR = 1,
  UPDATE = 2,
  APPEND = 3,
  DELETE = 4
)

ADS_TYPE = Enum (
  ADSTYPE_INVALID                  = 0,
  ADSTYPE_DN_STRING                = 1,
  ADSTYPE_CASE_EXACT_STRING        = 2,
  ADSTYPE_CASE_IGNORE_STRING       = 3,
  ADSTYPE_PRINTABLE_STRING         = 4,
  ADSTYPE_NUMERIC_STRING           = 5,
  ADSTYPE_BOOLEAN                  = 6,
  ADSTYPE_INTEGER                  = 7,
  ADSTYPE_OCTET_STRING             = 8,
  ADSTYPE_UTC_TIME                 = 9,
  ADSTYPE_LARGE_INTEGER            = 10,
  ADSTYPE_PROV_SPECIFIC            = 11,
  ADSTYPE_OBJECT_CLASS             = 12,
  ADSTYPE_CASEIGNORE_LIST          = 13,
  ADSTYPE_OCTET_LIST               = 14,
  ADSTYPE_PATH                     = 15,
  ADSTYPE_POSTALADDRESS            = 16,
  ADSTYPE_TIMESTAMP                = 17,
  ADSTYPE_BACKLINK                 = 18,
  ADSTYPE_TYPEDNAME                = 19,
  ADSTYPE_HOLD                     = 20,
  ADSTYPE_NETADDRESS               = 21,
  ADSTYPE_REPLICAPOINTER           = 22,
  ADSTYPE_FAXNUMBER                = 23,
  ADSTYPE_EMAIL                    = 24,
  ADSTYPE_NT_SECURITY_DESCRIPTOR   = 25,
  ADSTYPE_UNKNOWN                  = 26,
  ADSTYPE_DN_WITH_BINARY           = 27,
  ADSTYPE_DN_WITH_STRING           = 28
)

"""
2.5.5.1 DN String DN String
2.5.5.2 Object ID CaseIgnore String
2.5.5.3 Case Sensitive String CaseExact String
2.5.5.4 Case Ignored String CaseIgnore String
2.5.5.5 Print Case String Printable String
2.5.5.6 Numeric String Numeric String
2.5.5.7 OR Name DNWithOctetString Not Supported
2.5.5.8 Boolean Boolean
2.5.5.9 Integer Integer
2.5.5.10 Octet String Octet String
2.5.5.11 Time UTC Time
2.5.5.12 Unicode Case Ignore String
2.5.5.13 Address Not Supported
2.5.5.14 Distname-Address
2.5.5.15 NT Security Descriptor IADsSecurityDescriptor
2.5.5.16 Large Integer IADsLargeInteger
2.5.5.17 SID Octet String
"""
