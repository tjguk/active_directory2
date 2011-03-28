# -*- coding: iso-8859-1 -*-
import os, sys
import re

import win32api
from win32com import adsi

from . import core
from . import constants
from . import credentials
from . import exc
from . import types
from . import utils

class NotAContainerError (exc.ActiveDirectoryError):
  pass

class ADContainer (object):

  def __init__ (self, ad_com_object):
    try:
      self.container = exc.wrapped (ad_com_object.QueryInterface, adsi.IID_IADsContainer)
    except exc.ActiveDirectoryError, (error_code, _, _):
      if error_code == exc.E_NOINTERFACE:
        raise NotAContainerError

  def __iter__ (self):
    enumerator = exc.wrapped (adsi.ADsBuildEnumerator, self.container)
    while True:
      items = exc.wrapped (adsi.ADsEnumerateNext, enumerator, 10)
      if items:
        for item in items:
          yield exc.wrapped (item.QueryInterface, adsi.IID_IADs)
      else:
        break

class ADSimple (object):
  """A slender wrapper around an AD COM object which facilitates getting,
  setting and clearing an object's attributes plus pretty-printing to stdout.
  It does no validation of the names passed and an no conversions of the
  values. It can be used alone (most easily via the :func:`adsimple` function
  which takes an AD path and returns an ADSimple object). It also provides the
  basis for the other AD classes below.
  """

   #
   # For speed, hardcode the known properties of the IADs class
   #
  _properties = ["ADsPath", "Class", "GUID", "Name", "Parent", "Schema"]

  def __init__ (self, obj):
    utils._set (self, "com_object", obj.QueryInterface (adsi.IID_IADs))
    utils._set (self, "properties", self._properties)
    utils._set (self, "path", obj.ADsPath)

  def _put (self, name, value):
    operation = constants.ADS_PROPERTY.CLEAR if value is None else constants.ADS_PROPERTY.UPDATE
    exc.wrapped (self.com_object.PutEx, operation, name, value)

  def __getattr__ (self, name):
    try:
      return exc.wrapped (getattr, self.com_object, name)
    except (AttributeError, NotImplementedError):
      try:
        return exc.wrapped (self.com_object.Get, name)
      except NotImplementedError:
        raise AttributeError

  def __setattr__ (self, name, value):
    self._put (name, value)
    exc.wrapped (self.com_object.SetInfo)

  def __delattr__ (self, name):
    self._put (name, None)
    exc.wrapped (self.com_object.SetInfo)

  def __repr__ (self):
    return "<%s: %s>" % (self.__class__.__name__, self.as_string ())

  def __str__ (self):
    return self.as_string ()

  def __iter__(self):
    try:
      for item in ADContainer (self.com_object):
        yield self.__class__ (item)
    except NotAContainerError:
      raise TypeError ("%r is not iterable" % self)

  @classmethod
  def from_path (cls, path, cred=credentials.Passthrough):
    cred = credentials.credentials (cred)
    return cls (adsi.ADsOpenObject (path, cred.username, cred.password, cred.authentication_type))

  def as_string (self):
    return self.path

  def munge_attribute_for_dump (self, name, value):
    if value is None:
      return ""
    if isinstance (value, unicode):
      value = value.encode ("ascii", "backslashreplace")
    return str (value)

  def dump (self, ofile=sys.stdout):
    ofile.write (self.as_string () + u"\n")
    ofile.write ("{\n")
    for name in self.properties:
      ofile.write ("  %s => " % name)
      try:
        value = getattr (self, name)
      except AttributeError:
        value = "Unable to get value"
      ofile.write ("%s\n" % self.munge_attribute_for_dump (name, value))
    ofile.write ("}\n")

def adsimple (obj_or_path, cred=credentials.Passthrough):
  cred = credentials.credentials (cred)
  if isinstance (obj_or_path, ADSimple):
    return obj_or_path
  else:
    return ADSimple.from_path (obj_or_path, cred)

