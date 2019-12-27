# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import json
import re
import glob
import pathlib

import common
import git_tree

_TREE_FILE_NAME = ".git_tree"
common.DEBUG_ = False


class GitRebaser(object):
  """Provides rebaser functions.

  Assume the public function name is corresponding to the executable
  arguments.
  """

  def __init__(self):
    self._tree_path = self._find_tree_data_file()
    if self._tree_path is not None:
      self._tree = git_tree.GitTree(self._tree_path)

  def _find_tree_data_file(self):
    path = pathlib.Path(os.getcwd())
    while str(path) != path.root:
      tree_path = os.path.join(path, _TREE_FILE_NAME)
      result = glob.glob(tree_path)
      if len(result) > 0:
        return result[0]
      path = path.parent
    return None

  def _validate(self):
    if self._tree_path is None:
      print(
          "Error: Cannot find tree data file. Please use 'init' arg to initialize."
      )
      exit(1)

  def _switch_branch(self, new_branch_name):
    #error = common.sys_raise("git diff-index --quiet HEAD -- && git checkout " + new_branch_name)
    error = common.sys_raise("git checkout " + new_branch_name)
    if self._get_current_branch_name() != new_branch_name:
      raise RuntimeError("switch to branch %s failed" % new_branch_name)
    return error

  def _get_current_branch_name(self):
    current_branch_name = common.sys_output(
        "git rev-parse --abbrev-ref HEAD").strip()
    return current_branch_name

  def _get_brief_commit_message(self, branch_name):
    if branch_name == "master":
      log_format = "'(sync %cr) %h'"
    else:
      log_format = "%B"
    return common.sys_output("git log --format=%s -n 1 %s | head -1" %
                             (log_format, branch_name))

  def _update_one_git_edge(self, node_i, new_parent_i):
    node_name = self._tree.get_node_name(node_i)
    parent_name = self._tree.get_node_name(new_parent_i)
    print("Rebase %s to %s" % (node_name, parent_name))
    error = self._switch_branch(node_name)
    if error:
      print("ERROR")
      exit(1)

    error = common.sys_raise("git update-parent " + parent_name)
    self._tree.move_one_edge(node_i, new_parent_i)

  def _update_whole_branch(self, node_i, new_parent_i):
    node_i = int(node_i)
    new_parent_i = int(new_parent_i)
    for edge in [[new_parent_i, node_i]] + self._tree.get_subedges(node_i):
      self._update_one_git_edge(edge[1], edge[0])

  def init(self, args):
    if not os.path.exists(_TREE_FILE_NAME):
      git_tree.GitTree(_TREE_FILE_NAME)

  def xl(self, args):
    self._validate()
    self._tree.pprint(
        cb=lambda name: self._get_brief_commit_message(name),
        current_node_name=self._get_current_branch_name())

  def rebase(self, args):
    self._validate()
    self._update_whole_branch(args.source, args.dest)

  def commit(self, args):
    self._validate()
    branch_name = args.branch_name
    if branch_name is None:
      branch_name = str(self._tree.get_next_node_i())

    current_name = self._get_current_branch_name()
    common.sys_raise("git checkout -b %s; git commit" % branch_name)
    # Add a new one.
    self._tree.create_node(branch_name)
    self._tree.add_edge(current_name, branch_name)

  def amend(self, args):
    self._validate()
    common.sys_raise("git commit --amend --no-edit")
    current_branch = self._get_current_branch_name()
    self._tree.move_one_edge(current_branch,
                             self._tree.get_parent(current_branch))

  def prune(self, args):
    self._validate()
    branch_name = self._tree.get_node_name(args.branch_index)
    common.sys_raise("git branch -D %s" % branch_name)
    self._tree.remove_node_by_name(branch_name)

  def update(self, args):
    self._validate()
    branch_name = self._tree.get_node_name(args.branch_index)
    common.sys_raise("git checkout %s" % branch_name)

  def sync(self, args):
    self._validate()
    common.sys_raise("git checkout master")
    common.sys_raise("git pull")
    self._tree.move_one_edge(0, -1)

  def diff(self, args):
    self._validate()
    self.diff_parent("diff")

  def difftool(self, args):
    self._validate()
    self.diff_parent("difftool")

  def diff_parent(self, git_command, *args):
    current_branch = self._get_current_branch_name()
    parent_branch_name = self._tree.get_node_name(
        self._tree.get_parent(current_branch))
    opt = " ".join(args)
    common.sys_raise("git %s %s %s" % (git_command, parent_branch_name, opt))

  def change_branch_name(self, args):
    new_name = args.new_name
    node_index = self._tree._get_node_index(self._get_current_branch_name())
    if new_name is None:
      new_name = str(node_index)
    common.sys_raise("git branch -m %s" % new_name)
    self._tree.set_node_name(node_index, new_name)
