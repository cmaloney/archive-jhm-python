# This file is licensed under the terms of the Apache License, Version 2.0
# Please see the file COPYING for the full text of this license
#
# Copyright 2010-2011 Tagged

import os.path, re, tempfile

from jhm import BuildError, FileKind, FileKindNoIncl

#NOTE: Haskell Root is f.env.src_tree.GetAbsPath('hs3/src')
HASKELL_OFFSET='hs3/src'

def GetConfigSectionAsArgs(f, section):
  args = []

  def AddArg(p):
    k, v = p
    if v is not None:
      args.append(k + '=' + v)
    else:
      args.append(k)

  map(AddArg, f.YieldParentSection(section))
  map(AddArg, f.YieldReqSection(section))
  map(AddArg, f.YieldSection(section))
  return args

def BuildGccEnv(cpp, item):
  cmd_name = ('g++' if cpp else 'gcc')
  args = [cmd_name] + GetConfigSectionAsArgs(item, cmd_name + '-args')

  #Add trees
  for t in item.env.YieldEachTree():
    args.append('-I' + t.path)

  return args

def BuildHaskellEnv(f):
  return ['ghc', '-outputdir', f.env.out_tree.GetAbsPath(HASKELL_OFFSET), '-i%s' % f.env.src_tree.GetAbsPath(HASKELL_OFFSET),'-i%s' % f.env.out_tree.GetAbsPath(HASKELL_OFFSET)] + GetConfigSectionAsArgs(f,'ghc-args')

class CSource(FileKind):
  def __init__(self, is_cpp, ext):
    FileKind.__init__(self, 'C++' if is_cpp else 'C' + ' source', ext)
    self.__is_cpp = is_cpp
    self.__ext = ext

  def GetInclSet(self, f):
    def YieldEach():
      args = BuildGccEnv(self.__is_cpp, f)
      args += ['-M', '-MG', f.abs_path]

      (stdout, stderr) = f.env.RunCmd(args,True)
      for path in ' '.join(stdout.split(':', 1)[1].split('\\')).split():
        yield f.env.GetFileFromPath(os.path.normpath(path.strip()))
    return frozenset(YieldEach())

class Executable(FileKind):
  def __init__(self):
    FileKind.__init__(self, 'executable', '')

  def GetInclSet(self, f):
    return frozenset()

class Haskell(FileKind):
  def __init__(self):
    FileKind.__init__(self, 'haskell source', 'hs')

  def GetInclSet(self, f):
    incl_set = set()
    handle, tmp_fname = tempfile.mkstemp()
    os.close(handle)
    args = BuildHaskellEnv(f) + ['-M', '-v2', f.abs_path,'-dep-makefile',tmp_fname]
    (stdout, stderr) = f.env.RunCmd(args, True)
    os.remove(tmp_fname)
    hs_deps = set()
    for m in re.finditer(r'ms_mod = (.*)', stderr):
      dep = m.group(1)
      if dep.startswith('main:Main'):
        f.jhm_cache_file.Set('haskell', 'main', 'true')

    for m in re.finditer(r'import ([a-zA-Z0-9._\-]+)', stderr):
      dep = m.group(1)
      if dep == 'qualified':
        pass
      hs_deps.add(dep)
    for m in re.finditer(r'import qualified ([a-zA-Z0-9._\-]+) as [a-zA-Z0-9._\-]+', stderr):
      hs_deps.add(m.group(1))
    for m in re.finditer(r'import "([a-zA-Z0-9_\-]+)" ([a-zA-Z0-9._\-]+)', stderr):
      hs_deps.add(m.group(2))
      f.jhm_cache_file.Set('haskell-lib-deps', m.group(1))
    #Convert dep to filename, check if it's in Database.Stig
    for dep in hs_deps:
      if dep.find('Database.Stig') == 0:
        branch, base = '/'.join(dep.split('.')).rsplit('/',1)
        incl_set.add(f.GetRelatedFileAndTree(branch=os.path.join(HASKELL_OFFSET, branch),base=base, ext_list=['hs']))
        incl_set.add(f.GetRelatedFileAndTree(branch=os.path.join(HASKELL_OFFSET, branch),base=base, ext_list=['hi']))
      else:
        f.jhm_cache_file.Set('haskell-deps', dep)
    return frozenset(incl_set)

class Header(FileKind):
  def __init__(self):
    FileKind.__init__(self, 'C/C++ header', 'h')

  def GetInclSet(self, f):
    return frozenset()

class Object(FileKind):
  def __init__(self, is_pic):
    FileKind.__init__(self, 'object' + ' PIC' if is_pic else '', 'o_pic' if is_pic else 'o')

  def GetInclSet(self, f):
    return frozenset()

#TODO: Many of these non incl ones actually do have includes...
file_kinds = [FileKindNoIncl('static library', 'a', 'lib'), FileKindNoIncl('shared library', 'so', 'lib')
             ,FileKindNoIncl('python source', 'py'), FileKindNoIncl('php source', 'php'), FileKindNoIncl('java source', 'java')
             ,FileKindNoIncl('yacc source', 'y'), FileKindNoIncl('yacc C++ source', 'yy')
             ,FileKindNoIncl('lex source', 'l'), FileKindNoIncl('lex C++ source', 'll')
             ,FileKindNoIncl('PNG image', 'png'), FileKindNoIncl('SVG image', 'svg')
             ,FileKindNoIncl('Graphviz dot file', 'dot'), FileKindNoIncl('Grpaphviz fdp file', 'fdp')
             ,FileKindNoIncl('swig source', 'i')
             ,CSource(False,'c'), CSource(True, 'cc'), CSource(True, 'cpp'), Header()
             ,Object(False), Object(True)
             ,Executable()
             ,Haskell()
             ]