class ADBase (ADSimple):
  u"""Wrap an active-directory object for easier access
   to its properties and children. May be instantiated
   either directly from a COM object or from an ADs Path.

   Every IADs-derived object has at least the following attributes:

   Name, Class, GUID, ADsPath, Parent, Schema

   eg,

     import active_directory as ad
     users = ad.ad ("LDAP://cn=Users,DC=gb,DC=vo,DC=local")
  """

  _schema_cache = {}

  def __init__ (self, obj, cred=credentials.Passthrough, parse_schema=True):
    cred = credentials.credentials (cred)
    ADSimple.__init__ (self, obj)
    schema = None
    properties = self._properties
    is_container = False
    if parse_schema:
      try:
        schema = exc.wrapped (
          adsi.ADsOpenObject,
          exc.wrapped (getattr, obj, u"Schema", None),
          cred.username, cred.password,
          cred.authentication_type ## TODO: | constants.ADS_AUTHENTICATION.FAST_BIND
        )
      except exc.ActiveDirectoryError:
        pass
      else:
        properties, is_container = self._schema (schema)
    utils._set (self, u"properties", properties)
    utils._set (self, "is_container", is_container)

    #
    # At this point, __getattr__ & __setattr__ have enough
    # to decide whether an attribute belongs to the delegated
    # object or not.
    #
    utils._set (self, "cred", cred)
    utils._set (self, "connection", core.connect (cred=self.cred))
    utils._set (self, "dn", exc.wrapped (getattr, self.com_object, u"distinguishedName", None) or self.com_object.name)
    utils._set (self, "_delegate_map", dict ())

  def __getitem__ (self, key):
    return getattr (self, key)

  def __getattr__ (self, name):
    #
    # Special-case find_... methods to search for
    # corresponding object types.
    #
    if name.startswith (u"find_"):
      names = name[len (u"find_"):].lower ().split ("_")
      first, rest = names[0], names[1:]
      object_class = "".join ([first] + [n.title () for n in rest])
      return self._find (object_class)

    if name.startswith (u"search_"):
      names = name[len (u"search_"):].lower ().split ("_")
      first, rest = names[0], names[1:]
      object_class = u"".join ([first] + [n.title () for n in rest])
      return self._search (object_class)

    if name.startswith (u"get_"):
      names = name[len (u"get_"):].lower ().split (u"_")
      first, rest = names[0], names[1:]
      object_class = u"".join ([first] + [n.title () for n in rest])
      return self._get (object_class)

    #
    # Allow access to object's properties as though normal
    # Python instance properties. Some properties are accessed
    # directly through the object, others by calling its Get
    # method. Not clear why.
    #
    if name not in self._delegate_map:
      value = super (ADBase, self).__getattr__ (name)
      convert_from, _ = types.get_converter (name)
      self._delegate_map[name] = convert_from (value)
    return self._delegate_map[name]

  def __setitem__ (self, key, value):
    setattr (self, key, value)

  def __setattr__ (self, name, value):
    #
    # Allow attribute access to the underlying object's
    #  fields.
    #
    if name in self.properties:
      _, convert_to = types.get_converter (name)
      super (ADBase, self).__setattr__ (name, convert_to (value))
      self._invalidate (name)
    else:
      super (ADBase, self).__setattr__ (name, value)

  def _invalidate (self, name):
    #
    # Invalidate to ensure map is refreshed on next get
    #
    if name in self._delegate_map:
      del self._delegate_map[name]

  def as_string (self):
    return self.path

  def __str__ (self):
    return self.as_string ()

  def __repr__ (self):
    return u"<%s: %s>" % (exc.wrapped (getattr, self.com_object, u"Class") or u"AD", self.dn)

  def __eq__ (self, other):
    return self.com_object.Guid == other.com_object.Guid

  def __hash__ (self):
    return hash (self.com_object.Guid)

  def _get_parent (self):
    return self.__class__ (self.com_object.Parent)
  parent = property (_get_parent)

  @classmethod
  def _schema (cls, cschema):
    if cschema is None:
      return cls._properties, False

    if cschema.ADsPath not in cls._schema_cache:
      properties = \
        exc.wrapped (getattr, cschema, u"mandatoryProperties", []) + \
        exc.wrapped (getattr, cschema, u"optionalProperties", [])
      print "properties:", properties
      #~ print "container:", exc.wrapped (getattr, cschema, u"Container", False)
      cls._schema_cache[cschema.ADsPath] = properties, False ## exc.wrapped (getattr, cschema, u"Container", False)
    return cls._schema_cache[cschema.ADsPath]

  def munge_attribute_for_dump (self, name, value):
    if isinstance (value, (tuple, list)):
      value = "[(%d items)]" % len (value)
    else:
      value = super (ADBase, self).munge_attribute_for_dump (name, value)
      if isinstance (value, unicode):
        if len (value) > 60:
          value = value[:25] + "..." + value[-25:]
    return value

  def refresh (self):
    self._delegate_map.clear ()
    exc.wrapped (self.com_object.GetInfo)

  def walk (self):
    u"""Analogous to os.walk, traverse this AD subtree,
    depth-first, and yield for each container:

    container, containers, items
    """
    children = list (self)
    this_containers = [c for c in children if c.is_container]
    this_items = [c for c in children if not c.is_container]
    yield self, this_containers, this_items
    for c in this_containers:
      for container, containers, items in c.walk ():
        yield container, containers, items

  def flat (self):
    for container, containers, items in self.walk ():
      for item in items:
        yield item

  def set (self, **kwds):
    u"""Set a number of values at one time. Should be
     a little more efficient than assigning properties
     one after another.

    eg,

      import active_directory
      user = active_directory.find_user ("goldent")
      user.set (displayName = "Tim Golden", description="SQL Developer")
    """
    for k, v in kwds.items ():
      self._put (k, v)
    exc.wrapped (self.com_object.SetInfo)

  def _find (self, object_class):
    u"""Helper function to allow general-purpose searching for
    objects of a class by calling a .find_xxx_yyy method.
    """
    def _find (name):
      for item in self.search (objectClass=object_class, name=name):
        return item
    return _find

  def _search (self, object_class):
    u"""Helper function to allow general-purpose searching for
    objects of a class by calling a .search_xxx_yyy method.
    """
    def _search (*args, **kwargs):
      return self.search (objectClass=object_class, *args, **kwargs)
    return _search

  def _get (self, object_class):
    u"""Helper function to allow general-purpose retrieval of a
    child object by class.
    """
    def _get (rdn):
      return self.get (object_class, rdn)
    return _get

  def find (self, name):
    for item in self.search (name=name):
      return item

  def find_user (self, name=None):
    u"""Make a special case of (the common need of) finding a user
    either by username or by display name
    """
    name = name or exc.wrapped (win32api.GetUserName)
    for user in self.search (anr=name):
      return user

  def find_ou (self, name):
    u"""Convenient alias for find_organizational_unit"""
    return self.find_organizational_unit (name)

  def search (self, *args, **kwargs):
    filter = core.and_ (*args, **kwargs)
    #~ query_string = core.qs (base=self.ADsPath, filter=filter, attributes=["objectGuid"])
    query_string = u"<%s>;(%s);objectGuid;Subtree" % (self.ADsPath, filter)
    for result in core.query (query_string, connection=self.connection):
      guid = u"".join (u"%02X" % ord (i) for i in result['objectGuid'])
      yield ad (u"LDAP://<GUID=%s>" % guid, cred=self.cred)

  def get (self, object_class, relative_path):
    return ad (exc.wrapped (self.com_object.GetObject, object_class, relative_path))

  def new_ou (self, name, description=None, **kwargs):
    obj = exc.wrapped (self.com_object.Create, u"organizationalUnit", u"ou=%s" % name)
    exc.wrapped (obj.Put, u"description", description or name)
    exc.wrapped (obj.SetInfo)
    for name, value in kwargs.items ():
      exc.wrapped (obj.Put, name, value)
    exc.wrapped (obj.SetInfo)
    return ad (obj)

  def new_group (self, name, type=constants.GROUP_TYPES.DOMAIN_LOCAL | constants.GROUP_TYPES.SECURITY_ENABLED, **kwargs):
    obj = exc.wrapped (self.com_object.Create, u"group", u"cn=%s" % name)
    exc.wrapped (obj.Put, u"sAMAccountName", name)
    exc.wrapped (obj.Put, u"groupType", type)
    exc.wrapped (obj.SetInfo)
    for name, value in kwargs.items ():
      exc.wrapped (obj.Put, name, value)
    exc.wrapped (obj.SetInfo)
    return ad (obj)

  def new (self, object_class, sam_account_name, **kwargs):
    obj = exc.wrapped (self.com_object.Create, object_class, u"cn=%s" % sam_account_name)
    exc.wrapped (obj.Put, u"sAMAccountName", sam_account_name)
    exc.wrapped (obj.SetInfo)
    for name, value in kwargs.items ():
      exc.wrapped (obj.Put, name, value)
    exc.wrapped (obj.SetInfo)
    return ad (obj)

