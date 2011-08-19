# This file is licensed under the terms of the Apache License, Version 2.0
# Please see the file COPYING for the full text of this license
#
# Copyright 2010-2011 Tagged

"""Builds targets in the native source base using expert knowledge.


JHM == Jason Hates Make

My name is Jason and I hate make.  Make sucks.  Make has always sucked and everyone has always hated it.

The whole idea of having to write down separately and in excruciating detail information which is already implicitly
obvious in your source base makes no sense.  It is a pointless exercise in tedium and the result is almost always out of
date. Packages like autotools automate some of the tedium, but just mask the underlying problem. Every time I trace a
bug back to a badly constructed make file, I want to strangle whoever came up with the whole, rotten idea of make files.

Whew... ok... deep, cleansing breath...

So, what can be done about it?  I'll tell you.

This tool can build projects without having to be told how. You tell JHM what you want, then it will search from that
point, looking only at files that matter, in parallel, locate all dependencies, and construct your output as efficiently
as possible.


OVERVIEW
JHM is a tool that you tell what you want, and it will do it's best effort to build that for you. It keeps your source
tree clean from generated items, allowing you to focus on the core of your project. It keeps you from having to
duplicate effort by automatically finding dependencies instead of requiring you to list them, and reducing maintenance
burden by making it so it only has to be configured once ever for a given machine, rather than once for every different
project you try to build. It can be configured to use special commands for cross compilation, have multiple different
configurations for different types of builds (release, debug, ex.), needs to be taught how to compile on a given
platform only once, and can be taught new tricks at the system, user, or project level.


USAGE
jhm [options] [targets]
See jhm --help for more details, or the function GetArgParser().


ENVIRONMENT
JHM works by having a complete world view of your project. This world view is stored in the JHM Environment (Env).
An environment contains Trees, Files, and Jobs. The heart of the environment, is the project root. This directory is
automatically found by jhm by locating the nearest parent folder containing a folder named .jhm (This folder contains
configuration information, which we will discuss later).  The project root must have the source directory as a
subfolder (arbitrarily nested).  The output directory should be inside the project root as well, but is not required.
Generally speaking, the folders are laid out like this:

  $(build root)/
    .jhm/
    $(source_dir)/
    $(out_dir)/


TREES
A tree is a directory which JHM will look in to try and find files related to the build. Within the JHM environment,
files (discussed in detail later), are relative paths, which can exist in any tree. When you combine a relative path
with a tree you get an absolute path to a file in the filesystem.

There are three types of trees that JHM deals with:

    (1) the source tree,
    (2) the output tree,
    (3) zero or more external include trees

The source tree and output tree are the source directory, and the out directory respectively. Include trees are
specified through configuration. Note there is only ever one source tree, and one output tree. Also note that for
convenience, all the include trees and the source tree are sometimes grouped together and called the "input" trees.


FILES
A relative path. Files are associated with a single tree, either the first input tree in which they appear, or the
output tree which indicates the file must be generated. Within the codebase the relative path is broken up into several
meaningful pieces as documented below. Note that JHM depends on these different pieces to find similar files. For
instance, if you have a file which is a C++ header, which has the ext_list ['h'] (because it is a .h file), JHM will
infer that a file which has the same relative path except for swapping the ['h'] for a ['o'] may be needed for linking
any files which include the header.

The different pieces can be combined as follows (see below for example filepaths):

  <path> -> <tree> <rel_path>
  <rel_path> -> <branch> <name>
  <name> -> <base> <ext_list>
  <base> -> <prefix> <atom>

  path:
    the complete string, as given. This is the absolute path to where the file resides in the filesystem.
  tree:
    the tree in which the file resides.
  rel_path:
    the unique identity of this file within the environment. This is the portion of the path following the tree.
  branch:
    the directory within the tree where the file resides, so the portion of the rel_path from the beginning to the last
    slash.
  name:
    the portion of the path after the last slash, the "filename" when you're talking in general about filesystems.
  base:
    the portion of the name up to but not including the last dot.
  ext_list:
    the portion of the name after the last dot, split by '.' and represented as a list of extensions. Note that the list
    always has length greater than or equal to one. An empty extension is a valid within the extension list (Such an
    extension is given to Linux executables).
  prefix:
    the portion of the base which is always the same for a file of a given kind. For example, static libraries always
    start with 'lib'.  This is often an empty string.
  atom:
    the portion of the base after the prefix.  This is the kernel of the file's identify and the portion of the name
    which is shared between different but related files.  In the case when the prefix is the empty string, the base and
    the atom are the same string.

Here's an example:

  project_root = '/project/'
  out_tree  = '/project/out'
  path      = '/project/out/there/everywhere/libthorium.a'
  tree      = OUT:/project/out
  rel_path  = '/there/everywhere/libthorium.a'
  branch    = '/there/everywhere'
  name   = 'libthorium.a'
  base   = 'libthorium'
  ext_list = ['a']
  prefix = 'lib'
  atom   = 'thorium'


JOBS
Jobs are basically manipulations/transformations which can be applied to files to go from input to output, or to
create new files.  A job may or may not take an input file, but always produces at least one output file.
For each file the user asks for in the output tree, JHM figures out a job or chain of jobs which can produce it.  If
JHM can't find such a chain, then the file is unproducable.  Since job chains can be arbitrarily long, this gives JHM
a tremendous amount of flexibility, as it can cleanly deal with automatic generation of input files.

For example, CompileC is a job which compiles ['.c'] files to ['.o'] files.


JOBKIND and FILEKIND
JobKinds and FileKinds are abstract types of jobs and files respectively. A FileKind you can roughly think of as a
mime-type, in that file kinds apply to specific mimetypes. The primary differentiator between filekinds and mimetypes
is that filekinds look solely at file extension to determine file type, rather than contents. The key piece of
functionality that filekinds provide is insight into finding the files a given file directly requires (Such as through
#include in C/C++). JobKinds describe how to go from a given input to a set of given outputs in a predictable way.
JobKinds also contain code which can, given the input file, and files it requires, figure out the files which the job
must depend upon (.o modules for each included header, for instance). File kinds also can contain information about
prefixes, which is to say, optional start extensions. This is important for instance when on windows you are building a
shared library, which by convention have the prefix lib, even though the source file generating that .so, will
frequently not share the prefix.


REQUIRES and DEPENDS
In JobKinds and FileKinds I mentioned requires and depends. These are two related, but fundamentally different items
within the world of JHM.  Files have requires, and jobs have depends.

Requires are the explicitly declared needs of a file. For instance, if a file #includes a header, it 'requires' that
header, and thus that header is part of its req_set (set of requirements).

Dependencies are the files needed by a job, which may or may not explicitly by stated by a user. For instance, when
linking a program, the 'link' job would depend on object files of all the source files which are part of that program,
even though this information is never explicitly stated.


ALGORITHM
You start JHM by asking for one or more file which you want built. When you do this, jhm calls GetFile on the filename,
to try and locate the file. It will begin by locating which tree the file lives in. It does this by searching the source
directory, then the include trees one by one in precedence order until it finds where the file physically exists. If
the file does not exist in any of the input trees, then JHM assumes the file must be produced, and is assigned the
output tree.

Once JHM has all the files, it tries to build them. For a file, being built means that it exists and that all the files
it requires have been built.  For a job, being built means that all the job's output files have been created.  When JHM
tries to build a job in the output tree, it begins by using the FindAvailability function to figure out a chain of
jobs that can somehow build the file.

The FindAvailability function checks first to see if the file is in a source or include tree.  If so, the file
already exists, and is therefore available.  Next, the function cycles through the JobKinds that can produce the
file, finding the input file that would be necessary to produce the given output file by the given job, and whether
that file is available.  If the file is available, then the current file is also marked as available, and its
producer is set to be the job that was discovered.  This is effectively a depth-first search for job chains which
can produce the given file.  Note that it is acceptable that two different jobs can produce the same file, as JobKinds
are specified in order of precedence.

Once we've determined a file is available, we simply call its build function.  This will cause JHM to traverse up and
down the dependency/requires tree, expanding it as necessary, at all times working on something relevant for the file
which needs to be built. JHM will queue up things that need to be built/finished, and will have an arbitrary number of
workers (Defaults to the number of cores in your machine), working on whittling the queue down to nothing. When the
queue is empty, it means that everything requested was built. If there is a build error at some point in the process,
JHM will print all related output and wait for all the other workers to exit.

JHM stores a cache file for each file it builds.  The cache file contains extra arguments/configuration for jobs
which use the file, as well as the requires for the file (remember, files have requires, jobs have dependencies).
If JHM determines that this information is up to date, then it will skip trying to build the given output file,
asserting that it is already built, and load the cached information, saving JHM from having to explore more of the
dependency graph and run the job/jobs needed to build the file.

CONFIGURATION
JHM can be configured at the System, User, Project, and File level. System configuration should include standard
compilation pieces that all projects will need, such as compiling C/C++, linking objects to make an executable, etc.
The user configuration level should contain user-specific settings, such as possibly modifying the default number of
workers JHM executes with, and adding specific flags to different build jobs. The project level should contain project
specific job kinds and file kinds, as well as project specific configuration, such as the location of the source
and output directories, as well as project-specific build configurations (debug, release, etc).

System configuration lives in the folder /etc/jhm, user configuration lives in the folder ~/.jhm, and project
configuration lives in the .jhm folder at the project root. JHM tries to load the config files in the following order:
config_system_arch.jhm, config_system.ext, config_arch.ext, config.jhm, jhm.jhm where config is the selected
build configuration (debug, release, etc.), system is the operating system (Linux, Windows, etc.), and architecture
is the machine architecture (x86, x86_64, etc.).

JHM configuration files have the general format of sections, followed by key-value pairs. A section name is marked
by the line starting with a +. k-v pairs, are simply of the form 'key=value', or just 'key'. You can specify a 'parent'
configuration which the configuration inherits from by specifying 'parent=filename' before you start any section. There
are a number of jhm options which can be set in jhm config files, and a number of job kinds take standard arguments. To
read them look at the __init__ function for the Env class.

FileKinds and JobKinds are specializations/inherit from jhm.{JobKind, FileKind}, and as such should be written in a
python file. They are loaded using the same order as jhm config files, except they begin with 'file_kinds' and
'job_kinds' as prefixes, instead of the configuration name or 'jhm'. Just inheriting from the class in an imported
module does not cause your job kind/file kind to be recognized by jhm. Rather, it must be in an array file_kinds or
job_kinds within the loaded file.

TODO (Short run)
Make it so some configs are not buildable again (is_buildable=no/false/off), and the configs can be mixed and matched.
    Ex. A specific config could enable/disable some feature.
Get rid fo the spinlock that happens when one item is in the queue being processed and all others are waiting on it.

"""

