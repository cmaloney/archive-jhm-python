# This file is licensed under the terms of the Apache License, Version 2.0
# Please see the file COPYING for the full text of this license
#
# Copyright 2010-2011 Tagged

import glob, jhm, os, subprocess, sys
from itertools import chain
#TODO: Write README header comment
#TODO: Parallelize test searching
#TODO: Implied tests (requires overriding GetFile* to search for tests if flag is set)

class TestError(jhm.BuildError):
  """An error related to running a unit test, rather than a build problem"""

def RunTest(args):
  """Run the given build command with the given arguments."""
  opened = subprocess.Popen(args, stdin=subprocess.PIPE)
  opened.communicate()

  if opened.returncode != 0:
    raise TestError("FAILED %s, Returncode %s" % (args, opened.returncode))


def GetArgParser(parser=jhm.GetArgParser()):
  """Get an argument parser which will build the options for JHM-test."""
  parser.add_argument('-T','--test-verbose', dest='test_verbose', default=False, action='store_true',
      help='Run tests with the verbose flag (-v). Implies execute (-x).'),
  parser.add_argument('-i','--implied-tests', dest='implied_tests', default=False, action='store_true',
      help='Finda and build all tests of all dependencies of the given targets, including test dependencies. Only works with -f at the moment, Good chance it won\'t work.')
  parser.add_argument('-d','--direct-tests', dest='direct_tests', default=False, action='store_true',
      help='Run only tests directly inferrable from the filenames in the target set.')
  parser.add_argument('-s','--search', dest='search', default=None,
      help='Where to search for tests (cwd, cwd+, all)')
  parser.add_argument('--check-inc', dest='check_inc', default=None, action='store_true',
      help='Check all inc_trees as well as src_tree for tests')
  parser.add_argument('--test-ext', dest='test_ext', default=None,
      help='Extension unit tests have. Default is \'test\'')
  parser.add_argument('--atom-test-only', dest='atom_test_only', default=False, action='store_true',
      help='Only check for atom.test_ext, not any length extension list followed by test_ext')
  parser.add_argument('--no-test-trees', dest='no_test_trees', default=False, action='store_true',
      help='Don\'t check for tests in test-trees section from config')
  parser.add_argument('--no-test-targets', dest='no_test_targets', default=False, action='store_true',
      help='Don\'t use any test targets listed in the config')
  return parser

class Env(jhm.Env):
  """A JHM build environment with extensions for unit testing."""

  def __init__(self, options):
    #Basic setup
    if options.test_verbose:
      options.exec_targets = True

    #Setup that must happen before env init, because env init will touch it.
    self.__implied_targets = []

    super(Env, self).__init__(options)
    self.__check_inc = options.check_inc if options.check_inc is not None else bool(self.GetConfig('check_inc', section='test', default=False))
    self.__test_ext_list = [options.test_ext if options.test_ext is not None else self.GetConfig('ext', section='test', default='test'), '']

    #Keep track of what was test added vs. non-test to ensure we run non-tests before tests.
    self.__base_targets = self.target_file_set
    self.__test_targets = set()

    if self.search is not None:
      search = self.search

      def AddTestIfAvailable(path):
        """Given a path, sees if there are any unit tests for that path."""

        f_obj = self.GetFileFromPath(path)
        full_ext_list = f_obj.ext_list
        if options.atom_test_only:
          f_test = f_obj.GetRelatedFileAndTree(ext_list=self._test_ext_list)
          self.AddTestIfAvailable(f_test)
        else:
          while len(full_ext_list) > 0:
            f_test = f_obj.GetRelatedFileAndTree(ext_list=full_ext_list[:-1] + self.__test_ext_list)
            self.AddTestIfAvailable(f_test)

            full_ext_list = full_ext_list[:-1]

      def SearchDirAndSubdir(directory):
        """Search a directory and it's subdirectories for unit tests."""
        for root, dirs, files in os.walk(directory):
          for f in files:
            AddTestIfAvailable(os.path.join(root, f))

      def SearchDir(directory):
        """Search a directory for unit tests."""
        for path in os.listdir(directory):
          full_path = os.path.join(directory, path)
          if os.path.isfile(full_path):
            AddTestIfAvailable(full_path)

      def FindTestsInDir(dir_search_func, start_path):
        """Find all unit tests using the dir_search_function in the given path using any user set options."""
        dir_search_func(start_path)
        rel_path = self.FindTree(start_path).GetRelPath(start_path)

        if self.__check_inc:
          for tree in self.YieldEachInTree():
            dir_search_func(os.path.join(tree.path, rel_path) if rel_path != '' else tree.path)

        if not options.no_test_trees:
          for path in self.YieldConfigSection('test-tree'):
            self.AddIncTreeFromPath(path)
            dir_search_func(os.path.join(tree.path, rel_path) if rel_path != '' else tree.path)

      if search == 'cwd':
        FindTestsInDir(SearchDir, os.getcwd())
      elif search == 'cwd+':
        FindTestsInDir(SearchDirAndSubdir, os.getcwd())
      elif search == 'all':
        FindTestsInDir(SearchDirAndSubdir, self.__src_tree.path)

      else:
        raise TestError('Invalid search. Search must be "cwd", "cwd+", or "all"')

    if not (options.no_test_targets or options.targets):
      for f in self.GetConfig('test_targets', default='').split(','):
        f = f.strip();
        if f == '':
          continue
        self.AddPath(f)

    #Add tests of directly stated dependencies.
    if options.direct_tests:
      self.FindAndAddTests(self.target_file_set)

  def FindTests(self, f):
    #Search for tests related to the file by name, and add them to targets.
    found_tests = set()
    for possible in glob.glob(os.path.join(self.__src_tree.path, f.branch, f.atom + '*.test*')):
      #Get the test executable
      branch, base, ext_list = self.SplitRelPath(self.__src_tree.GetRelPath(possible))
      test = self.GetFileAndTree(branch, base, ext_list[:ext_list.index('test')+1] + [''])
      if test.is_available:
        found_tests.add(test)
    return found_tests

  def FindAndAddTests(self, file_set):
    map(self.AddTest, reduce(lambda x, y: x | y, map(self.FindTests, file_set),set()))

  def AddTest(self, f):
    self.__test_targets.add(f)
    self.AddTarget(f)

  def AddTestIfAvailable(self, f):
    if f.is_available:
      self.AddTest(f)

  def Exec(self):
    #Run all the tests in verbose mode, before the files they're testing.
    #Reversed implied targets, since we construct the list as things are come across in JHM, so reverse ordering gives
    #us a toposort from leaves to roots.
    for f in chain(reversed(self.__implied_targets), self.__test_targets - set(self.__implied_targets), self.__base_targets):
      if os.access(f.abs_path, os.X_OK):
        print f
        RunTest([f.abs_path] + (['-v'] if self.options.test_verbose else []))

  def Queue(self, item_set):
    #Queue the items
    retval = super(Env, self).Queue(frozenset(item_set))
    #See if there are any  tests for the file, and if so, add them as well
    #TODO: The set(self.__implied_targets could be fairly expensive.
    if self.options.implied_tests:
      for i in item_set:
        if isinstance(i, jhm.Job) or i in self.target_file_set:
          continue
        found_tests = self.FindTests(i) - self.target_file_set
        self.__implied_targets += found_tests
        map(self.AddTarget, found_tests)
    return retval

  @property
  def check_inc(self):
    return self.__check_inc

  @property
  def test_ext_list(self):
    return self.__test_ext_list

  @property
  def search(self):
    return self.options.search.lower() if self.options.search is not None else self.options.search
