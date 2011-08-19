# This file is licensed under the terms of the Apache License, Version 2.0
# Please see the file COPYING for the full text of this license
#
# Copyright 2010-2011 Tagged

from itertools import chain
import os.path

from jhm import BuildError, JobKind
from file_kinds import BuildGccEnv, BuildHaskellEnv, GetConfigSectionAsArgs
import haskell

haskell_deps = haskell.Deps()

def SetGnuArg(jhm_cache_file, arg):
  jhm_cache_file.Set('g++-args',arg)
  jhm_cache_file.Set('gcc-args',arg)


class Closure(JobKind):
  def __init__(self):
    JobKind.__init__(self, 'Closure generator', None, ['h'])

  def GetInput(self, out_file):
    #Check to see if in closure tree.
    if out_file.branch == 'closure':
      return True
    return None

  def GetRunner(self, job):
    args = ['closure.py',job.output.abs_path]
    def Go():
      job.env.RunBuildCmd(args)
    return Go

class CompileC(JobKind):
  def __init__(self, ext, is_cpp, is_pic):
    self.__ext = ext
    self.__is_cpp = is_cpp
    self.__is_pic = is_pic
    self.__out_ext = 'o_pic' if is_pic else 'o'
    JobKind.__init__(self, 'compile C' + ('++' if is_cpp else '') + (' PIC' if is_pic else ''), ext, [self.__out_ext])

  #Compilation has no actual depends. (just the input files have reqs from scanning).
  def GetDepends(self, req_set):
    return set()

  def GetInput(self, out_file):
    return out_file.GetRelatedFileAndTree(ext_list=out_file.ext_list[:-1] + [self.__ext])

  def GetOutput(self, in_file):
    return frozenset([in_file.GetRelatedOutFile(ext_list=in_file.ext_list[:-1] + [self.__out_ext])])

  def GetRunner(self, j):
    args = BuildGccEnv(self.__is_cpp, j.input)

    #Say this is input.
    args += ['-c', j.input.abs_path]
    if self.__is_pic:
      args.append('-fPIC')

    #Set output location
    args.append('-o' + j.env.out_tree.GetAbsPath(list(j.output_set)[0].rel_path))
    args.append('-DSRC_ROOT="%s"' % j.env.src_tree.path)

    def Go():
      j.env.RunBuildCmd(args)
    return Go

class GenerateSwig(JobKind):

  def __init__(self, wrapper, cpp):
    self.__wrapper = wrapper
    self.__cpp = cpp
    self.__out_sub_ext = wrapper if wrapper != 'python' else 'py'
    self.__out_ext = 'cc' if cpp else 'c'
    JobKind.__init__(self, 'generate swig %s C%s' % (wrapper, '++' if cpp else ''), 'i', [self.__out_ext,'py','php','java','h'])

  def GetInput(self, out_f):
    #TODO: Check for the php_ prefix file...
    if out_f.ext_list[-1] == self.__out_sub_ext:
      return out_f.GetRelatedFileAndTree(ext_list=out_f.ext_list[:-1] + ['i'])
    elif len(out_f.ext_list) > 1 and self.__out_sub_ext == out_f.ext_list[-2] and out_f.ext_list[-1] == self.__out_ext:
      return out_f.GetRelatedFileAndTree(ext_list=out_f.ext_list[:-2] + ['i'])

  def GetOutput(self, in_f):
    out_file_set = set([
         in_f.GetRelatedOutFile(ext_list=in_f.ext_list[:-1] + [self.__out_sub_ext, self.__out_ext])
        ,in_f.GetRelatedOutFile(ext_list=in_f.ext_list[:-1] + [self.__out_sub_ext])
      ])

    if self.__wrapper == 'php':
      #TODO: Check to make sure the atom mangling here is the 'proper' way to do it.
      out_file_set.add(in_f.GetRelatedOutFile(base='php_'+in_f.atom, ext_list=in_f.ext_list[:-1] + ['h']))
    return frozenset(out_file_set)

  #TODO: This should actually do something...
  def GetDepends(self, req_set):
    return set()

  def GetRunner(self, j):
    args = ['swig-wrapper.py', '-a' + j.input.atom, '-l' + self.__wrapper, '-i' + j.input.abs_path, '-o' + j.output_dir]
    for tree in j.env.YieldEachTree():
      args.append('--include=' + tree.path)
    if self.__cpp:
      args.append('--cplusplus')

    def Go():
      for f in j.output_set:
        SetGnuArg(f.jhm_cache_file, '-Wno-old-style-cast')
        SetGnuArg(f.jhm_cache_file, '-Wno-unused-but-set-variable')
        if self.__wrapper == 'php':
          #PHP is just too ugh to deal with.
          SetGnuArg(f.jhm_cache_file, '-w')
      j.env.RunBuildCmd(args)
    return Go