"""Misc. Thoughts (Long run TODO)

  Should probably introduce a generic concept of Buildable, which means "has dependencies", and a "build function". The
    buildable interface would enforce the JHM requirements on buildables, rather than the slightly duplicate code that
    currently exists. The buildable would hold an array of dependencies, which are things which must be done in order
    for the buildable to be run, as well as a list of things which depend on the buildable.
"""

import argparse, heapq, copy, imp, multiprocessing, subprocess, threading, os, os.path, platform, re, signal, sys, threading, traceback

from itertools import chain, ifilter

class BuildError(Exception):
  """An error in attempting to build"""

def RunCmd(args, return_output=False, print_command=False):
  """Run the given build command with the given arguments."""
  if print_command:
    print ' '.join(args)

  try:
    opened = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  except OSError as e:
    if e.errno == 2:
      raise BuildError('Program "%s" is not in PATH' % args[0])
    raise
  retval = opened.communicate()

  if opened.returncode != 0:
    if not print_command:
      print ' '.join(args)
    raise BuildError("ERROR RUNNING COMMAND: %s, Returncode %s\nSTDOUT:\n%s\nSTDERR:\n%s" % (args, opened.returncode, retval[0],retval[1]))

  if return_output:
    return retval

#Things that should be in the python stdlib..
def EnsurePathExists(path):
  """Makes the path if possible. If the path already exists, do nothing. Threadsafe (makedirs isn't)."""

  try:
    os.makedirs(path)
  except OSError as e:
    if e.errno != 17:
      raise

def GetTimestamp(path):
  return os.path.getmtime(path) if os.path.exists(path) else 0

class MultithreadProcessingQueue(object):
  """JHM-Specifc processing queue/set."""
  def __init__(self, do_func, queue_item_func, num_cores, print_worker_stacks):
    #Stash for use.
    self.__do_func = do_func
    self.__queue_item_func = queue_item_func

    #Task storage
    self.__queue = []          #The priority queue of items to be worked on.
    self.__queue_set = set()   #The set of items currently considered to be in the queue (queue | working_set)
    self.__task_set = set()         #The full set of items which must be built
    self.__lock = threading.Lock()  #The lock for all the above

    #Messages to controller thread from workers.
    self.__worker_event = threading.Event()
    self.__worker_dead = threading.Event()

    #Nice printing for threads requires locking.
    self.__print_lock = threading.RLock()

    #Messages to all worker threads
    self.__worker_go = threading.Event()        #Set to false when the task_queue is empty to prevent spinning.
    self.__stop_workers = threading.Event()     #Set when the user has asked all workers to kill themselves.

    #The worker threads
    def Worker():
      """Processesor of items in the queue."""
      def Get():
        """Get something to do, warn others if there is now nothing to do"""
        item = None
        with self.__lock:
          if len(self.__queue) > 0:
            item = self.__queue.pop(0)
          if len(self.__queue) == 0:
            self.__worker_go.clear()
          return item

      #Run as a worker until we're told otherwise
      while not self.__stop_workers.is_set():
        #Catch all exceptions, we only ever actually die if the stop_workers flag gets set.
        try:
          #Make sure we have something to do, then check if that something is to stop.
          self.__worker_go.wait()
          if self.__stop_workers.is_set():
            continue

          item = Get()
          if not item or self.__stop_workers.is_set():
            continue

          self.__do_func(item, self.__print_lock)

          with self.__lock:
            self.__queue_set.remove(item)

        except Exception, e:
          #Immediately kill all other workers. Exceptions are fatal.
          self.__stop_workers.set()
          self.__worker_dead.set()
          self.__worker_go.set()

          #Print the error, or a stack trace if it is an internal error.
          with self.__print_lock:
            try:
              if isinstance(e, BuildError):
                print e
                if print_worker_stacks:
                  traceback.print_exc()
              else:
                traceback.print_exc()
            except:
              pass
        #Let the parent thread know that something happend (be it a job was processed, or we died).
        self.__worker_event.set()

    self.__workers = map(lambda i: threading.Thread(
                        name='Builder-%s'% i,
                        target=Worker
                        ), range(0, num_cores))

  #With semantics to make it simple to run everything inserted to completion or error.
  def __enter__(self):
    for w in self.__workers:
      w.start()

  def __exit__(self, type, value, traceback):
    #Wait until everything is done.
    try:
      #Wait for something to happen before checking if we're working again
      while self.working and not self.worker_dead:
        self.__worker_event.wait()
        self.__worker_event.clear()
      self.__stop_workers.set()
      self.__worker_go.set()
      for w in self.__workers:
        w.join()
    except KeyboardInterrupt:
      self.__stop_workers.set()
      self.__worker_go.set()
      with self.__print_lock:
        print "Killing workers"
      for w in self.__workers:
        w.join(2)
      #This isn't pretty, but python makes us, because there is no way to kill a hung thread.
      os._exit(-1)

  #Used when going up the tree
  def AddRequired(self, item_set):
    """Add items in item_set to the queue if they aren't done, and add them to the needed set. Returns false if nothing is left to be done."""
    with self.__lock:
      self.__task_set |= set(self.__queue_item_func(item) for item in item_set)
      unfinished = set(self.__queue_item_func(item) for item in filter(lambda x: not x.done, item_set))
      if len(unfinished) == 0:
        return False
      unfinished  -= self.__queue_set
      self.__queue_set |= unfinished
      self.__queue += list(unfinished)
      self.__worker_go.set()
      return True

  #Used when going down the tree.
  def AddIfNeeded(self, item_set):
    """Adds items in item_set to the queue if they aren't done, but only if they are in the needed set.  Returns false if nothing is left to be done."""
    with self.__lock:
      item_set = set(self.__queue_item_func(item) for item in filter(lambda item: not item.done, item_set)) & self.__task_set
      if len(item_set) == 0:
        return False
      item_set -= self.__queue_set
      self.__queue_set |= item_set
      self.__queue += list(item_set)
      self.__worker_go.set()
      return True

  @property
  def working(self):
    with self.__lock:
      return len(self.__queue_set) > 0

  @property
  def worker_dead(self):
    return self.__worker_dead.is_set()

