import os, sys
import unittest as unittest0
try:
  unittest0.skipUnless
  unittest0.skip
except AttributeError:
  import unittest2 as unittest
else:
  unittest = unittest0
del unittest0

import win32com.client

from active_directory2 import core, credentials, exc
from active_directory2.tests import config

com_object = win32com.client.CDispatch

class TestBaseMoniker (unittest.TestCase):

  def test_defaults (self):
    self.assertEquals (core._base_moniker (), "LDAP://")

  def test_server (self):
    self.assertEquals (core._base_moniker (server="server"), "LDAP://server/")

  def test_scheme (self):
    self.assertEquals (core._base_moniker (scheme="GC:"), "GC://")

  def test_server_and_scheme (self):
    self.assertEquals (core._base_moniker (server="server", scheme="GC:"), "GC://server/")

  def test_cacheing (self):
    #
    # Use a ridiculously long server name to defeat Python string interning
    #
    server = "s" * 1024
    m1 = core._base_moniker (server=server)
    m2 = core._base_moniker (server=server)
    self.assertIs (m1, m2)

class TestRootDSE (unittest.TestCase):

  def _expected_moniker (self, scheme):
    if config.is_inside_domain:
      return "%s//rootDSE" % scheme
    else:
      return "%s//%s/rootDSE" % (scheme, config.server or config.dc)

  @unittest.skipUnless (config.is_inside_domain, "Serverless testing not enabled")
  def test_defaults (self):
    obj = core.root_dse ()
    self.assertIsInstance (obj, com_object)
    self.assertEquals (obj.ADsPath, self._expected_moniker ("LDAP:"))

  def test_server (self):
    obj = core.root_dse (server=config.server)
    self.assertIsInstance (obj, com_object)
    self.assertEquals (obj.ADsPath, self._expected_moniker ("LDAP:"))

  @unittest.skipUnless (config.is_inside_domain, "Serverless testing not enabled")
  def test_scheme (self):
    obj = core.root_dse (scheme="GC:")
    self.assertIsInstance (obj, com_object)
    self.assertEquals (obj.ADsPath, self._expected_moniker ("GC:"))

  def test_server_and_scheme (self):
    obj = core.root_dse (server=config.server, scheme="GC:")
    self.assertIsInstance (obj, com_object)
    self.assertEquals (obj.ADsPath, self._expected_moniker ("GC:"))

  @unittest.skipUnless (config.is_inside_domain, "Serverless testing not enabled")
  def test_cacheing (self):
    obj1 = core.root_dse ()
    obj2 = core.root_dse ()
    self.assertIs (obj1, obj2)

class TestRootMoniker (unittest.TestCase):

  def setUp (self):
    self.server = config.server or config.dc

  def _expected (self, server=None, scheme="LDAP:"):
    return scheme + "//" + ((server + "/") if server else "") + config.domain_dn

  @unittest.skipUnless (config.is_inside_domain, "Serverless testing not enabled")
  def test_defaults (self):
    self.assertEquals (core.root_moniker (), self._expected ())

  def test_server (self):
    self.assertEquals (core.root_moniker (server=self.server), self._expected (server=self.server))

  def test_server_and_scheme (self):
    self.assertEquals (core.root_moniker (server=self.server, scheme="GC:"), self._expected (server=self.server, scheme="GC:"))

  @unittest.skipUnless (config.is_inside_domain, "Serverless testing not enabled")
  def test_scheme (self):
    self.assertEquals (core.root_moniker (scheme="GC:"), self._expected (scheme="GC:"))

  @unittest.skipUnless (config.is_inside_domain, "Serverless testing not enabled")
  def test_cacheing (self):
    self.assertIs (core.root_moniker (), core.root_moniker ())

class TestRootObj (unittest.TestCase):

  def _test (self, *args, **kwargs):
    root_obj = core.root_obj (cred=config.cred, *args, **kwargs)
    self.assertIsInstance (root_obj, com_object)
    self.assertEquals (root_obj.ADsPath, core.root_moniker (*args, **kwargs))

  @unittest.skipUnless (config.is_inside_domain, "Serverless testing not enabled")
  def test_defaults (self):
    self._test ()

  def test_server (self):
    self._test (server=config.server)

  @unittest.skip ("Doesn't seem possible to come up with a reproducible test")
  def test_server_and_scheme (self):
    self._test (server=config.server, scheme="GC:")

  @unittest.skip ("Doesn't seem possible to come up with a reproducible test")
  @unittest.skipUnless (config.is_inside_domain, "Serverless testing not enabled")
  def test_scheme (self):
    self._test (scheme="GC:")

  @unittest.skipUnless (config.is_inside_domain, "Serverless testing not enabled")
  def test_cacheing (self):
    self.assertIs (core.root_obj (cred=config.cred), core.root_obj (cred=config.cred))