class Haskell(JobKind):
  def __init__(self, pic):
    self.__pic = pic
    JobKind.__init__(self, 'compile haskell', 'hs', ['hi_pic','o_pic'] if pic else ['hi', 'o'])

  def GetInput(self, out_f):
    return out_f.GetRelatedFileAndTree(ext_list=out_f.ext_list[:-1] + ['hs'])

  def GetDepends(self, req_set):
    dep_set = set()
    for f in req_set:
      if f.ext_list[-1] == 'hs':
        dep_set.add(f.GetRelatedFileAndTree(ext_list=f.ext_list[:-1] + (['hi_pic'] if self.__pic else ['hi'])))
    return dep_set

  def GetOutput(self, in_f):
    if self.__pic:
      return frozenset([
        in_f.GetRelatedOutFile(ext_list=in_f.ext_list[:-1] + ['o_pic']),
        in_f.GetRelatedOutFile(ext_list=in_f.ext_list[:-1] + ['hi_pic']),
        ])
    else:
      return frozenset([
        in_f.GetRelatedOutFile(ext_list=in_f.ext_list[:-1] + ['hi']),
        in_f.GetRelatedOutFile(ext_list=in_f.ext_list[:-1] + ['o']),
        ])

  def GetRunner(self, j):
    obj_out = filter(lambda f: f.ext_list[-1] == ('o_pic' if self.__pic else 'o'), j.output_set)[0]
    args = BuildHaskellEnv(j.input) + ['-c',j.input.abs_path,'-fforce-recomp','-o', obj_out.abs_path]
    if self.__pic:
      args += ['-fPIC','-hisuf','hi_pic','-osuf','o_pic','-dynamic']
    def Go():
      for f in j.output_set:
        if f.ext_list[-1] == 'o_pic':
          f.jhm_cache_file.Set('link-args','-Bsymbolic')
      j.env.RunBuildCmd(args)
    return Go

#TODO: Come up with a non-hand-coded way to do this...
link_map = {
  'boost/regex.hpp': '-lboost_regex',
  'cairo.h': '-lcairo',
  'cairo-xcb.h': '-lxcb-render',
  'GL/gl.h': '-lGL',
  'GL/glx.h': '-lGL',
  'GL/glu.h': '-lGLU',
  'GL/glew.h': '-lGLEW',
  'GL/glxew.h': '-lGLEW',
  'HsFFi':'-lHSffi',
  'dlfcn.h':'-ldl',
  'pango/pangocairo.h': ['-lpangocairo-1.0', '-lpango-1.0','-pthread','-lgobject-2.0','-lgmodule-2.0','-lgthread-2.0','-lrt','-lglib-2.0'],
  'pthread.h': '-lpthread',
  'SOIL.h': ['-lSOIL', '-lGL', '-lm'],
  'time.h': '-lrt',
  'xcb/xcb.h': '-lxcb',
}