class JHMFile(object):
  """Standard JHM configuration file."""

  @staticmethod
  def MergeAndYieldSection(jhm_file_list, section=''):
    """Yield the precedence-merged section of all the given jhm files.

    Args:
      jhm_file_list
        Priority list of jhm_files to merge.
      section
        Section to yield.
    """
    if section is None:
      section = ''

    yield_dict = {}
    rev_prec_file_list = copy.copy(jhm_file_list)
    rev_prec_file_list.reverse()
    for f in rev_prec_file_list:
      yield_dict.update(f.YieldSection(section))

    for k, v in yield_dict.items():
      yield k, v

  def __init__(self, filename):
    #Parse the contents to build the config.
    #section='',key='parent' means that the value is a parent config. Include and parse the given parent config.
    self.__settings_by_section = {}
    section = ''
    self.__settings_by_section[section] = {}
    self.__parent = None
    if filename is not None:
      try:
        for line in open(filename, 'r'):
          line = line.split('#',1)[0].strip()
          if line == '':
            continue;

          if line[0] == '+':
            section = line[1:].strip()
            self.__settings_by_section[section] = {}
          else:
            args = line.split('=',1)
            k = args[0].strip()
            v = args[1].strip() if len(args) > 1 else None
            if section == '' and k == 'parent':
                if self.__parent:
                  raise KeyError('Duplicate entry for "parent" in %s' % filename)
                fname = v
                if not os.path.isabs(fname):
                  fname = os.path.join(os.path.dirname(filename), fname)
                self.__parent = JHMFile(fname)
            self.__settings_by_section[section][k] = (v if v else None)
      except IOError as e:
        if e.errno == 2:
          raise BuildError('config file "%s" does not exist' % filename)
        raise

  def Get(self, key, section='', default=None):
    """Get the given key in the given section, returning default if the key doesn't exist"""
    if section is None:
      section = ''

    if self.__settings_by_section.has_key(section):
      return self.__settings_by_section[section].get(key, self.__parent.Get(key, section, default) if self.__parent else default)
    else:
      return default

  def YieldSection(self, section=''):
    """Yield all k,v pairs in the given section"""
    if section is None:
      section = ''

    if self.__parent:
      yield_dict = dict(self.__parent.YieldSection(section), **self.__settings_by_section.get(section,{}))
    else:
      yield_dict = self.__settings_by_section.get(section, {})

    for k, v in yield_dict.items():
      yield k, v

  @property
  def settings_by_section(self):
    return self.__settings_by_section

class JHMOutFile(JHMFile):
  """A JHM File which can be saved."""

  def __init__(self, filename, read_file):
    self.__filename = filename
    JHMFile.__init__(self, filename if read_file and os.path.exists(filename) else None)

  def Set(self, section, key, value=None):
    if section is None:
      section = ''
    self.settings_by_section.setdefault(section,{})[key] = value


  def Save(self):
    EnsurePathExists(os.path.dirname(self.__filename))
    with open(self.__filename, 'w') as f:
      for k, v in self.settings_by_section.items():
        if k != '':
          print>>f, '+%s' % k
        for k_, v_ in v.items():
          if v_ is not None:
            print>>f, '%s=%s' % (k_, v_)
          else:
            print>>f, k_

def GetArgParser():
  """Get an argument parser for a JHM Env. The argument parser builds the options namespace for the Env."""
  parser = argparse.ArgumentParser(description='Intelligent build tool')
  parser.add_argument('-a', '--arch', dest='arch', action='store', default=platform.machine(),
      help='The architecture (x86, x86_64, etc.) to compile for. Default is :%(default)r.')
  parser.add_argument('--os', dest='system', action='store', default=platform.system(),
      help='The operating system (Linux, Windows, etc.) to compile for. Default is :%(default)r.')
  parser.add_argument('-c', '--config', dest='config', action='store', default='debug',
      help='The configuration to use (debug, release, etc). Default is :%(default)r.')
  parser.add_argument('-v', '--verbose', dest='verbose', action='count', default=0,
      help='Level of verbosity to use when compiling. More repititions means more verbose.')
  parser.add_argument('-I', '--inc-tree', dest='inc_trees', action='append', default=[],
      help='A path to use as a tree for input that isn\'t the primary source tree.')
  parser.add_argument('-f','--force', dest='force', action='store_true', default=False,
      help='Force full recompilation.')
  parser.add_argument('--src-dir', dest='src_dir', action='store', default=None,
      help='The directory which contains the project source.')
  parser.add_argument('--out-dir', dest='out_dir', action='store', default=None,
      help='The directory which contains the project output.')
  parser.add_argument('--root-dir', dest='root_dir', action='store', default=None,
      help='The root directory of the project.')
  parser.add_argument('--project-conf-dir', dest='project_conf_root', action='store', default=None,
      help='The directory where project configuration is located.')
  parser.add_argument('--sys-conf-dir', dest='sys_conf_root', action='store', default=None,
      help='The directory where system configuration is located.')
  parser.add_argument('--user-conf-dir', dest='user_conf_root', action='store', default=None,
      help='The directory where user configuration is located.')
  parser.add_argument('--num-cores', dest='num_cores', action='store', default=None, type=int,
      help='The number of threads to concurrent builders allow. Default is the number of cores in your machine.')
  parser.add_argument('--no-auto-targets', dest='no_auto_targets', action='store_true', default=False,
      help='Do not use targets listed in the jhm file no matter what.')
  parser.add_argument('-x', '--exec', dest='exec_targets', action='store_true', default=False,
      help='Execute all executables after successful build.')
  parser.add_argument('--jhm-debug', dest='jhm_debug', action='store_true', default=False,
      help='Tells JHM to show more debugging information, such as printing python stack on build errors.')
  parser.add_argument('--print-commands', dest='print_all_cmd', action='store_true', default=False,
      help='Print all executed commands.')
  parser.add_argument('--print-build-commands', dest='print_build_cmd', action='store_true', default=False,
      help='Print all build related commands.')
  parser.add_argument('targets', metavar='target', nargs='*',
      help='List of files which should be built.')
  return parser