class TestSchemaObj (unittest.TestCase):

  def _expected (self, server=None):
    return "LDAP://" + ((server + "/") if server else "") + "CN=Schema,CN=Configuration," + config.domain_dn

  @unittest.skipUnless (config.is_inside_domain, "Serverless testing not enabled")
  def test_defaults (self):
    schema_obj = core.schema_obj (cred=config.cred)
    self.assertIsInstance (schema_obj, com_object)
    self.assertEquals (schema_obj.ADsPath, self._expected ())

  def test_server (self):
    schema_obj = core.schema_obj (config.server, cred=config.cred)
    self.assertIsInstance (schema_obj, com_object)
    self.assertEquals (schema_obj.ADsPath, self._expected (config.server))

class TestClassSchema (unittest.TestCase):

  def _expected (self, class_name, server=None):
    #
    # The abstract schema is a special, serverless object
    #
    if config.is_inside_domain or server is None:
      return "LDAP://" + class_name + ",schema"
    else:
      return "LDAP://%s/%s,schema" % (server, class_name)

  @unittest.skipUnless (config.is_inside_domain, "Serverless testing not enabled")
  def test_class_with_defaults (self):
    class_schema = core.class_schema ("user")
    self.assertIsInstance (class_schema, com_object)
    self.assertEquals (class_schema.ADsPath, self._expected ("user"))

  def test_class_with_server (self):
    class_schema = core.class_schema ("user", server=config.server, cred=config.cred)
    self.assertIsInstance (class_schema, com_object)
    self.assertEquals (class_schema.ADsPath, self._expected ("user", server=config.server))

class TestAttributes (unittest.TestCase):

  @unittest.skipUnless (config.is_inside_domain, "Serverless testing not enabled")
  def test_defaults (self):
    all_attributes = set (i.ldapDisplayName for i in core.schema_obj () if i.Class == "attributeSchema")
    attributes = core.attributes (cred=config.cred)
    self.assertSetEqual (all_attributes, set (name for name, _ in attributes))
    self.assertTrue (all (i.Class == "attributeSchema" for i in attributes))

  def test_server (self):
    all_attributes = set (i.ldapDisplayName for i in core.schema_obj (server=config.server, cred=config.cred) if i.Class == "attributeSchema")
    attributes = core.attributes (server=config.server, cred=config.cred)
    self.assertSetEqual (all_attributes, set (name for name, _ in attributes))
    self.assertTrue (all (i.Class == "attributeSchema" for i in attributes))

  def test_one_attribute (self):
    attribute = core.attribute ("displayName", server=config.server, cred=config.cred)
    self.assertEquals (attribute.ldapDisplayName, "displayName")
    self.assertTrue (attribute.Class == "attributeSchema")

  def test_attributes_not_found (self):
    with self.assertRaises (exc.AttributeNotFound):
      list (core.attributes (["does_not_exist"], server=config.server, cred=config.cred))

  def test_attribute_not_found (self):
    with self.assertRaises (exc.AttributeNotFound):
      core.attribute ("does_not_exist", server=config.server, cred=config.cred)

class TestQuery (unittest.TestCase):

  def _test (self):
    root = core.root_obj (server=config.server, cred=config.cred)
    return core.query (root, "name=CN=Domain Admins", attributes=['sAMAccountname'])

  def test_domain_admins (self):
    for attributes in self._test ():
      self.assertEquals (attributes['sAMAccountname'], ['Domain Admins'])

  def test_results_are_mappings (self):
    for attributes in self._test ():
      self.assertIsInstance (attributes, dict)

  def test_results_are_mappings (self):
    for attributes in self._test ():
      for name, values in attributes:
        self.assertIsInstance (values, list)

class TestOpenObject (unittest.TestCase):

  def test_root (self):
    root = core.root_obj (server=config.server, cred=config.cred)
    obj = core.open_object (root.ADsPath, cred=config.cred)
    self.assertEquals (obj.GUID, root.GUID)