class Link(JobKind):
  def __init__(self, is_pic=False, name='link', out_ext=['']):
    self.__in_ext = 'o_pic' if is_pic else 'o'
    self.__out_ext = out_ext[0]
    JobKind.__init__(self, name + (' PIC' if is_pic else ''), self.__in_ext, out_ext)

  def GetDepends(self, req_set):
    #TODO: Add haskell dependencies.
    #TODO: Simplify this.?
    dep_set = set()
    to_check = list(req_set)
    full_set = set(req_set)
    while to_check:
      f = to_check.pop()
      to_check += list(f.req_set - full_set)
      full_set |= f.req_set
      dep = f.GetRelatedFileAndTree(ext_list=f.ext_list[:-1] + [self.__in_ext])
      if dep and dep.is_available:
        to_check += list((dep_set | set([dep]) | dep.req_set) - full_set)
        full_set |= dep_set | set([dep]) | dep.req_set
        dep_set.add(dep)
    return dep_set

  def GetInput(self, out_file):
    return out_file.GetRelatedFileAndTree(ext_list=out_file.ext_list[:-1] + [self.__in_ext])

  def GetOutput(self, in_file):
    return frozenset([in_file.GetRelatedFileAndTree(ext_list=in_file.ext_list[:-1] + [self.__out_ext])])

  def GetRunnerArgs(self, j):
    args = ['g++']
    GetConfigSectionAsArgs(j.input, 'ld-args')
    args += ['-o' + j.output.abs_path]

    use_hs_main = False

    #Collect haskell deps from tree.
    for f in j.depend_set:
      args.append(f.abs_path)

    dep_set = set()
    to_check = list(j.depend_set)
    to_check.append(j.input)
    full_set = j.depend_set
    while to_check:
      f = to_check.pop()
      to_check += list(f.req_set - full_set)
      full_set |= f.req_set
      dep_set |= set(map(lambda l: l[0], chain(f.YieldParentSection('haskell-deps'), f.YieldReqSection('haskell-deps'), f.YieldSection('haskell-deps'))))
      use_hs_main |= f.HasInConfig('haskell', 'main')

    if use_hs_main:
      args.append('-lHSrtsmain')

    if self.__out_ext in ['','a']:
      new_args = haskell_deps.GetStaticLinkArgs(dep_set)
      args += new_args
    elif self.__out_ext in ['so']:
      args += haskell_deps.GetDynamicLinkArgs(dep_set)

    #Lookup dependencies which need to be linked against.
    for dep in set(chain(j.input.req_set, reduce(lambda x, y: x | y, map(lambda d: d.req_set, j.depend_set),set()))):
      link_lib = link_map.get(dep.rel_path,None)
      if link_lib is not None:
        if isinstance(link_lib, str):
          args.append(link_lib)
        else:
          assert isinstance(link_lib, list)
          args += link_lib


    args += GetConfigSectionAsArgs(j.input, 'link-args')
    return args

  def GetRunner(self, j):
    #TODO: Don't force g++
    args = self.GetRunnerArgs(j) + GetConfigSectionAsArgs(j.input, 'link-args-executable')

    def Go():
      j.env.RunBuildCmd(args)
    return Go

class Archive(Link):
  def __init__(self):
    Link.__init__(self, True, 'archive', ['a'])

  def GetRunner(self, j):
    #TODO: Add config section 'link args'?
    #TODO: This one is massively wrong...
    args = ['ar', 'rcs', j.output.abs_path] + [f.abs_path for f in j.depend_set]
    args += GetConfigSectionAsArgs(j.input, 'archive-args')
    def Go():
      j.env.RunBuildCmd(args)
    return Go
class MakeSo(Link):
  def __init__(self):
    Link.__init__(self, True, 'generate so', ['so'])

  def GetRunner(self, job):
    args = Link.GetRunnerArgs(self, job)
    args += ['-shared', '-Wl,-soname,' + job.output.base,'-Wl,-Bsymbolic', '-o'+ job.output.abs_path]
    args += GetConfigSectionAsArgs(job.input, 'so-args')

    def Go():
      job.env.RunBuildCmd(args)
    return Go