class Config(object):
  """Loads a level of configuration as once nice tidy bundle."""

  def __init__(self, config_root, base, arch, system):
    self.__conf_root = config_root
    self.__base = base

    #Load config file
    def GetFNameList(base, ext):
      """Simple helper function for building the possible specializations of filenames."""
      #base-system-arch.ext, base-system.ext, base-arch.ext, base.ext
      return ['_'.join([base, arch]) + ext, '_'.join([base, system]) + ext
                , '_'.join([base, arch]) + ext, base + ext]

    conf_fname_list = chain(GetFNameList(base, '.jhm'), GetFNameList('jhm', '.jhm'))
    self.__config = None
    for fname in conf_fname_list:
      config_fullpath = os.path.join(config_root, fname)
      if os.path.isfile(config_fullpath):
        self.__config = JHMFile(config_fullpath)
        break

    def TryLoadList(list_name):
      fname = self.Get(list_name, default=None)
      if fname is not None:
        if not IsAbsPath(fname):
          fname = os.path.join(config_root, fname)

        if os.path.exists(fname):
          return imp.load_source(list_name, fname).__dict__[list_name]
        raise ValueError('Explicit value given in configuration file for where to find %s, but that file does not exist.' % list_name)
      else:
        for fname in GetFNameList(list_name, '.py'):
          fname = os.path.join(config_root, fname)
          if os.path.exists(fname):
            return imp.load_source(list_name, fname).__dict__[list_name]
        return []

    #Load FileKinds, JobKinds
    self.__file_kinds  = TryLoadList('file_kinds')
    self.__job_kinds = TryLoadList('job_kinds')

  @property
  def file_kinds(self):
    return self.__file_kinds

  @property
  def job_kinds(self):
    return self.__job_kinds

  @property
  def base(self):
    return self.__base

  @property
  def conf_root(self):
    return self.__conf_root

  def Get(self, key, section='', default=None):
    """Returns the value for the given key from the config in the given section with the given key. Returns default if it does not exist."""
    return self.__config.Get(key, section, default) if self.__config else default

  def YieldSection(self, section=''):
    """Yields each kv pair in the given section"""
    if self.__config:
      for k, v in self.__config.YieldSection(section):
        yield k, v

#JHM concept validation tests, and inline wrapper.
def Validate(func, value):
  """Raises a ValueError if the value doesn't cause the given function to return true"""
  if func(value):
    return value
  raise ValueError("%r: Invalid value %r" % (func, value))

def IsValidAtom(atom):
  """Test if an atom conforms to the JHM definition of an atom"""
  return re.match("([_a-zA-Z][_\-a-zA-Z0-9]*)?",atom)

def IsValidExtList(ext_list):
  """Makes sure the given extension list conforms to the JHM definition"""
  return isinstance(ext_list, list) and reduce(lambda x, y: x & y, map(lambda e: e != "", ext_list[:-1]), True)

def IsAbsPath(path):
  """Tests if a path is absolute"""
  return os.path.isabs(path)

def IsRelPath(path):
  """Tests if a path is relative"""
  return not IsAbsPath(path)

def IsInstance(type_):
  """Returns a function which can be used to check whether or not  a value is of the given type."""
  def Do(item):
    return isinstance(item, type_)
  return Do

class Tree(object):
  """A directory containing branches/files which may be used by the build environment."""

  def __init__(self, kind, path):
    self.__kind = kind
    self.__path = os.path.normpath(Validate(IsAbsPath, path[:-1] if path[-1] == os.sep else path)) + os.sep

  def Contains(self, path):
    """Return a bool representing if the given path is a file in this tree."""
    if IsAbsPath(path):
      return self.ContainsAbs(path)
    else:
      return self.ContainsRel(path)

  def ContainsAbs(self, path):
    """Returns whether or not the given absolute path is in this tree"""
    return path == self.__path[:-1] or (len(path) >= len(self.__path) and path[:len(self.__path)] == self.__path)

  def ContainsRel(self, path):
    """Returns whether or not the given relative path is in this tree"""
    return os.path.exists(self.GetAbsPath(path))

  def GetAbsPath(self, path):
    """From the given relative path, make an absolute path in this tree"""
    return os.path.join(self.__path, Validate(IsRelPath, path))

  def GetRelPath(self, path):
    """From the given absolute path, make a relative path in this tree"""
    assert self.ContainsAbs(path)
    return path[len(self.__path):]

  @property
  def kind(self):
    return self.__kind

  @property
  def path(self):
    return self.__path

  def __str__(self):
    return self.__kind

  def __repr__(self):
    return "%s:%s" % (self.__kind, self.__path)

  #Possible tree kinds.
  INC = "INC" #Not the primary input tree, but an input tree that may be used.
  OUT = "OUT" #The tree where all output is located.
  SRC = "SRC" #The single primary input tree.

class JobKind(object):
  """A transformation that can be applied to a file to produce other files."""

  def __init__(self, name, in_ext, out_exts):
    self.__name = name
    self.__in_ext = in_ext
    self.__out_exts = set(out_exts) if out_exts is not None else set()

  def GetBaseDepends(self, job):
    """Gets any depends of the job which only need to be found once (such as a file list stored somewhere"""
    return set()

  def GetDepends(self, req_set):
    """Given a req_set, will get the files that must be depended upon."""
    return set()

  def GetInput(self, out_file):
    """Returns the File object that would be required as input to the job to get the given output. May return none if no in_file would be suitable."""
    raise NotImplementedError(self)

  def GetOutput(self, in_file):
    """Returns the frozenset of files that will be produced by this job if run on the given in_file. May return none if in__file couldn't be used by the job."""
    raise NotImplementedError(self)

  def GetRunner(self, job):
    """Returns a function which, when called, will produce the output_set of the given job."""
    raise NotImplementedError(self)

  @property
  def in_ext(self):
    return self.__in_ext

  @property
  def name(self):
    return self.__name

  @property
  def out_exts(self):
    return self.__out_exts

  def __str__(self):
    return self.__name

#TODO: Make it so FileKind can do n-length extension matches.
class FileKind(object):
  """A type of file which can exist in the environment. Used for scanning files for dependencies. Also for figuring out what is a prefix (such as 'lib')"""

  def __init__(self, name, ext, prefix=""):
    self.__name = name
    self.__ext = Validate(IsInstance(str), ext)
    self.__prefix = Validate(IsInstance(str), prefix)

  def GetInclSet(self, f):
    """Scan the file and return a list of JHM File objects which are all the dependency"""
    raise NotImplementedError(self)

  def Split(self, base):
    """With the given file kind, split base into prefix and atom."""
    if len(base) > len(self.__prefix) and base[:len(self.__prefix)] == self.__prefix:
      return self.__prefix, base[len(self.__prefix):]
    return '', base

  @property
  def ext(self):
    """The extension which identifies the file kind"""
    return self.__ext

  @property
  def name(self):
    """A human readable name for the file kind"""
    return self.__name

  @property
  def prefix(self):
    """The optional prefix used by the file kind"""
    return self.__prefix

  def __str__(self):
    return self.__name

class FileKindNoIncl(FileKind):
  """File kind which takes care of the GetInclSet function for you, aka, yours is empty"""
  def __init__(self, name, ext, prefix=""):
    FileKind.__init__(self, name, ext, prefix)

  def GetInclSet(self, f):
    return frozenset()


