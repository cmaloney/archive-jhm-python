# This file is licensed under the terms of the Apache License, Version 2.0
# Please see the file COPYING for the full text of this license
#
# Copyright 2010-2011 Tagged

import os.path, threading
from itertools import chain

from jhm import RunCmd


class Deps(object):
  def __init__(self):
    #Lazy loaded to keep from doing work when not necessary.
    self.__module_dict = None
    self.__modules_by_id = {}
    self.__module_dict_lock = threading.Lock()

  def __BuildDb(self):
    self.__module_dict = {}
    #TODO: Print all commands flag doesn't reach this...
    (stdout, stderr) = RunCmd(['ghc-pkg','dump'], True, False)
    for module in stdout.split('---'):
      submodule_dict = {}
      current_cmd = None
      for line in module.split('\n'):
        if len(line) < 1:
          continue
        if line[0] == ' ':
          cleaned_rhs = ' ' + line.strip()
          if current_cmd is None:
            raise ValueError(cleaned_rhs)
          cur = submodule_dict[current_cmd]
          submodule_dict[current_cmd] += ' ' + cleaned_rhs
        else:
          split = line.split(':',2)
          assert len(split) > 1
          current_cmd = split[0].strip() + '_str'

          cleaned_rhs = split[1].strip()
          submodule_dict[current_cmd] = (cleaned_rhs if cleaned_rhs else '')

      def ToArray(option):
        submodule_dict[option] = submodule_dict.get(option + '_str','').split()

      #TODO: De-stringify select pieces.
      ToArray('depends')
      ToArray('exposed-modules')
      ToArray('ld-options')
      ToArray('extra-libraries')
      if submodule_dict.get('exposed_str','True').strip() == 'False':
        continue
      self.__module_dict[submodule_dict['name_str']] = submodule_dict
      self.__modules_by_id[submodule_dict['id_str']] = submodule_dict

  def __ExtractArgs(self, mod_dict):
    #TODO: This probably is slightly oversimplified
    link_list = [(mod_dict['library-dirs_str'], mod_dict['hs-libraries_str'])]
    for l in mod_dict['extra-libraries']:
      link_list.append((None,l))
    ld_options = mod_dict['ld-options']

    for dep in  mod_dict['depends']:
      link_list += self.GetLinkArgsById(dep)
    return link_list

  def GetLinkArgsByImportName(self, import_list):
    #TODO: This is a bad way to do this search. Should really index, but are lazy for now.
    if import_list is None:
      return list()
    link_list = list()
    for k, v in self.module_dict.items():
      for f in import_list:
        assert f == f.strip()
        if f in v['exposed-modules']:
          link_list += self.__ExtractArgs(v)
    return link_list

  def GetLinkInfo(self, import_list):
    link_list = list()
    link_list += self.GetLinkArgsByImportName(import_list)
    link_list.reverse()
    min_link_list = list()
    used_links = set()
    base_link = None
    for l in link_list:
      if l[1] not in used_links:
        used_links.add(l[1])
        min_link_list.append(l)
    min_link_list.reverse()
    return min_link_list

  def GetStaticLinkArgs(self, import_list):
    #TODO: Could eliminate redundant library path additions.
    link_list = self.GetLinkInfo(import_list)
    l = reduce(lambda a, b: a + b, map(lambda l: ['-L%s' % l[0], '-l%s' % l[1]] if l[0] not in [None,'/'] else (['-l%s' % l[1]] if l[1] else []), link_list),list())
    if len(l) > 0:
      #TODO: This is sort of hackish, but then again this is haskell's way of getting around a dependency loop the built.
      l += self.module_dict['rts']['ld-options']
    return l

  def GetDynamicLinkArgs(self, import_list):
    #What we need is a list of tuples (lib_path, libname)
    args = []
    link_list = self.GetLinkInfo(import_list)
    for l in link_list:
      if l[0] is None:
        args.append('-l%s' % l[1])
      else:
        ghc_ver = RunCmd(['ghc', '--numeric-version'], True, False)[0].strip()
        args += ['-L%s' % l[0], '-l%s-ghc%s' % (l[1],ghc_ver)]
    return args

  def GetLinkArgsById(self, id_):
    id_ = id_.strip()
    if self.modules_by_id.has_key(id_):
      return self.__ExtractArgs(self.modules_by_id[id_])
    else:
      raise ValueError("Depended upon module %s is hidden or not present." % id_)

  @property
  def module_dict(self):
    with self.__module_dict_lock:
      if self.__module_dict is None:
        self.__BuildDb()
      return self.__module_dict

  @property
  def modules_by_id(self):
    #Ensure initialized
    assert(self.module_dict)
    return self.__modules_by_id