class WinNT (ADBase):

  def __eq__ (self, other):
    return self.com_object.ADsPath.lower () == other.com_object.ADsPath.lower ()

  def __hash__ (self):
    return hash (self.com_object.ADsPath.lower ())

class _Members (set):

  def __init__ (self, group, name="members"):
    super (_Members, self).__init__ (ad (i) for i in iter (exc.wrapped (group.com_object.members)))
    self._group = group
    self._name = name

  def _effect (self, original):
    group = self._group.com_object
    for member in (self - original):
      exc.wrapped (group.Add, member.AdsPath)
    for member in (original - self):
      exc.wrapped (group.Remove, member.AdsPath)
    self._group._invalidate (self._name)

  def update (self, *others):
    original = set (self)
    for other in others:
      super (_Members, self).update (ad (o) for o in other)
    self._effect (original)

  def __ior__ (self, other):
    return self.update (other)

  def intersection_update (self, *others):
    original = set (self)
    for other in others:
      super (_Members, self).intersection_update (ad (o) for o in other)
    self._effect (original)

  def __iand__ (self, other):
    return self.intersection_update (self, other)

  def difference_update (self, *others):
    original = set (self)
    for other in others:
      self.difference_update (ad (o) for o in other)
    self._effect (original)

  def symmetric_difference_update (self, *others):
    original = set (self)
    for other in others:
      self.symmetric_difference_update (ad (o) for o in others)
    self._effect (original)

  def add (self, elem):
    original = set (self)
    result = super (_Members, self).add (ad (elem))
    self._effect (original)
    return result

  def remove (self, elem):
    original = set (self)
    result = super (_Members, self).remove (ad (elem))
    self._effect (original)
    return result

  def discard (self, elem):
    original = set (self)
    result = super (_Members, self).discard (ad (elem))
    self._effect (original)
    return result

  def pop (self):
    original = set (self)
    result = super (_Members, self).pop ()
    self._effect (original)
    return result

  def clear (self):
    original = set (self)
    super (_Members, self).clear ()
    self._effect (original)

  def __contains__ (self, element):
    return  super (_Members, self).__contains__ (ad (element))