class Job(object):
  """A JobKind which has been assigned an input or output file."""

  @staticmethod
  def Hash(kind, in_file):
    """Hash of the given job for interning"""
    return hash((kind, in_file))

  def __init__(self, kind, in_file, env, out_only):
    self.__env = env
    self.__hash = Job.Hash(kind, in_file)
    self.__kind = kind
    self.__input = (in_file if not out_only else None)
    self.__done = False
    self.__out_only = out_only

    self.__depend_set = (set([self.__input]) if not out_only else set())
    self.__output_set = set() if self.__input else frozenset([in_file])
    self.__output_dir = os.path.dirname(in_file.env.out_tree.GetAbsPath(in_file.rel_path))

    self.__dep_lock = threading.RLock()
    self.__base_deps = False

    if not out_only:
      self.__input.AddConsumer(self)

  def FinishInit(self):
    if not self.__out_only:
      self.__output_set = Validate(IsInstance(frozenset), self.__kind.GetOutput(self.__input))
    for f in self.__output_set:
      f.SetProducer(self, self.__out_only)

  def AddDepends(self, req_set):
    """Calculate dependencies given the req_set using the JobKind depend getter."""
    self.__DoAddDepends(self.__kind.GetDepends(frozenset(req_set)))

  def __DoAddDepends(self, dep_set):
    with self.__dep_lock:
      new_deps = dep_set - self.__depend_set
      self.__depend_set |= new_deps
    for dep in new_deps:
      dep.AddConsumer(self)
      for f in self.__output_set:
        dep.AddUser(f)

  def Build(self):
    """Attempt to build the given job."""
    assert not self.__done

    #Queue anything we depend on that isn't done yet.
    if not self.__base_deps:
      with self.__dep_lock:
        if not self.__base_deps:
          self.__base_deps = True
          self.__DoAddDepends(self.kind.GetBaseDepends(self))

    with self.__dep_lock:
      if self.__env.Queue(self.__depend_set):
        return False

    #Make the directory to the out file(s), and setup their caches so flags can be added.
    for f in self.output_set:
      EnsurePathExists(os.path.dirname(f.abs_path))
      f.FinishNoCache()

    #Run the job.
    self.__kind.GetRunner(self)()
    #TODO: We need to do something like this, but this overly agressively saves the cache files (Some will be empty, even though they shouldn't b)
    #      Really we should just finish all the files?
    #for f in self.__output_set: #Ensure the caches are commited. Since the files may not be finished, which is when files are guaranteed to have caches finished.
    #  f.jhm_cache_file.Save()

    self.__done = True
    self.__env.QueueIfNeeded(self.__output_set)
    return True

  @property
  def depend_set(self):
    return self.__depend_set

  @property
  def done(self):
    return self.__done

  @done.setter
  def done(self, d):
    assert d is True
    self.__done = d
    return self.__done

  @property
  def env(self):
    return self.__env

  @property
  def input(self):
    return self.__input

  @property
  def kind(self):
    return self.__kind

  @property
  def output(self):
    assert len(self.__output_set) == 1
    return list(self.__output_set)[0]

  @property
  def output_dir(self):
    return self.__output_dir

  @property
  def output_set(self):
    return self.__output_set

  def __str__(self):
    return '"%s":%s' % (self.__kind, list(self.output_set))

  def __hash__(self):
    return self.__hash