class RenderGraphviz(JobKind):
  def __init__(self, tool, out):
    self.__tool = tool
    self.__out = out
    JobKind.__init__(self, 'render Graphviz %s %s' % (tool, out), tool, [out])

  def GetInput(self, out_f):
    return out_f.GetRelatedFileAndTree(ext_list=out_f.ext_list[:-1] + [self.__tool])

  def GetOutput(self, in_f):
    return frozenset([in_f.GetRelatedOutFile(ext_list=in_f.ext_list[:-1] + [self.__out])])

  def GetRunner(self, job):
    args = [self.__tool, '-T%s' % self.__out, '-o%s' % job.output.abs_path, job.input.abs_path]

    def Go():
      job.env.RunBuildCmd(args)
    return Go

class TranslateNyc(JobKind):
  def __init__(self):
    JobKind.__init__(self, 'translate nyc', 'nyc', [ 'yy', 'cc', 'h'])

  def GetInput(self, out_f):
    if len(out_f.ext_list) < 1:
      return None
    out_ext = out_f.ext_list[-1]
    if out_ext == 'h':
      if len(out_f.ext_list) > 1 and out_f.ext_list[-2] in ['lexer', 'driver']:
        return out_f.GetRelatedFileAndTree(ext_list=out_f.ext_list[:-2] + ['nyc'])
      else:
        return out_f.GetRelatedFileAndTree(ext_list=out_f.ext_list[:-1] + ['nyc'])

    #Everything else must have a subtype, so stop if we don't have one.
    elif len(out_f.ext_list) < 2:
      return None

    elif out_ext == 'yy':
      if out_f.ext_list[-2] != 'parser':
        return None
      return out_f.GetRelatedFileAndTree(ext_list=out_f.ext_list[:-2] + ['nyc'])

    elif out_ext == 'cc':
      if out_f.ext_list[-2] in ['lexer', 'cst']:
        return out_f.GetRelatedFileAndTree(ext_list=out_f.ext_list[:-2] + ['nyc'])
      return None

  def GetOutput(self, in_f):
    return frozenset([
      in_f.GetRelatedOutFile(ext_list=in_f.ext_list[:-1] + ['parser', 'yy']),
      in_f.GetRelatedOutFile(ext_list=in_f.ext_list[:-1] + ['lexer',  'cc']),
      in_f.GetRelatedOutFile(ext_list=in_f.ext_list[:-1] + ['lexer',  'h']),
      in_f.GetRelatedOutFile(ext_list=in_f.ext_list[:-1] + ['driver', 'h']),
      in_f.GetRelatedOutFile(ext_list=in_f.ext_list[:-1] + ['cst', 'cc']),
      in_f.GetRelatedOutFile(ext_list=in_f.ext_list[:-1] + ['h'])
      ])

  def GetRunner(self, job):
    args = ['nyc.py', job.input.abs_path, '-o', job.output_dir, '-b', job.input.branch]
    def Do():
      job.env.RunBuildCmd(args)
      #TODO: Make these warning removals either go away, or be more precise
      for f in job.output_set:
        SetGnuArg(f.jhm_cache_file, '-Wno-unused-parameter')
    return Do

class TranslateYacc(JobKind):
  def __init__(self, cpp):
    self.__cpp = cpp
    self.__in_ext = 'yy' if cpp else 'y'
    self.__c_ext = 'cc' if cpp else 'c'
    JobKind.__init__(self, 'translate yacc C' + '++' if cpp else '', self.__in_ext, [self.__c_ext, 'h'])

  #TODO: There is actually a little that should be scanned for here.
  def GetDepends(self, req_set):
    return set()

  def GetInput(self, out_f):
    if out_f.ext_list[-1] == 'h':
      if len(out_f.ext_list) > 1 and out_f.ext_list[-2] in ['location', 'position']:
        return out_f.GetRelatedFileAndTree(ext_list=out_f.ext_list[:-2] + [self.__in_ext])
      else:
        return out_f.GetRelatedFileAndTree(ext_list=out_f.ext_list[:-1] + [self.__in_ext])
    if out_f.ext_list[-1] == self.__c_ext:
      return out_f.GetRelatedFileAndTree(ext_list=out_f.ext_list[:-1] + [self.__in_ext])
    return None

  def GetOutput(self, in_f):
    return frozenset([
         in_f.GetRelatedOutFile(ext_list=in_f.ext_list[:-1] + [self.__c_ext])
        ,in_f.GetRelatedOutFile(ext_list=in_f.ext_list[:-1] + ['h'])
        ,in_f.GetRelatedOutFile(ext_list=in_f.ext_list[:-1] + ['position','h'])
        ,in_f.GetRelatedOutFile(ext_list=in_f.ext_list[:-1] + ['location','h'])
      ])

  def GetRunner(self, job):
    args = ['bison-fixer.py', job.input.name]
    for f in job.depend_set:
      args.append(f.abs_path)
    args.append(job.output_dir)

    if job.env.options.print_all_cmd or job.env.options.print_build_cmd:
      args.append('--print-commands')

    def Go():
      for f in job.output_set:
        SetGnuArg(f.jhm_cache_file, '-Wno-old-style-cast')
        SetGnuArg(f.jhm_cache_file, '-Wno-all')
        SetGnuArg(f.jhm_cache_file, '-Wno-extra')
      job.env.RunBuildCmd(args)
    return Go