class Group (ADBase):

  def _get_members (self):
    return _Members (self)
  def _set_members (self, members):
    original = self.members
    new_members = set (ad (m) for m in members)
    for member in (new_members - original):
      exc.wrapped (self.com_object.Add, member.AdsPath)
    for member in (original - new_members):
      exc.wrapped (self.com_object.Remove, member.AdsPath)
  members = property (_get_members, _set_members)

  def walk (self):
    """Override the usual .walk method by returning instead:

    group, groups, users
    """
    members = self.members
    groups = [m for m in members if m.Class == u'group']
    users = [m for m in members if m.Class == u'user']
    yield (self, groups, users)
    for group in groups:
      for result in group.walk ():
        yield result

  def flat (self):
    for group, groups, members in self.walk ():
      for member in members:
        yield member

class WinNTGroup (WinNT, Group):
  pass

def namespaces ():
  return ADSimple (adsi.ADsGetObject (u"ADs:"))

_CLASS_MAP = {
  u"group" : Group,
}
_WINNT_CLASS_MAP = {
  u"group" : WinNTGroup
}
_namespace_names = None
def ad (obj_or_path, cred=credentials.Passthrough, connection=None):
  u"""Factory function for suitably-classed Active Directory
  objects from an incoming path or object. NB The interface
  is now  intended to be:

    ad (obj_or_path)

  @param obj_or_path Either an COM AD object or the path to one. If
  the path doesn't start with "LDAP://" this will be prepended.

  @return An _AD_object or a subclass proxying for the AD object
  """
  if isinstance (obj_or_path, ADBase):
    return obj_or_path

  global _namespace_names
  if _namespace_names is None:
    if cred.type == credentials.Credentials.PASSTHROUGH:
      _namespace_names = [u"GC:"] + [ns.Name for ns in exc.wrapped (adsi.ADsGetObject, u"ADs:")]
    else:
      _namespace_names = ["GC:", "LDAP:", "WinNT:"]
  matcher = re.compile ("(" + "|".join (_namespace_names)+ ")?(//)?([A-za-z0-9-_]+/)?(.*)")

  cred = credentials.credentials (cred)
  if isinstance (obj_or_path, basestring):
    #
    # Special-case the "ADs:" moniker which isn't a child of IADs
    #
    if obj_or_path == u"ADs:":
      return namespaces ()

    scheme, slashes, server, dn = matcher.match (obj_or_path).groups ()
    if scheme is None:
      scheme, slashes = u"LDAP:", u"//"
    if scheme == u"WinNT:":
      moniker = dn
    else:
      moniker = utils.escaped_moniker (dn)
    obj_path = scheme + (slashes or u"") + (server or u"") + (moniker or u"")
    flags = cred.authentication_type
    if server:
      flags |= constants.AUTHENTICATION_TYPES.SERVER_BIND
    obj = exc.wrapped (adsi.ADsOpenObject, obj_path, cred.username, cred.password, flags)
  else:
    obj = obj_or_path
    scheme, slashes, server, dn = matcher.match (obj_or_path.AdsPath).groups ()

  if dn == u"rootDSE":
    return ADSimple (obj)

  if scheme == u"WinNT:":
    class_map = _WINNT_CLASS_MAP.get (obj.Class.lower (), WinNT)
  else:
    class_map = _CLASS_MAP.get (obj.Class.lower (), ADBase)
  return class_map (obj, cred)