class File(object):
  """A path inside a JHM Tree, may or may not need to be built."""

  @staticmethod
  def ToRelPath(branch, base, ext_list):
    """Convert a branch, base, and ext_list to a relative path"""
    return os.path.join(branch, '.'.join(chain([base], ext_list[:-1] if ext_list and ext_list[-1] == '' else ext_list)))

  @staticmethod
  def Hash(rel_path):
    """Hash of the given file for interning"""
    return hash(rel_path)

  def __init__(self, tree, branch, base, ext_list, env):
    self.__env = env
    self.__tree = tree
    self.__branch = Validate(IsRelPath, branch)
    self.__base = base
    self.__ext_list = Validate(IsValidExtList, ext_list)
    self.__rel_path = File.ToRelPath(self.__branch, base, ext_list)
    self.__name = self.__rel_path[len(branch)+1:-len(ext_list[-1])-1]
    self.__abs_path = tree.GetAbsPath(self.__rel_path)
    self.__hash = File.Hash(self.__rel_path)

    #split out prefix/atom from base, and determine kinds.
    self.__kind, self.__prefix, self.__atom = self.__env.GetFileKind(base, ext_list)
    Validate(IsValidAtom, self.__atom)

    #Computed properties/flags.
    self.__cache_filename = env.out_tree.GetAbsPath(self.__rel_path + '.jhm-cache')
    self.__jhm_cache_file = None
    self.__cache_checked = False
    self.__cache_finished = False

    #NOTE: It is a design decision that JHM Files cannot be produced by a job. If you can automatically find the depends/reqs/additional args/etc. you
    #      should be doing so in the FileKind for the file, or JobKinds which use the file.
    self.__jhm_file = None
    self.__jhm_filename = None
    jhm_filename_rel_path = self.__rel_path + '.jhm'
    for t in self.env.YieldEachInTree():
      path = t.GetAbsPath(jhm_filename_rel_path)
      if os.path.exists(path):
        self.__jhm_filename = path
        break;
    self.__stamp = None
    self.__done = False

    self.__req_set = set()
    self.__producer = None
    self.__user_tree_lock = threading.RLock()
    self.__consumer_set = set()
    self.__user_set = set()

    self.__is_available = False
    self.__availability_searched = False

  def AddConsumer(self, consumer):
    """Add a job which depends on this file."""
    with self.__user_tree_lock:
      self.__consumer_set.add(consumer)
      reqs = self.__req_set
    if len(reqs) > 0:
      consumer.AddDepends(reqs)

  def AddReqs(self, reqs):
    """Add a set of files to the set of files this file requires."""
    assert isinstance(reqs, (set, frozenset))
    #TODO: The next line should be uncommented, but it was causing issues.
    #assert not self.__done

    with self.__user_tree_lock:
      new_reqs = reqs - self.__req_set - set([self])
      self.__req_set |= new_reqs
      cons = frozenset(self.__consumer_set)
      users = frozenset(self.__user_set)
      #If we are in the source tree, We define our stamp, to be the newest of our requires stamps.
      #This makes it so that anything that can change this file changes, this file is marked as new.
      if self.__tree == self.__env.src_tree:
        for f in new_reqs:
          if f.stamp > self.stamp:
            self.__stamp = f.stamp
      if len(new_reqs) == 0:
        return
    for j in frozenset(cons):
      j.AddDepends(new_reqs)
    for u in frozenset(users):
      u.AddReqs(new_reqs)
    for f in frozenset(new_reqs):
      f.AddUser(self)

  def AddUser(self, user):
    """Add a file which depends on this file."""
    #Users are files which have this file in their req_set
    with self.__user_tree_lock:
      self.__user_set.add(user)
      reqs = self.__req_set
    if len(reqs) > 0:
      user.AddReqs(reqs)

  def Build(self):
    """Try and build the file."""
    assert not self.__done
    self.jhm_file

    if self.__cache_finished:
      self.__done = True
      self.__env.QueueIfNeeded(self.__user_set | self.__consumer_set)
      return True

    #Check cache file to see if there is anything that needs to be done
    if not (self.__cache_checked or self.__env.force):
      self.__cache_checked = True
      cache_timestamp = GetTimestamp(self.__cache_filename)

      def CheckCache():
        """Open the cache file, check each req timetsamp."""
        self.__jhm_cache_file = JHMOutFile(self.__cache_filename, True)
        new_reqs = set()
        for req, _ in self.__jhm_cache_file.YieldSection('requires'):
          f = req.strip()
          if GetTimestamp(f) >= cache_timestamp or not os.path.exists(f):
            self.__jhm_cache_file = None
            return False
          new_reqs.add(f)
        file_set = set()
        for f in new_reqs:
          file_set.add(self.env.GetFileFromPath(f.strip()))
        for f in file_set:
          f.__CacheFinish()
        self.AddReqs(file_set)
        return True

      if (self.__jhm_filename != None and GetTimestamp(self.__jhm_filename) <= self.stamp) or self.__jhm_filename is None:
        if os.path.isfile(self.__cache_filename) and self.stamp > 0 and cache_timestamp >= self.stamp:
          if CheckCache():
            self.__done = True
            self.__env.QueueIfNeeded(self.__consumer_set | self.__user_set)
            return True
    if not self.__jhm_cache_file:
      self.FinishNoCache()

    if self.__tree.kind == Tree.OUT and not self.__producer:
      raise BuildError('%s must be produced, but no producer was found.' % self)

    if self.__producer and not self.__producer.done:
      self.__env.Queue(set([self.__producer]))
      return False

    self.__Scan()

    if self.__env.Queue(self.__req_set):
      return False

    #Add reqs to jhm_cachefile and save it since it cannot be changed again.
    for f in self.__req_set:
      self.jhm_cache_file.Set('requires', f.abs_path)
    self.jhm_cache_file.Save()

    #TODO: This overly agressively queues items. Really should do a more precise check per item when queuing.
    self.__done = True
    self.__env.QueueIfNeeded(self.__user_set | self.__consumer_set)
    return True

  def FinishNoCache(self):
    if self.__jhm_cache_file is None:
      self.__jhm_cache_file = JHMOutFile(self.__cache_filename, False)

  def __CacheFinish(self):
    #This function is so the file can get itself to a good state if it is finished by another file's cache.
    #TODO: This function has a race condition with regular completion.
    if self.__done or self.__jhm_cache_file:
      return
    self.__cache_finished = True
    if not self.__jhm_cache_file:
      self.__jhm_cache_file = JHMOutFile(self.__cache_filename, True)
    self.AddReqs(set(map(lambda v: self.env.GetFileFromPath(v[0].strip()), self.__jhm_cache_file.YieldSection('requires'))))

  def FindAvailability(self):
    """Test for whether or not this file is available (Exists, or can be created via a transformation chain from a file that exists."""
    if self.__availability_searched:
      return
    self.__availability_searched = True
    if self.__tree.kind in [Tree.SRC, Tree.INC] or self.__producer:
      self.__is_available = True
      return

    def CheckJobKinds(ext):
      for job_kind in self.__env.YieldJobKindsWithOutput(ext):
        in_f = job_kind.GetInput(self)
        #If the job JUST returns true on a call to get input, it means it can make the file, but doesn't require an input file.
        if in_f is True:
          self.__is_available = True
          self.__env.GetJob(job_kind, self, True)
          return True
        elif in_f and in_f.is_available:
          self.__is_available = True
          #NOTE: We don't error on multiple producers because we want precedence to work in the event two jobs could do the same thing, so we do first wins.
          self.__env.GetJob(job_kind, in_f)
          return True
      return False


    assert len(self.__ext_list) > 0
    #Check more exact job kinds.
    CheckJobKinds(self.__ext_list[-1])

  def GetConfig(self, key, section='', result=None):
    """Get a config setting out of this file's jhm file, if it has one."""
    result = self.jhm_file.Get(key, section, result) if self.jhm_file else result
    if self.__jhm_cache_file:
      result = self.__jhm_cache_file.Get(key, section, result)
    return result

  def GetRelatedFileAndTree(self, branch=None, base=None, ext_list=None):
    """Return a file based on this file in whatever tree it should be in naturally."""
    return self.__env.GetFileAndTree(branch if branch else self.__branch, base if base else self.__base, ext_list if ext_list else self.__ext_list)

  def GetRelatedOutFile(self, branch=None, base=None, ext_list=None):
    """Return a file based on this file in the output tree (used when generating job output set."""
    return self.__env.GetFile(self.__env.out_tree, branch if branch else self.__branch, base if base else self.__base
                                , ext_list if ext_list else self.__ext_list
                                )

  def SetProducer(self, job, out_only):
    """Set the job which will produce this file."""
    if len(job.kind.out_exts) > 0 and (not self.ext_list[-1] in job.kind.out_exts):
      raise BuildError('Internal Error: A job kind (%s) produced an output (%s) that it said it would never produce.' % (job.kind, self.ext_list[-1]))
    assert(not self.__producer)
    self.__is_available = True
    self.__producer = job
    if not out_only:
      self.__producer.input.AddUser(self)
      self.AddReqs(set([self.__producer.input]))

  def HasInConfig(self, section, key, needed_value=None):
    """Returns whether the key exists with the given value."""
    #TODO: Could be more efficent about this.
    for k, v in JHMFile.MergeAndYieldSection(list(self.__req_set) + [self], section):
      if k == key:
        if needed_value is None:
          return True
        if needed_value == v:
          return True
    return False


  def YieldParentSection(self, section=''):
    """Yield a section from this files parents config"""
    for k, v in JHMFile.MergeAndYieldSection(self.__env.sys_config_list, section): yield k, v

  def YieldReqSection(self, section=''):
    """Yield a section from this files requires config."""
    for k, v in JHMFile.MergeAndYieldSection(list(self.__req_set), section): yield k, v

  def YieldSection(self, section='', parent=False):
    """Yield a section from this file's config (The JHM File for this file, followed by the system configuration)."""

    conf_list = []
    if self.jhm_file: conf_list.append(self.jhm_file)

    if self.done or self.__jhm_cache_file:
      conf_list.append(self.__jhm_cache_file)

    if parent: conf_list += self.__env.sys_config_list

    for k, v in JHMFile.MergeAndYieldSection(conf_list, section): yield k, v

  def __Scan(self):
    """Scan the file for dependencies."""
    if self.__kind:
      reqs = Validate(IsInstance(frozenset), self.__kind.GetInclSet(self))
      self.AddReqs(reqs)

  @property
  def abs_path(self):
    return self.__abs_path

  @property
  def atom(self):
    return self.__atom

  @property
  def base(self):
    return self.__base

  @property
  def branch(self):
    return self.__branch

  @property
  def consumer_set(self):
    return self.__consumer_set

  @property
  def depend_set(self):
    return self.__depend_set

  @property
  def directory(self):
    return os.path.join(self.__tree.path, self.__branch)

  @property
  def done(self):
    return self.__done

  @done.setter
  def done(self, d):
    assert d is True
    self.__done = d
    return self.__done

  @property
  def env(self):
    return self.__env

  @property
  def ext_list(self):
    return self.__ext_list

  @property
  def is_available(self):
    return self.__is_available

  @property
  def jhm_file(self):
    if self.__jhm_file is None:
      self.__jhm_file = False
      if self.__jhm_filename is not None:
        self.__jhm_file = JHMFile(self.__jhm_filename)
        self.AddReqs(set(map(lambda k: self.env.GetFileFromPath(k[0]), self.__jhm_file.YieldSection('requires'))))
    return self.__jhm_file

  @property
  def jhm_cache_file(self):
    #The cache file must always be set before anyone uses it. Logic for setting is in the cache checking code.
    assert self.__jhm_cache_file
    return self.__jhm_cache_file

  @property
  def kind(self):
    return self.__kind

  @property
  def name(self):
    return self.__name

  @property
  def prefix(self):
    return self.__prefix

  @property
  def producer(self):
    return self.__producer

  @property
  def rel_path(self):
    return self.__rel_path

  @property
  def req_set(self):
    return self.__req_set

  @property
  def stamp(self):
    if self.__stamp is None:
      self.__stamp = GetTimestamp(self.__abs_path)
    return self.__stamp

  @property
  def tree(self):
    return self.__tree

  def __hash__(self):
    return self.__hash

  def __str__(self):
    return '%s:%s' % (self.__tree, self.__rel_path)

  def __repr__(self):
    return str(self)

def TryFindRoot(dirname):
  path = os.getcwd()
  while path:
    fullpath = os.path.join(path, dirname)
    if os.path.exists(fullpath):
      return path
    if path[-1] == os.sep:
      path = path[:-1]
    path = os.path.dirname(path)
  return False