class SideEffect(JobKind):
  def __init__(self):
    JobKind.__init__(self, 'side effect', None, None)

  def GetInput(self, out_f):
    if out_f.GetConfig('job_kind') == 'sideeffect':
      if not out_f.GetConfig('src'):
        raise BuildError('"src" for sideeffect job not specified in "%s.jhm".' % out_f)
      return True
    return False

  def GetBaseDepends(self, job):
    return set([job.env.GetFileFromPath(job.output.jhm_file.Get('src'))])

  def GetRunner(self, job):
    def Go():
      pass
    return Go

class Symlink(JobKind):
  def __init__(self):
    JobKind.__init__(self, 'symlink', None, None)

  def GetInput(self, out_f):
    if out_f.GetConfig('job_kind') == 'symlink':
      if not out_f.GetConfig('src'):
        raise BuildError('"src" for symlink job not specified in "%s.jhm".' % out_f)
      return True
    return None

  def GetBaseDepends(self, job):
    return set([job.env.GetFileFromPath(job.output.jhm_file.Get('src'))])

  def GetRunner(self, job):
    args = ['ln','-f','-s',list(job.depend_set)[0].abs_path, list(job.output_set)[0].abs_path]
    def Go():
      job.env.RunBuildCmd(args)
    return Go

class OpenOfficeToPdf(JobKind):
  def __init__(self, in_ext):
    self.__in_ext = in_ext
    JobKind.__init__(self, 'Convert %s to pdf' % in_ext, in_ext, ['pdf'])

  def GetInput(self, out_f):
    return out_f.GetRelatedFileAndTree(ext_list=out_f.ext_list[:-1] + [self.__in_ext])

  def GetOutput(self, in_f):
    return frozenset([in_f.GetRelatedFileAndTree(ext_list=in_f.ext_list[:-1] + ['pdf'])])

  def GetRunner(self, job):
    outdir = os.path.join(job.output.tree.path, job.output.branch)
    args = ['soffice','-convert-to','pdf','-invisible', '-outdir', outdir, job.input.abs_path ]
    def Go():
      job.env.RunBuildCmd(args)
    return Go


job_kinds = [CompileC('c', False, False), CompileC('cc', True, False) #, CompileC('cpp', True, False)
             ,CompileC('c', False, True), CompileC('cc', True, True) #, CompileC('cpp', True, True)
             , Haskell(False), Haskell(True)
             ,Link(), Archive(), MakeSo()
             ,TranslateNyc()
             ,TranslateYacc(False), TranslateYacc(True)
             ,GenerateSwig('php', True), GenerateSwig('python', True), GenerateSwig('java', True)
             ,Closure()
             ,RenderGraphviz('dot', 'png'), RenderGraphviz('dot', 'svg'), RenderGraphviz('fdp', 'png'), RenderGraphviz('fdp', 'svg'), RenderGraphviz('dot','pdf')
             ,OpenOfficeToPdf('docx')
             ,SideEffect(), Symlink()
            ]
