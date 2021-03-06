# -*- coding: iso-8859-1 -*-
u"""active_directory - a lightweight wrapper around COM support
 for Microsoft's Active Directory

Active Directory is Microsoft's answer to LDAP, the industry-standard
directory service holding information about users, computers and
other resources in a tree structure, arranged by departments or
geographical location, and optimized for searching.

There are several ways of attaching to Active Directory. This
module uses the Dispatchable LDAP:// objects and wraps them
lightly in helpful Python classes which do a bit of the
otherwise tedious plumbing. The module is quite naive, and
has only really been developed to aid searching, but since
you can always access the original COM object, there's nothing
to stop you using it for any AD operations.

* :func:`ad` - this is the wrap-all function which transforms an LDAP: moniker
  into a Python object which offers the existing properties and members in
  Pythonic wrappers. It will also convert an existing LDAP COM Object::

    import active_directory as ad

    me =

* :func:`find_user`, :func:`find_group`, :func:`find_ou` - these are module-level
  convenience functions which each return a Python object corresponding to the
  user, group or ou of the name passed in::

    import active_directory as ad

    camden_users = (obj for obj in ad.find_ou ("Camden") if obj.Class == "User")

* The active directory class (ADBase or a subclass) will determine
  its properties and allow you to access them as instance properties::

     import active_directory as ad
     goldent = ad.find_user ("goldent")
     print goldent.displayName

* Any object returned by the AD object's operations is itself
  wrapped as an AD object so you get the same benefits::

    import active_directory as  ad
    users = ad.root ().child ("cn=users")
    for user in users.search (displayName='Tim*'):
      print user.displayName

* To search the AD, there are two module-level general
  search functions, and module-level convenience functions
  to find a user, computer etc. Usage is illustrated below::

   import active_directory as ad

   for user in ad.search (
     objectClass='User',
     ad.core.or_ (displayName='Tim Golden', sAMAccountName='goldent')
   ):
     #
     # This search returns an ADUser object
     #
     print user

* Typical usage will be::

    import active_directory as ad

    for computer in ad.search (objectClass='computer'):
      print computer.displayName

(c) Tim Golden <mail@timgolden.me.uk> October 2004-2011
Licensed under the (GPL-compatible) MIT License:
http://www.opensource.org/licenses/mit-license.php

Many thanks, obviously, to Mark Hammond for creating
the pywin32 extensions without which this wouldn't
have been possible. (Or would at least have been much
more work...)
"""
__VERSION__ = u"2.0rc1"

import os, sys
import logging

from win32com import adsi
import win32com.client

from .adcore import adcore, namespaces, root_dse
from .adbase import adbase
from .adobject import adobject
from . import constants
from . import core
from . import exc
from .log import logger
from . import utils

def AD (server=None, cred=None, use_gc=False, factory=adobject):
  logger.debug ("server=%s, cred=%s, use_gc=%s, factory=%s", server, cred, use_gc, factory)
  if use_gc:
    scheme = u"GC:"
  else:
    scheme = u"LDAP:"
  if server:
    base_moniker = scheme + "//" + server + "/"
  else:
    base_moniker = scheme + "//"
  return factory (core.root_obj (server, scheme, cred=cred), cred=cred)

#
# Convenience functions for common needs
#
def find (*args, **kwargs):
  return _root ().find (*args, **kwargs)

def find_user (name=None):
  return _root ().find_user (name)

def find_computer (name=None):
  return _root ().find_computer (name)

def find_group (name):
  return _root ().find_group (name)

def find_ou (name):
  return _root ().find_ou (name)

def search (*args, **kwargs):
  return _root ().search (*args, **kwargs)

#
# root returns a cached object referring to the
#  root of the logged-on active directory tree.
#
_ad = None
def _root (server=None, cred=None):
  global _ad
  if _ad is None:
    _ad = AD (cred=cred)
  return _ad