class Env(object):
  """A build environment, containing trees and files, files which are interconnected by jobs, dependencies, and requires."""

  def __init__(self, options):
    #Options is a namespace (most likely built by argparse), containing JHM options.
    self.__options = options

    #Find the build environment root, either use provided or do a directory search.
    self.__root = os.path.abspath(options.root_dir) if options.root_dir else TryFindRoot('.jhm')
    if not self.__root:
      raise BuildError("Unable to find buld root. Indicate the build root by making a jhm config dir ('.jhm'), or specifying --root-dir")

    #Load the three different levels of configuration (project, user, and sys)
    self.__config = {}
    def GetConfig(main_path, backup_path):
      return Config(os.path.abspath(main_path) if main_path else backup_path, options.config, options.arch, options.system)
    self.__config['project'] = GetConfig(options.project_conf_root, os.path.join(self.__root, '.jhm'))
    self.__config['user'] = GetConfig(options.user_conf_root, os.path.expanduser('~/.jhm'))
    self.__config['sys'] = GetConfig(options.sys_conf_root, '/etc/jhm')

    def ProjectAbs(path):
      if not os.path.isabs(path):
        path =  os.path.join(self.__root, path)
      return os.path.normpath(path)
    #Setup the environment src/out trees.
    self.__src_tree = Tree(Tree.SRC, ProjectAbs(options.src_dir if options.src_dir else self.__config['project'].Get('src_dir', default='src')))
    self.__incl_tree = list(map(lambda path: Tree(Tree.INC, ProjectAbs(path)), chain((path for path, _ in self.YieldConfigSection('incl-tree')), options.inc_trees)))
    #The default out directory gets longer/shorter based on how many args are non-default.
    out_sub_dir = options.config
    if options.system != platform.system():
      out_sub_dir += '-' + options.system
    if options.arch != platform.machine():
      out_sub_dir +=  '-' + options.arch
    self.__out_tree = Tree(Tree.OUT, ProjectAbs(options.out_dir if options.out_dir else os.path.join(self.__config['project'].Get('out_dir', default='out'),out_sub_dir)))

    #Setup file kinds for easy access.
    self.__file_kinds = list(chain(self.__config['project'].file_kinds, self.__config['user'].file_kinds, self.__config['sys'].file_kinds))
    self.__file_kinds_by_ext = {}
    for file_kind in self.__file_kinds:
      self.__file_kinds_by_ext[file_kind.ext] = self.__file_kinds_by_ext.get(file_kind.ext, list()) + [file_kind]

    #Setup job kinds for easy access.
    self.__job_kinds = list(chain(self.__config['project'].job_kinds, self.__config['user'].job_kinds, self.__config['sys'].file_kinds))
    self.__job_kinds_by_in_ext = {}
    self.__job_kinds_by_out_ext = {}
    self.__job_kinds_magic = []
    for job_kind in self.__job_kinds:
      self.__job_kinds_by_in_ext[job_kind.in_ext] = self.__job_kinds_by_in_ext.get(job_kind.in_ext, list()) +[job_kind]
      for ext in job_kind.out_exts:
        self.__job_kinds_by_out_ext[ext] = self.__job_kinds_by_out_ext.get(ext, list()) + [job_kind]
      if job_kind.in_ext is None and not job_kind.out_exts:
        self.__job_kinds_magic.append(job_kind)

    #Load in the targets.
    #TODO #HACK: We do '1:' here to slice off the program name. This should really be done by argparse.
    self.__targets = set(options.targets[1:] if options.targets[1:] else (filter(lambda x: x, map(lambda s: s.strip(), [] if options.no_auto_targets else list(k for k, v in self.YieldConfigSection('targets'))))))
    self.__file_dict = {}
    self.__job_dict = {}
    self.__file_lock = threading.RLock()
    self.__job_lock = threading.RLock()

    #Setup the processing queue.
    self.__num_cores = options.num_cores if options.num_cores is not None else int(self.GetSysConfig('num_cores',default=multiprocessing.cpu_count()))
    if self.__num_cores <= 0:
      raise ValueError('num_cores argument must be greater than zero')
    self.__verbose = options.verbose if options.verbose is not None else int(self.GetConfig('num_cores', default=0))

    def QueueWorker(item, print_lock):
      """Function which processes itmes in the queue one at a time."""

      if self.verbose > 0:
        with print_lock:
          print ('TRY FINISH %s' % self.__file_dict[item[1]] if item[0] == 'F' else 'TRY BUILD %s' % self.__job_dict[item[1]])

      if item[0] == 'F':
        i = self.__file_dict[item[1]]
      elif item[0] == 'J':
        i = self.__job_dict[item[1]]
      else:
        #Serious error. Completely invalid type entered.
        assert(False)

      result = i.Build()
      if result:
        i.done = True

      if self.verbose > 0:
        with print_lock:
          if result:
            print('FINISHED: %s' % i if item[0] == 'F' else 'BUILT %s' % i)
      return result

    def ItemToHashable(item):
      if isinstance(item, File):
        return ('F', hash(item))
      elif isinstance(item, Job):
        return ('J', hash(item))
      else:
        #Serious error. We only build files and jobs...
        assert(False)

    self.__queue = MultithreadProcessingQueue(QueueWorker, ItemToHashable, self.__num_cores, options.jhm_debug)


    if self.__verbose > 0:
      print 'FILE KINDS: %s' % ', '.join(repr(str(f)) for f in self.__file_kinds)
      print 'JOB KINDS: %s' % ', '.join(repr(str(f)) for f in self.__job_kinds)
      print 'TREES: %s' % ', '.join(repr(f) for f in self.YieldEachTree())

    if not self.__file_kinds:
      raise BuildError('No file kinds were found')
    if not self.__job_kinds:
      raise BuildError('No job kinds were found')

    #Add everything we want to finish to the processing queue.
    self.__target_file_set = set()
    for path in self.__targets:
      self.AddTargetByPath(path)

  def AddTargetByPath(self, path):
    """Adds the given path to the JHM build set."""
    #If starts with a '/' then it is relative to the project root. No one uses absolute absolute paths.
    #Else: Since we aren't absolute, we're relative to cwd.

    if IsAbsPath(path):
      f = self.GetFileFromPath(path)
    else:
      abs_path = os.path.abspath(path)
      tree = self.TryFindTree(abs_path)
      f = self.GetFileFromPath(tree.GetRelPath(abs_path) if tree and tree.ContainsAbs(abs_path) else path)
    self.AddTarget(f)

  def AddTarget(self, f):
    """Adds the given JHM File to the build set."""
    assert isinstance(f, File)
    self.__target_file_set.add(f)
    return self.Queue(set([f]))

  def AddTargets(self, file_set):
    """"Add a set of targets to the build set."""
    assert isinstance(file_set, (set, frozenset))
    self.__target_file_set |= file_set
    return self.Queue(file_set)

  def Build(self):
    """Build all files that need building in the target set (self.__targets). Raises errors if one or more can't be built."""

    #Make sure we have something to do, or the user has called us in error.
    if not self.__target_file_set:
      raise BuildError("No files were specied to be built")

    if self.verbose > 0:
      print "TARGET SET:" + (' '.join(str(f) for f in self.__target_file_set))

    #Run the job queue and wait for it to coalesce
    with self.__queue:
      pass

    #If one of the workers died, then we have a build error that not everything was finished.
    if self.__queue.worker_dead:
      raise BuildError('One (or more) jobs exited with an error code.')

    leftovers = filter(lambda x: not x.done, self.__target_file_set)
    if leftovers:
      raise BuildError('LEFTOVERS:\n%s\nCRITICAL JHM BUILD FAILURE. EXITED WITHOUT FINISHING EVERYTHING. Note if you just re-run jhm, everything will likely work.' % leftovers)

    if self.options.exec_targets:
      self.Exec()

  def Exec(self):
    """Run all executable targets."""
    for f in self.__target_file_set:
      if os.access(f.abs_path, os.X_OK):
        ret_code = subprocess.Popen([f.abs_path]).wait()
        if ret_code != 0:
          raise BuildError('Program returned %s' % ret_code)

    return 0


  def RunCmd(self, args, returned_output=False, print_command=False):
    return RunCmd(args, returned_output, print_command | self.options.print_all_cmd)

  def RunBuildCmd(self, args, returned_output=False):
    return self.RunCmd(args, returned_output, self.options.print_build_cmd)


  def TryFindTree(self, path):
    for t in self.YieldEachInTree():
      if t.Contains(path):
        return t
    if self.__out_tree.Contains(path) or not os.path.isabs(path):
      return self.__out_tree


  def FindTree(self, path):
    """Find the tree containing the given rel_path, if none have it, then the file must be produced, so out_tree"""
    t = self.TryFindTree(path)
    if t is None:
      raise BuildError('No tree contains the path %s' % path)
    return t

  def GetConfig(self, key, section='', default=None):
    """Returns the value for the given key from the config in the given section with the given key. Returns default if it does not exist."""
    v = self.__config['project'].Get(key, section, None)
    if v is None:
      v = self.__config['user'].Get(key, section, None)
    if v is None:
      v = self.__config['sys'].Get(key, section, default)
    return v

  def GetFile(self, tree, branch, base, ext_list):
    """Given a tree, branch, base, and ext_list, get the File object representing that file. If we can't, we have a build problem."""
    hash_ = File.Hash(File.ToRelPath(branch, base, ext_list))
    f = self.__file_dict.get(hash_, None)
    if f:
      #The system requested the same file in the build from a different tree. This is illegal. A file may only exist in one tree.
      assert(f.tree == tree)
      return f

    #Lock on inserts for thread safety.
    with self.__file_lock:
      f = self.__file_dict.get(hash_, None)
      if f:
        assert(f.tree == tree)
        return f
      f = File(tree, branch, base, ext_list, self)
      self.__file_dict[hash_] = f

    f.FindAvailability() #TODO: I don't think this is necessary anymore...
    return f

  def GetFileAndTree(self, branch, base, ext_list):
    """Returns the File class. Inserts if not exists. Finds the proper tree in which the file should live."""
    rel = File.ToRelPath(branch, base, ext_list)
    hash_ = File.Hash(rel)
    if self.__file_dict.has_key(hash_):
      return self.__file_dict[hash_]

    tree = None
    for t in self.YieldEachInTree():
      if t.ContainsRel(rel):
        #NOTE: These are in order of precedence, so existing in multiple trees doesn't matter.
        tree = t
        break
    if not tree:
      tree = self.__out_tree

    #Lock on inserts for thread safety.
    with self.__file_lock:
      if self.__file_dict.has_key(hash_):
        return self.__file_dict[hash_]
      f = File(tree, branch, base, ext_list, self)
      self.__file_dict[hash_] = f
      f.FindAvailability()
    return f

  def GetFileFromPath(self, path):
    """Returns the canonical file object for the path, if any."""
    #Step 1: Find the tree.
    rel_path = None
    tree = None
    if IsAbsPath(path):
      ath = path[1:]
      for t in self.YieldEachTree():
        if t.ContainsAbs(path):
          rel_path = t.GetRelPath(path)
          tree = t
          break
        if os.path.exists(t.GetAbsPath(ath)):
          rel_path = ath
          tree = t
          break
      if tree is None:
        tree = self.__out_tree
        rel_path = ath
    else:
      rel_path = path
      tree = self.FindTree(rel_path)
    #Step 2: With the remaining rel_path, split it into pieces (branch, base, ext_list)
    #Test if either of two are available, Construct two, first one with an no extra empty piece, then one with a final extension as empty. If neither are
    #available, Then intern the one without the empty piece last.
    branch, base, ext_list = self.SplitRelPath(rel_path)
    hash_ = File.Hash(rel_path)
    f = self.__file_dict.get(hash_, None)
    if f:
      return f
    with self.__file_lock:
      f = self.__file_dict.get(hash_, None)
      if f:
        return f
      f = File(tree, branch, base, ext_list, self)
      self.__file_dict[hash_] = f
      f.FindAvailability()
      if f.is_available:
        return f
      orig_f = f

      #Check to see if executable version of file is available.
      if len(ext_list) > 0 and ext_list[-1] != '':
        f = File(tree, branch, base, ext_list + [''], self)
        self.__file_dict[hash_] = f
        f.FindAvailability()
        if not f.is_available:
          f = orig_f
          self.__file_dict[hash_] = f
    return f

  def GetFileKind(self, base, ext_list):
    """Find the best mathcing file_kind for the file. One with the longest prefix on match wins."""
    assert len(ext_list) > 0
    file_kind = None
    prefix = ''
    atom = base

    for tmp_fk in self.GetFileKindsWithExt(ext_list[-1]):
      tmp_prefix, tmp_atom = tmp_fk.Split(base)
      if not file_kind or (file_kind and len(tmp_prefix) > len(prefix)):
        file_kind = tmp_fk
        prefix  = tmp_prefix
        atom = tmp_atom

    return file_kind, prefix, atom

  def GetFileKindsWithExt(self, ext):
    """Return the list of file kinds which could possibly have the given final extension."""
    return self.__file_kinds_by_ext.get(ext, [])

  def GetJob(self, kind, in_file, out_only=False):
    """Gets job from job dict or creates it.

    If out_only is true, then the job doesn't take input, but it just makes a specific output."""
    hash_ = Job.Hash(kind, in_file)
    j = self.__job_dict.get(hash_, None)
    if j:
      return j

    with self.__job_lock:
      if self.__job_dict.has_key(hash_):
        return self.__job_dict[hash_]
      j = Job(kind, in_file, self, out_only)
      self.__job_dict[hash_] = j
      j.FinishInit()
    return j

  def GetSysConfig(self, key, section='', default=None):
    """Get an item from the system config only, not project specific config."""
    v = self.__config['user'].Get(key, section, None)
    if v is None:
      v = self.__config['sys'].Get(key, section, default)
    return v

  def Queue(self, item_set):
    return self.__queue.AddRequired(item_set)

  def QueueIfNeeded(self, item_set):
    return self.__queue.AddIfNeeded(item_set)

  def SplitRelPath(self, rel_path):
    """Split a relative path into a branch, base, and ext_list"""
    branch, rem = os.path.split(rel_path)

    #Handle files that start with a '.' gracefully.
    split = rem.split('.', 1)
    base = '' if rem[0] == '.' else split[0]

    ext_list = Validate(IsValidExtList, split[1].split('.')) if len(split) > 1 else ['']

    return (branch, base, ext_list)

  def YieldConfigSection(self, section=''):
    """Yields each k, v pair in the given section for all configurations."""

    for k, v in JHMFile.MergeAndYieldSection([self.__config['project'], self.__config['user'], self.__config['sys']], section):
      yield k, v

  def YieldEachInTree(self):
    """Yields each input tree in the env, in order of precedence."""
    yield self.__src_tree
    for tree in self.__incl_tree:
      yield tree

  def YieldEachTree(self):
    """Yields each tree in the env, in order of precedence."""
    yield self.__src_tree
    for tree in self.__incl_tree:
      yield tree
    yield self.__out_tree

  def YieldJobKindsWithInput(self, in_ext):
    """Yield each job kind which can use files with the given extension as input."""
    for job_kind in self.__job_kinds_by_in_ext.get(in_ext, set()):
      yield job_kind

  def YieldJobKindsWithOutput(self, out_ext):
    """Yield each job kind which can output files with the given extension."""
    for job_kind in self.__job_kinds_by_out_ext.get(out_ext, set()):
      yield job_kind
    for job_kind in self.__job_kinds_magic:
      yield job_kind

  @property
  def arch(self):
    """The machine architecture (x86, x86_64, etc.)"""
    return self.__options.arch

  @property
  def config(self):
    """The build configuration to use (release, debug, etc.)"""
    return self.__options.config

  @property
  def force(self):
    """Whether or not all jobs should be run no matter what."""
    return self.__options.force

  @property
  def incl_trees(self):
    """Trees, in order of precednce, which JHM can use files in."""
    return self.__incl_trees

  @property
  def options(self):
    """A namespace containing options which Env was constructed with (Usually from argparse)."""
    return self.__options

  @property
  def out_tree(self):
    """The tree to which all output should be written"""
    return self.__out_tree

  @property
  def root(self):
    """The root directory of the JHM Environment."""
    return self.__root

  @property
  def src_tree(self):
    """The primary input tree."""
    return self.__src_tree

  @property
  def sys_config_list(self):
    """List of JHMFiles in system precedence order."""
    return [self.__config['project'], self.__config['user'], self.__config['sys']]

  @property
  def system(self):
    """The operating system the build is being run for."""
    return self.__system

  @property
  def targets(self):
    """Return the list of filenames that should be built"""
    return self.__targets

  @property
  def target_file_set(self):
    """Returns the list of File objects that should be built"""
    return frozenset(self.__target_file_set)

  @property
  def user_config_list(self):
    """List of JHMFiles in user precedence order."""
    return [self.__config['project'], self.__config['user']]

  @property
  def verbose(self):
    """The verbosity with which the build should be executed."""
    return self.__verbose
