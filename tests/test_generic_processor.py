# Copyright (C) 2008 Canonical Ltd
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import time

from bzrlib import (
    branch,
    tests,
    )

from bzrlib.plugins.fastimport import (
    commands,
    errors,
    )

from bzrlib.plugins.fastimport.processors import (
    generic_processor,
    )


class TestCaseForGenericProcessor(tests.TestCaseWithTransport):

    branch_format = "pack-0.92"

    def get_handler(self):
        branch = self.make_branch('.', format=self.branch_format)
        handler = generic_processor.GenericProcessor(branch.bzrdir)
        return handler, branch

    # FIXME: [] as a default is bad, as it is mutable, but I want
    # to use None to mean "don't check this".
    def assertChanges(self, branch, revno, expected_added=[],
            expected_removed=[], expected_modified=[],
            expected_renamed=[], expected_kind_changed=[]):
        """Check the changes introduced in a revision of a branch.

        This method checks that a revision introduces expected changes.
        The required changes are passed in as a list, where
        each entry contains the needed information about the change.

        If you do not wish to assert anything about a particular
        category then pass None instead.

        branch: The branch.
        revno: revision number of revision to check.
        expected_added: a list of (filename,) tuples that must have
            been added in the delta.
        expected_removed: a list of (filename,) tuples that must have
            been removed in the delta.
        expected_modified: a list of (filename,) tuples that must have
            been modified in the delta.
        expected_renamed: a list of (old_path, new_path) tuples that
            must have been renamed in the delta.
        expected_kind_changed: a list of (path, old_kind, new_kind) tuples
            that must have been changed in the delta.
        :return: revtree1, revtree2
        """
        repo = branch.repository
        revtree1 = repo.revision_tree(branch.get_rev_id(revno - 1))
        revtree2 = repo.revision_tree(branch.get_rev_id(revno))
        changes = revtree2.changes_from(revtree1)
        self._check_changes(changes, expected_added, expected_removed,
            expected_modified, expected_renamed, expected_kind_changed)
        return revtree1, revtree2

    def _check_changes(self, changes, expected_added=[],
            expected_removed=[], expected_modified=[],
            expected_renamed=[], expected_kind_changed=[]):
        """Check the changes in a TreeDelta

        This method checks that the TreeDelta contains the expected
        modifications between the two trees that were used to generate
        it. The required changes are passed in as a list, where
        each entry contains the needed information about the change.

        If you do not wish to assert anything about a particular
        category then pass None instead.

        changes: The TreeDelta to check.
        expected_added: a list of (filename,) tuples that must have
            been added in the delta.
        expected_removed: a list of (filename,) tuples that must have
            been removed in the delta.
        expected_modified: a list of (filename,) tuples that must have
            been modified in the delta.
        expected_renamed: a list of (old_path, new_path) tuples that
            must have been renamed in the delta.
        expected_kind_changed: a list of (path, old_kind, new_kind) tuples
            that must have been changed in the delta.
        """
        renamed = changes.renamed
        added = changes.added
        removed = changes.removed
        modified = changes.modified
        kind_changed = changes.kind_changed
        if expected_renamed is not None:
            self.assertEquals(len(renamed), len(expected_renamed),
                "%s is renamed, expected %s" % (renamed, expected_renamed))
            renamed_files = [(item[0], item[1]) for item in renamed]
            for expected_renamed_entry in expected_renamed:
                self.assertTrue(expected_renamed_entry in renamed_files,
                    "%s is not renamed, %s are" % (str(expected_renamed_entry),
                        renamed_files))
        if expected_added is not None:
            self.assertEquals(len(added), len(expected_added),
                "%s is added" % str(added))
            added_files = [(item[0],) for item in added]
            for expected_added_entry in expected_added:
                self.assertTrue(expected_added_entry in added_files,
                    "%s is not added, %s are" % (str(expected_added_entry),
                        added_files))
        if expected_removed is not None:
            self.assertEquals(len(removed), len(expected_removed),
                "%s is removed" % str(removed))
            removed_files = [(item[0],) for item in removed]
            for expected_removed_entry in expected_removed:
                self.assertTrue(expected_removed_entry in removed_files,
                    "%s is not removed, %s are" % (str(expected_removed_entry),
                        removed_files))
        if expected_modified is not None:
            self.assertEquals(len(modified), len(expected_modified),
                "%s is modified" % str(modified))
            modified_files = [(item[0],) for item in modified]
            for expected_modified_entry in expected_modified:
                self.assertTrue(expected_modified_entry in modified_files,
                    "%s is not modified, %s are" % (
                    str(expected_modified_entry), modified_files))
        if expected_kind_changed is not None:
            self.assertEquals(len(kind_changed), len(expected_kind_changed),
                "%s is kind-changed, expected %s" % (kind_changed,
                    expected_kind_changed))
            kind_changed_files = [(item[0], item[2], item[3])
                for item in kind_changed]
            for expected_kind_changed_entry in expected_kind_changed:
                self.assertTrue(expected_kind_changed_entry in
                    kind_changed_files, "%s is not kind-changed, %s are" % (
                    str(expected_kind_changed_entry), kind_changed_files))

    def assertContent(self, branch, tree, path, content):
        file_id = tree.inventory.path2id(path)
        branch.lock_read()
        self.addCleanup(branch.unlock)
        self.assertEqual(tree.get_file_text(file_id), content)

    def assertSymlinkTarget(self, branch, tree, path, target):
        file_id = tree.inventory.path2id(path)
        branch.lock_read()
        self.addCleanup(branch.unlock)
        self.assertEqual(tree.get_symlink_target(file_id), target)

    def assertExecutable(self, branch, tree, path, executable):
        file_id = tree.inventory.path2id(path)
        branch.lock_read()
        self.addCleanup(branch.unlock)
        self.assertEqual(tree.is_executable(file_id), executable)

    def assertRevisionRoot(self, revtree, path):
        self.assertEqual(revtree.get_revision_id(),
                         revtree.inventory.root.children[path].revision)


class TestImportToPackModify(TestCaseForGenericProcessor):

    def file_command_iter(self, path, kind='file', content='aaa',
        executable=False, to_kind=None, to_content='bbb', to_executable=None):
        # Revno 1: create a file or symlink
        # Revno 2: modify it
        if to_kind is None:
            to_kind = kind
        if to_executable is None:
            to_executable = executable
        def command_list():
            author = ['', 'bugs@a.com', time.time(), time.timezone]
            committer = ['', 'elmer@a.com', time.time(), time.timezone]
            def files_one():
                yield commands.FileModifyCommand(path, kind, executable,
                        None, content)
            yield commands.CommitCommand('head', '1', author,
                committer, "commit 1", None, [], files_one)
            def files_two():
                yield commands.FileModifyCommand(path, to_kind, to_executable,
                        None, to_content)
            yield commands.CommitCommand('head', '2', author,
                committer, "commit 2", ":1", [], files_two)
        return command_list

    def test_modify_file_in_root(self):
        handler, branch = self.get_handler()
        path = 'a'
        handler.process(self.file_command_iter(path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[(path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_modified=[(path,)])
        self.assertContent(branch, revtree1, path, "aaa")
        self.assertContent(branch, revtree2, path, "bbb")
        self.assertRevisionRoot(revtree1, path)
        self.assertRevisionRoot(revtree2, path)

    def test_modify_file_in_subdir(self):
        handler, branch = self.get_handler()
        path = 'a/a'
        handler.process(self.file_command_iter(path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_modified=[(path,)])
        self.assertContent(branch, revtree1, path, "aaa")
        self.assertContent(branch, revtree2, path, "bbb")

    def test_modify_symlink_in_root(self):
        handler, branch = self.get_handler()
        path = 'a'
        handler.process(self.file_command_iter(path, kind='symlink'))
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_modified=[(path,)])
        self.assertSymlinkTarget(branch, revtree1, path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, path, "bbb")
        self.assertRevisionRoot(revtree1, path)
        self.assertRevisionRoot(revtree2, path)

    def test_modify_symlink_in_subdir(self):
        handler, branch = self.get_handler()
        path = 'a/a'
        handler.process(self.file_command_iter(path, kind='symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_modified=[(path,)])
        self.assertSymlinkTarget(branch, revtree1, path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, path, "bbb")

    def test_modify_file_becomes_symlink(self):
        handler, branch = self.get_handler()
        path = 'a/a'
        handler.process(self.file_command_iter(path,
            kind='file', to_kind='symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_kind_changed=[(path, 'file', 'symlink')])
        self.assertContent(branch, revtree1, path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, path, "bbb")

    def test_modify_symlink_becomes_file(self):
        handler, branch = self.get_handler()
        path = 'a/a'
        handler.process(self.file_command_iter(path,
            kind='symlink', to_kind='file'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_kind_changed=[(path, 'symlink', 'file')])
        self.assertSymlinkTarget(branch, revtree1, path, "aaa")
        self.assertContent(branch, revtree2, path, "bbb")

    def test_modify_file_now_executable(self):
        handler, branch = self.get_handler()
        path = 'a/a'
        handler.process(self.file_command_iter(path,
            executable=False, to_executable=True, to_content='aaa'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_modified=[(path,)])
        self.assertExecutable(branch, revtree1, path, False)
        self.assertExecutable(branch, revtree2, path, True)

    def test_modify_file_no_longer_executable(self):
        handler, branch = self.get_handler()
        path = 'a/a'
        handler.process(self.file_command_iter(path,
            executable=True, to_executable=False, to_content='aaa'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_modified=[(path,)])
        self.assertExecutable(branch, revtree1, path, True)
        self.assertExecutable(branch, revtree2, path, False)


class TestImportToPackModifyTwice(TestCaseForGenericProcessor):
    """This tests when the same file is modified twice in the one commit.
    
    Note: hg-fast-export produces data like this on occasions.
    """

    def file_command_iter(self, path, kind='file', content='aaa',
        executable=False, to_kind=None, to_content='bbb', to_executable=None):
        # Revno 1: create a file twice
        if to_kind is None:
            to_kind = kind
        if to_executable is None:
            to_executable = executable
        def command_list():
            author = ['', 'bugs@a.com', time.time(), time.timezone]
            committer = ['', 'elmer@a.com', time.time(), time.timezone]
            def files_one():
                yield commands.FileModifyCommand(path, kind, executable,
                        None, content)
                yield commands.FileModifyCommand(path, to_kind, to_executable,
                        None, to_content)
            yield commands.CommitCommand('head', '1', author,
                committer, "commit 1", None, [], files_one)
        return command_list

    def test_modify_file_twice_in_root(self):
        handler, branch = self.get_handler()
        path = 'a'
        handler.process(self.file_command_iter(path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[(path,)])
        self.assertContent(branch, revtree1, path, "aaa")
        self.assertRevisionRoot(revtree1, path)


class TestImportToPackModifyTricky(TestCaseForGenericProcessor):

    def file_command_iter(self, path1, path2, kind='file'):
        # Revno 1: create a file or symlink in a directory
        # Revno 2: create a second file that implicitly deletes the
        # first one because either:
        # * the new file is a in directory with the old file name
        # * the new file has the same name as the directory of the first
        def command_list():
            author = ['', 'bugs@a.com', time.time(), time.timezone]
            committer = ['', 'elmer@a.com', time.time(), time.timezone]
            def files_one():
                yield commands.FileModifyCommand(path1, kind, False,
                        None, "aaa")
            yield commands.CommitCommand('head', '1', author,
                committer, "commit 1", None, [], files_one)
            def files_two():
                yield commands.FileModifyCommand(path2, kind, False,
                        None, "bbb")
            yield commands.CommitCommand('head', '2', author,
                committer, "commit 2", ":1", [], files_two)
        return command_list


    def test_modify_file_becomes_directory(self):
        handler, branch = self.get_handler()
        path1 = 'a/b'
        path2 = 'a/b/c'
        handler.process(self.file_command_iter(path1, path2))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (path1,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_added=[(path2,)],
            expected_kind_changed=[(path1, 'file', 'directory')])
        self.assertContent(branch, revtree1, path1, "aaa")
        self.assertContent(branch, revtree2, path2, "bbb")

    def test_modify_directory_becomes_file(self):
        handler, branch = self.get_handler()
        path1 = 'a/b/c'
        path2 = 'a/b'
        handler.process(self.file_command_iter(path1, path2))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), ('a/b',), (path1,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[(path1,),],
            expected_kind_changed=[(path2, 'directory', 'file')])
        self.assertContent(branch, revtree1, path1, "aaa")
        self.assertContent(branch, revtree2, path2, "bbb")

    def test_modify_symlink_becomes_directory(self):
        handler, branch = self.get_handler()
        path1 = 'a/b'
        path2 = 'a/b/c'
        handler.process(self.file_command_iter(path1, path2, 'symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (path1,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_added=[(path2,)],
            expected_kind_changed=[(path1, 'symlink', 'directory')])
        self.assertSymlinkTarget(branch, revtree1, path1, "aaa")
        self.assertSymlinkTarget(branch, revtree2, path2, "bbb")

    def test_modify_directory_becomes_symlink(self):
        handler, branch = self.get_handler()
        path1 = 'a/b/c'
        path2 = 'a/b'
        handler.process(self.file_command_iter(path1, path2, 'symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), ('a/b',), (path1,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[(path1,),],
            expected_kind_changed=[(path2, 'directory', 'symlink')])
        self.assertSymlinkTarget(branch, revtree1, path1, "aaa")
        self.assertSymlinkTarget(branch, revtree2, path2, "bbb")


class TestImportToPackDelete(TestCaseForGenericProcessor):

    def file_command_iter(self, path, kind='file'):
        # Revno 1: create a file or symlink
        # Revno 2: delete it
        def command_list():
            author = ['', 'bugs@a.com', time.time(), time.timezone]
            committer = ['', 'elmer@a.com', time.time(), time.timezone]
            def files_one():
                yield commands.FileModifyCommand(path, kind, False,
                        None, "aaa")
            yield commands.CommitCommand('head', '1', author,
                committer, "commit 1", None, [], files_one)
            def files_two():
                yield commands.FileDeleteCommand(path)
            yield commands.CommitCommand('head', '2', author,
                committer, "commit 2", ":1", [], files_two)
        return command_list

    def test_delete_file_in_root(self):
        handler, branch = self.get_handler()
        path = 'a'
        handler.process(self.file_command_iter(path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[(path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[(path,)])
        self.assertContent(branch, revtree1, path, "aaa")
        self.assertRevisionRoot(revtree1, path)

    def test_delete_file_in_subdir(self):
        handler, branch = self.get_handler()
        path = 'a/a'
        handler.process(self.file_command_iter(path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[('a',), (path,)])
        self.assertContent(branch, revtree1, path, "aaa")

    def test_delete_symlink_in_root(self):
        handler, branch = self.get_handler()
        path = 'a'
        handler.process(self.file_command_iter(path, kind='symlink'))
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[(path,)])
        self.assertSymlinkTarget(branch, revtree1, path, "aaa")
        self.assertRevisionRoot(revtree1, path)

    def test_delete_symlink_in_subdir(self):
        handler, branch = self.get_handler()
        path = 'a/a'
        handler.process(self.file_command_iter(path, kind='symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[('a',), (path,)])
        self.assertSymlinkTarget(branch, revtree1, path, "aaa")

    def test_delete_file_in_deep_subdir(self):
        handler, branch = self.get_handler()
        path = 'a/b/c/d'
        handler.process(self.file_command_iter(path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), ('a/b',), ('a/b/c',), (path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[('a',), ('a/b',), ('a/b/c',), (path,)])
        self.assertContent(branch, revtree1, path, "aaa")


class TestImportToPackDeleteNew(TestCaseForGenericProcessor):
    """Test deletion of a newly added file."""

    def file_command_iter(self, path, kind='file'):
        # Revno 1: create a file or symlink then delete it
        def command_list():
            author = ['', 'bugs@a.com', time.time(), time.timezone]
            committer = ['', 'elmer@a.com', time.time(), time.timezone]
            def files_one():
                yield commands.FileModifyCommand(path, kind, False,
                        None, "aaa")
                yield commands.FileDeleteCommand(path)
            yield commands.CommitCommand('head', '1', author,
                committer, "commit 1", None, [], files_one)
        return command_list

    def test_delete_new_file_in_root(self):
        handler, branch = self.get_handler()
        path = 'a'
        handler.process(self.file_command_iter(path))
        revtree0, revtree1 = self.assertChanges(branch, 1,)

    def test_delete_new_file_in_subdir(self):
        handler, branch = self.get_handler()
        path = 'a/a'
        handler.process(self.file_command_iter(path))
        revtree0, revtree1 = self.assertChanges(branch, 1,)

    def test_delete_new_symlink_in_root(self):
        handler, branch = self.get_handler()
        path = 'a'
        handler.process(self.file_command_iter(path, kind='symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,)

    def test_delete_new_symlink_in_subdir(self):
        handler, branch = self.get_handler()
        path = 'a/a'
        handler.process(self.file_command_iter(path, kind='symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,)

    def test_delete_new_file_in_deep_subdir(self):
        handler, branch = self.get_handler()
        path = 'a/b/c/d'
        handler.process(self.file_command_iter(path))
        revtree0, revtree1 = self.assertChanges(branch, 1,)


class TestImportToPackDeleteThenAdd(TestCaseForGenericProcessor):
    """Test delete followed by an add. Merges can cause this."""

    def file_command_iter(self, path, kind='file', content='aaa',
        executable=False, to_kind=None, to_content='bbb', to_executable=None):
        # Revno 1: create a file or symlink
        # Revno 2: delete it and add it
        if to_kind is None:
            to_kind = kind
        if to_executable is None:
            to_executable = executable
        def command_list():
            author = ['', 'bugs@a.com', time.time(), time.timezone]
            committer = ['', 'elmer@a.com', time.time(), time.timezone]
            def files_one():
                yield commands.FileModifyCommand(path, kind, executable,
                        None, content)
            yield commands.CommitCommand('head', '1', author,
                committer, "commit 1", None, [], files_one)
            def files_two():
                yield commands.FileDeleteCommand(path)
                yield commands.FileModifyCommand(path, to_kind, to_executable,
                        None, to_content)
            yield commands.CommitCommand('head', '2', author,
                committer, "commit 2", ":1", [], files_two)
        return command_list

    def test_delete_then_add_file_in_root(self):
        handler, branch = self.get_handler()
        path = 'a'
        handler.process(self.file_command_iter(path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[(path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[(path,)],
            expected_added=[(path,)])
        self.assertContent(branch, revtree1, path, "aaa")
        self.assertContent(branch, revtree2, path, "bbb")
        self.assertRevisionRoot(revtree1, path)
        self.assertRevisionRoot(revtree2, path)

    def test_delete_then_add_file_in_subdir(self):
        handler, branch = self.get_handler()
        path = 'a/a'
        handler.process(self.file_command_iter(path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[(path,)],
            expected_added=[(path,)])
        self.assertContent(branch, revtree1, path, "aaa")
        self.assertContent(branch, revtree2, path, "bbb")

    def test_delete_then_add_symlink_in_root(self):
        handler, branch = self.get_handler()
        path = 'a'
        handler.process(self.file_command_iter(path, kind='symlink'))
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[(path,)],
            expected_added=[(path,)])
        self.assertSymlinkTarget(branch, revtree1, path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, path, "bbb")
        self.assertRevisionRoot(revtree1, path)
        self.assertRevisionRoot(revtree2, path)

    def test_delete_then_add_symlink_in_subdir(self):
        handler, branch = self.get_handler()
        path = 'a/a'
        handler.process(self.file_command_iter(path, kind='symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[(path,)],
            expected_added=[(path,)])
        self.assertSymlinkTarget(branch, revtree1, path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, path, "bbb")


class TestImportToPackDeleteDirectory(TestCaseForGenericProcessor):

    def file_command_iter(self, paths, dir):
        # Revno 1: create multiple files
        # Revno 2: delete a directory holding those files
        def command_list():
            author = ['', 'bugs@a.com', time.time(), time.timezone]
            committer = ['', 'elmer@a.com', time.time(), time.timezone]
            def files_one():
                for i, path in enumerate(paths):
                    yield commands.FileModifyCommand(path, 'file', False,
                            None, "aaa%d" % i)
            yield commands.CommitCommand('head', '1', author,
                committer, "commit 1", None, [], files_one)
            def files_two():
                yield commands.FileDeleteCommand(dir)
            yield commands.CommitCommand('head', '2', author,
                committer, "commit 2", ":1", [], files_two)
        return command_list

    def test_delete_dir(self):
        handler, branch = self.get_handler()
        paths = ['a/b/c', 'a/b/d', 'a/b/e/f', 'a/g']
        dir = 'a/b'
        handler.process(self.file_command_iter(paths, dir))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[
                ('a',), ('a/b',), ('a/b/c',),
                ('a/b/d',),
                ('a/b/e',), ('a/b/e/f',),
                ('a/g',),
                ])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[
                ('a/b',), ('a/b/c',),
                ('a/b/d',),
                ('a/b/e',), ('a/b/e/f',),
                ])


class TestImportToPackRename(TestCaseForGenericProcessor):

    def get_command_iter(self, old_path, new_path, kind='file'):
        # Revno 1: create a file or symlink
        # Revno 2: rename it
        def command_list():
            author = ['', 'bugs@a.com', time.time(), time.timezone]
            committer = ['', 'elmer@a.com', time.time(), time.timezone]
            def files_one():
                yield commands.FileModifyCommand(old_path, kind, False,
                        None, "aaa")
            yield commands.CommitCommand('head', '1', author,
                committer, "commit 1", None, [], files_one)
            def files_two():
                yield commands.FileRenameCommand(old_path, new_path)
            yield commands.CommitCommand('head', '2', author,
                committer, "commit 2", ":1", [], files_two)
        return command_list

    def test_rename_file_in_root(self):
        handler, branch = self.get_handler()
        old_path = 'a'
        new_path = 'b'
        handler.process(self.get_command_iter(old_path, new_path))
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_renamed=[(old_path, new_path)])
        self.assertRevisionRoot(revtree1, old_path)
        self.assertRevisionRoot(revtree2, new_path)

    def test_rename_symlink_in_root(self):
        handler, branch = self.get_handler()
        old_path = 'a'
        new_path = 'b'
        handler.process(self.get_command_iter(old_path, new_path, 'symlink'))
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_renamed=[(old_path, new_path)])
        self.assertRevisionRoot(revtree1, old_path)
        self.assertRevisionRoot(revtree2, new_path)

    def test_rename_file_in_subdir(self):
        handler, branch = self.get_handler()
        old_path = 'a/a'
        new_path = 'a/b'
        handler.process(self.get_command_iter(old_path, new_path))
        self.assertChanges(branch, 2, expected_renamed=[(old_path, new_path)])

    def test_rename_symlink_in_subdir(self):
        handler, branch = self.get_handler()
        old_path = 'a/a'
        new_path = 'a/b'
        handler.process(self.get_command_iter(old_path, new_path, 'symlink'))
        self.assertChanges(branch, 2, expected_renamed=[(old_path, new_path)])

    def test_rename_file_to_new_dir(self):
        handler, branch = self.get_handler()
        old_path = 'a/a'
        new_path = 'b/a'
        handler.process(self.get_command_iter(old_path, new_path))
        self.assertChanges(branch, 2,
            expected_renamed=[(old_path, new_path)],
            expected_added=[('b',)],
            expected_removed=[('a',)])

    def test_rename_symlink_to_new_dir(self):
        handler, branch = self.get_handler()
        old_path = 'a/a'
        new_path = 'b/a'
        handler.process(self.get_command_iter(old_path, new_path, 'symlink'))
        self.assertChanges(branch, 2,
            expected_renamed=[(old_path, new_path)],
            expected_added=[('b',)],
            expected_removed=[('a',)])


class TestImportToPackRenameNew(TestCaseForGenericProcessor):
    """Test rename of a newly added file."""

    def get_command_iter(self, old_path, new_path, kind='file'):
        # Revno 1: create a file and rename it
        def command_list():
            author = ['', 'bugs@a.com', time.time(), time.timezone]
            committer = ['', 'elmer@a.com', time.time(), time.timezone]
            def files_one():
                yield commands.FileModifyCommand(old_path, kind, False,
                        None, "aaa")
                yield commands.FileRenameCommand(old_path, new_path)
            yield commands.CommitCommand('head', '1', author,
                committer, "commit 1", None, [], files_one)
        return command_list

    def test_rename_new_file_in_root(self):
        handler, branch = self.get_handler()
        old_path = 'a'
        new_path = 'b'
        handler.process(self.get_command_iter(old_path, new_path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[(new_path,)])
        self.assertRevisionRoot(revtree1, new_path)

    def test_rename_new_symlink_in_root(self):
        handler, branch = self.get_handler()
        old_path = 'a'
        new_path = 'b'
        handler.process(self.get_command_iter(old_path, new_path, 'symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[(new_path,)])
        self.assertRevisionRoot(revtree1, new_path)

    def test_rename_new_file_in_subdir(self):
        handler, branch = self.get_handler()
        old_path = 'a/a'
        new_path = 'a/b'
        handler.process(self.get_command_iter(old_path, new_path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (new_path,)])

    def test_rename_new_symlink_in_subdir(self):
        handler, branch = self.get_handler()
        old_path = 'a/a'
        new_path = 'a/b'
        handler.process(self.get_command_iter(old_path, new_path, 'symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (new_path,)])


class TestImportToPackRenameToDeleted(TestCaseForGenericProcessor):
    """Test rename to a destination path deleted in this commit."""

    def get_command_iter(self, old_path, new_path, kind='file'):
        # Revno 1: create two files
        # Revno 2: delete one, rename the other one to that path
        def command_list():
            author = ['', 'bugs@a.com', time.time(), time.timezone]
            committer = ['', 'elmer@a.com', time.time(), time.timezone]
            def files_one():
                yield commands.FileModifyCommand(old_path, kind, False,
                        None, "aaa")
                yield commands.FileModifyCommand(new_path, kind, False,
                        None, "bbb")
            yield commands.CommitCommand('head', '1', author,
                committer, "commit 1", None, [], files_one)
            def files_two():
                yield commands.FileDeleteCommand(new_path)
                yield commands.FileRenameCommand(old_path, new_path)
            yield commands.CommitCommand('head', '2', author,
                committer, "commit 2", ":1", [], files_two)
        return command_list

    def test_rename_to_deleted_file_in_root(self):
        handler, branch = self.get_handler()
        old_path = 'a'
        new_path = 'b'
        handler.process(self.get_command_iter(old_path, new_path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[(old_path,), (new_path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[(new_path,)],
            expected_renamed=[(old_path, new_path)])
        self.assertContent(branch, revtree1, old_path, "aaa")
        self.assertContent(branch, revtree1, new_path, "bbb")
        self.assertContent(branch, revtree2, new_path, "aaa")
        self.assertRevisionRoot(revtree1, old_path)
        self.assertRevisionRoot(revtree1, new_path)

    def test_rename_to_deleted_symlink_in_root(self):
        handler, branch = self.get_handler()
        old_path = 'a'
        new_path = 'b'
        handler.process(self.get_command_iter(old_path, new_path, 'symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[(old_path,), (new_path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[(new_path,)],
            expected_renamed=[(old_path, new_path)])
        self.assertSymlinkTarget(branch, revtree1, old_path, "aaa")
        self.assertSymlinkTarget(branch, revtree1, new_path, "bbb")
        self.assertSymlinkTarget(branch, revtree2, new_path, "aaa")
        self.assertRevisionRoot(revtree1, old_path)
        self.assertRevisionRoot(revtree1, new_path)

    def test_rename_to_deleted_file_in_subdir(self):
        handler, branch = self.get_handler()
        old_path = 'd/a'
        new_path = 'd/b'
        handler.process(self.get_command_iter(old_path, new_path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('d',), (old_path,), (new_path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[(new_path,)],
            expected_renamed=[(old_path, new_path)])
        self.assertContent(branch, revtree1, old_path, "aaa")
        self.assertContent(branch, revtree1, new_path, "bbb")
        self.assertContent(branch, revtree2, new_path, "aaa")

    def test_rename_to_deleted_symlink_in_subdir(self):
        handler, branch = self.get_handler()
        old_path = 'd/a'
        new_path = 'd/b'
        handler.process(self.get_command_iter(old_path, new_path, 'symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('d',), (old_path,), (new_path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[(new_path,)],
            expected_renamed=[(old_path, new_path)])
        self.assertSymlinkTarget(branch, revtree1, old_path, "aaa")
        self.assertSymlinkTarget(branch, revtree1, new_path, "bbb")
        self.assertSymlinkTarget(branch, revtree2, new_path, "aaa")

    def test_rename_to_deleted_file_in_new_dir(self):
        handler, branch = self.get_handler()
        old_path = 'd1/a'
        new_path = 'd2/b'
        handler.process(self.get_command_iter(old_path, new_path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('d1',), (old_path,), ('d2',), (new_path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[('d1',), (new_path,)],
            expected_renamed=[(old_path, new_path)])
        self.assertContent(branch, revtree1, old_path, "aaa")
        self.assertContent(branch, revtree1, new_path, "bbb")
        self.assertContent(branch, revtree2, new_path, "aaa")

    def test_rename_to_deleted_symlink_in_new_dir(self):
        handler, branch = self.get_handler()
        old_path = 'd1/a'
        new_path = 'd2/b'
        handler.process(self.get_command_iter(old_path, new_path, 'symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('d1',), (old_path,), ('d2',), (new_path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[('d1',), (new_path,)],
            expected_renamed=[(old_path, new_path)])
        self.assertSymlinkTarget(branch, revtree1, old_path, "aaa")
        self.assertSymlinkTarget(branch, revtree1, new_path, "bbb")
        self.assertSymlinkTarget(branch, revtree2, new_path, "aaa")


class TestImportToPackRenameModified(TestCaseForGenericProcessor):
    """Test rename of a path previously modified in this commit."""

    def get_command_iter(self, old_path, new_path, kind='file'):
        # Revno 1: create a file or symlink
        # Revno 2: modify then rename it
        def command_list():
            author = ['', 'bugs@a.com', time.time(), time.timezone]
            committer = ['', 'elmer@a.com', time.time(), time.timezone]
            def files_one():
                yield commands.FileModifyCommand(old_path, kind, False,
                        None, "aaa")
            yield commands.CommitCommand('head', '1', author,
                committer, "commit 1", None, [], files_one)
            def files_two():
                yield commands.FileModifyCommand(old_path, kind, False,
                        None, "bbb")
                yield commands.FileRenameCommand(old_path, new_path)
            yield commands.CommitCommand('head', '2', author,
                committer, "commit 2", ":1", [], files_two)
        return command_list

    def test_rename_of_modified_file_in_root(self):
        handler, branch = self.get_handler()
        old_path = 'a'
        new_path = 'b'
        handler.process(self.get_command_iter(old_path, new_path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[(old_path,)])
        # Note: the delta doesn't show the modification?
        # The actual new content is validated in the assertions following.
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_renamed=[(old_path, new_path)])
        self.assertContent(branch, revtree1, old_path, "aaa")
        self.assertContent(branch, revtree2, new_path, "bbb")
        self.assertRevisionRoot(revtree1, old_path)
        self.assertRevisionRoot(revtree2, new_path)

    def test_rename_of_modified_symlink_in_root(self):
        handler, branch = self.get_handler()
        old_path = 'a'
        new_path = 'b'
        handler.process(self.get_command_iter(old_path, new_path, 'symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[(old_path,)])
        # Note: the delta doesn't show the modification?
        # The actual new content is validated in the assertions following.
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_renamed=[(old_path, new_path)])
        self.assertSymlinkTarget(branch, revtree1, old_path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, new_path, "bbb")
        self.assertRevisionRoot(revtree1, old_path)
        self.assertRevisionRoot(revtree2, new_path)

    def test_rename_of_modified_file_in_subdir(self):
        handler, branch = self.get_handler()
        old_path = 'd/a'
        new_path = 'd/b'
        handler.process(self.get_command_iter(old_path, new_path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('d',), (old_path,)])
        # Note: the delta doesn't show the modification?
        # The actual new content is validated in the assertions following.
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_renamed=[(old_path, new_path)])
        self.assertContent(branch, revtree1, old_path, "aaa")
        self.assertContent(branch, revtree2, new_path, "bbb")

    def test_rename_of_modified_symlink_in_subdir(self):
        handler, branch = self.get_handler()
        old_path = 'd/a'
        new_path = 'd/b'
        handler.process(self.get_command_iter(old_path, new_path, 'symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('d',), (old_path,)])
        # Note: the delta doesn't show the modification?
        # The actual new content is validated in the assertions following.
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_renamed=[(old_path, new_path)])
        self.assertSymlinkTarget(branch, revtree1, old_path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, new_path, "bbb")

    def test_rename_of_modified_file_to_new_dir(self):
        handler, branch = self.get_handler()
        old_path = 'd1/a'
        new_path = 'd2/b'
        handler.process(self.get_command_iter(old_path, new_path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('d1',), (old_path,)])
        # Note: the delta doesn't show the modification?
        # The actual new content is validated in the assertions following.
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_renamed=[(old_path, new_path)],
            expected_added=[('d2',)],
            expected_removed=[('d1',)])
        self.assertContent(branch, revtree1, old_path, "aaa")
        self.assertContent(branch, revtree2, new_path, "bbb")

    def test_rename_of_modified_symlink_to_new_dir(self):
        handler, branch = self.get_handler()
        old_path = 'd1/a'
        new_path = 'd2/b'
        handler.process(self.get_command_iter(old_path, new_path, 'symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('d1',), (old_path,)])
        # Note: the delta doesn't show the modification?
        # The actual new content is validated in the assertions following.
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_renamed=[(old_path, new_path)],
            expected_added=[('d2',)],
            expected_removed=[('d1',)])
        self.assertSymlinkTarget(branch, revtree1, old_path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, new_path, "bbb")


class TestImportToPackRenameTricky(TestCaseForGenericProcessor):

    def file_command_iter(self, path1, old_path2, new_path2, kind='file'):
        # Revno 1: create two files or symlinks in a directory
        # Revno 2: rename the second file so that it implicitly deletes the
        # first one because either:
        # * the new file is a in directory with the old file name
        # * the new file has the same name as the directory of the first
        def command_list():
            author = ['', 'bugs@a.com', time.time(), time.timezone]
            committer = ['', 'elmer@a.com', time.time(), time.timezone]
            def files_one():
                yield commands.FileModifyCommand(path1, kind, False,
                        None, "aaa")
                yield commands.FileModifyCommand(old_path2, kind, False,
                        None, "bbb")
            yield commands.CommitCommand('head', '1', author,
                committer, "commit 1", None, [], files_one)
            def files_two():
                yield commands.FileRenameCommand(old_path2, new_path2)
            yield commands.CommitCommand('head', '2', author,
                committer, "commit 2", ":1", [], files_two)
        return command_list

    def test_rename_file_becomes_directory(self):
        handler, branch = self.get_handler()
        old_path2 = 'foo'
        path1     = 'a/b'
        new_path2 = 'a/b/c'
        handler.process(self.file_command_iter(path1, old_path2, new_path2))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (path1,), (old_path2,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_renamed=[(old_path2, new_path2)],
            expected_kind_changed=[(path1, 'file', 'directory')])
        self.assertContent(branch, revtree1, path1, "aaa")
        self.assertContent(branch, revtree2, new_path2, "bbb")

    def test_rename_directory_becomes_file(self):
        handler, branch = self.get_handler()
        old_path2 = 'foo'
        path1     = 'a/b/c'
        new_path2 = 'a/b'
        handler.process(self.file_command_iter(path1, old_path2, new_path2))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), ('a/b',), (path1,), (old_path2,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_renamed=[(old_path2, new_path2)],
            expected_removed=[(path1,), (new_path2,)])
        self.assertContent(branch, revtree1, path1, "aaa")
        self.assertContent(branch, revtree2, new_path2, "bbb")

    def test_rename_symlink_becomes_directory(self):
        handler, branch = self.get_handler()
        old_path2 = 'foo'
        path1     = 'a/b'
        new_path2 = 'a/b/c'
        handler.process(self.file_command_iter(path1, old_path2, new_path2,
            'symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (path1,), (old_path2,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_renamed=[(old_path2, new_path2)],
            expected_kind_changed=[(path1, 'symlink', 'directory')])
        self.assertSymlinkTarget(branch, revtree1, path1, "aaa")
        self.assertSymlinkTarget(branch, revtree2, new_path2, "bbb")

    def test_rename_directory_becomes_symlink(self):
        handler, branch = self.get_handler()
        old_path2 = 'foo'
        path1     = 'a/b/c'
        new_path2 = 'a/b'
        handler.process(self.file_command_iter(path1, old_path2, new_path2,
            'symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), ('a/b',), (path1,), (old_path2,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_renamed=[(old_path2, new_path2)],
            expected_removed=[(path1,), (new_path2,)])
        self.assertSymlinkTarget(branch, revtree1, path1, "aaa")
        self.assertSymlinkTarget(branch, revtree2, new_path2, "bbb")


class TestImportToPackCopy(TestCaseForGenericProcessor):

    def file_command_iter(self, src_path, dest_path, kind='file'):
        # Revno 1: create a file or symlink
        # Revno 2: copy it
        def command_list():
            author = ['', 'bugs@a.com', time.time(), time.timezone]
            committer = ['', 'elmer@a.com', time.time(), time.timezone]
            def files_one():
                yield commands.FileModifyCommand(src_path, kind, False,
                        None, "aaa")
            yield commands.CommitCommand('head', '1', author,
                committer, "commit 1", None, [], files_one)
            def files_two():
                yield commands.FileCopyCommand(src_path, dest_path)
            yield commands.CommitCommand('head', '2', author,
                committer, "commit 2", ":1", [], files_two)
        return command_list

    def test_copy_file_in_root(self):
        handler, branch = self.get_handler()
        src_path = 'a'
        dest_path = 'b'
        handler.process(self.file_command_iter(src_path, dest_path))
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_added=[(dest_path,)])
        self.assertContent(branch, revtree1, src_path, "aaa")
        self.assertContent(branch, revtree2, src_path, "aaa")
        self.assertContent(branch, revtree2, dest_path, "aaa")
        self.assertRevisionRoot(revtree1, src_path)
        self.assertRevisionRoot(revtree2, dest_path)

    def test_copy_file_in_subdir(self):
        handler, branch = self.get_handler()
        src_path = 'a/a'
        dest_path = 'a/b'
        handler.process(self.file_command_iter(src_path, dest_path))
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_added=[(dest_path,)])
        self.assertContent(branch, revtree1, src_path, "aaa")
        self.assertContent(branch, revtree2, src_path, "aaa")
        self.assertContent(branch, revtree2, dest_path, "aaa")

    def test_copy_file_to_new_dir(self):
        handler, branch = self.get_handler()
        src_path = 'a/a'
        dest_path = 'b/a'
        handler.process(self.file_command_iter(src_path, dest_path))
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_added=[('b',), (dest_path,)])
        self.assertContent(branch, revtree1, src_path, "aaa")
        self.assertContent(branch, revtree2, src_path, "aaa")
        self.assertContent(branch, revtree2, dest_path, "aaa")

    def test_copy_symlink_in_root(self):
        handler, branch = self.get_handler()
        src_path = 'a'
        dest_path = 'b'
        handler.process(self.file_command_iter(src_path, dest_path, 'symlink'))
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_added=[(dest_path,)])
        self.assertSymlinkTarget(branch, revtree1, src_path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, src_path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, dest_path, "aaa")
        self.assertRevisionRoot(revtree1, src_path)
        self.assertRevisionRoot(revtree2, dest_path)

    def test_copy_symlink_in_subdir(self):
        handler, branch = self.get_handler()
        src_path = 'a/a'
        dest_path = 'a/b'
        handler.process(self.file_command_iter(src_path, dest_path, 'symlink'))
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_added=[(dest_path,)])
        self.assertSymlinkTarget(branch, revtree1, src_path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, src_path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, dest_path, "aaa")

    def test_copy_symlink_to_new_dir(self):
        handler, branch = self.get_handler()
        src_path = 'a/a'
        dest_path = 'b/a'
        handler.process(self.file_command_iter(src_path, dest_path, 'symlink'))
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_added=[('b',), (dest_path,)])
        self.assertSymlinkTarget(branch, revtree1, src_path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, src_path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, dest_path, "aaa")


class TestImportToPackCopyNew(TestCaseForGenericProcessor):
    """Test copy of a newly added file."""

    def file_command_iter(self, src_path, dest_path, kind='file'):
        # Revno 1: create a file or symlink and copy it
        def command_list():
            author = ['', 'bugs@a.com', time.time(), time.timezone]
            committer = ['', 'elmer@a.com', time.time(), time.timezone]
            def files_one():
                yield commands.FileModifyCommand(src_path, kind, False,
                        None, "aaa")
                yield commands.FileCopyCommand(src_path, dest_path)
            yield commands.CommitCommand('head', '1', author,
                committer, "commit 1", None, [], files_one)
        return command_list

    def test_copy_new_file_in_root(self):
        handler, branch = self.get_handler()
        src_path = 'a'
        dest_path = 'b'
        handler.process(self.file_command_iter(src_path, dest_path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[(src_path,), (dest_path,)])
        self.assertContent(branch, revtree1, src_path, "aaa")
        self.assertContent(branch, revtree1, dest_path, "aaa")
        self.assertRevisionRoot(revtree1, src_path)
        self.assertRevisionRoot(revtree1, dest_path)

    def test_copy_new_file_in_subdir(self):
        handler, branch = self.get_handler()
        src_path = 'a/a'
        dest_path = 'a/b'
        handler.process(self.file_command_iter(src_path, dest_path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (src_path,), (dest_path,)])
        self.assertContent(branch, revtree1, src_path, "aaa")
        self.assertContent(branch, revtree1, dest_path, "aaa")

    def test_copy_new_file_to_new_dir(self):
        handler, branch = self.get_handler()
        src_path = 'a/a'
        dest_path = 'b/a'
        handler.process(self.file_command_iter(src_path, dest_path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (src_path,), ('b',), (dest_path,)])
        self.assertContent(branch, revtree1, src_path, "aaa")
        self.assertContent(branch, revtree1, dest_path, "aaa")

    def test_copy_new_symlink_in_root(self):
        handler, branch = self.get_handler()
        src_path = 'a'
        dest_path = 'b'
        handler.process(self.file_command_iter(src_path, dest_path, 'symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[(src_path,), (dest_path,)])
        self.assertSymlinkTarget(branch, revtree1, src_path, "aaa")
        self.assertSymlinkTarget(branch, revtree1, dest_path, "aaa")
        self.assertRevisionRoot(revtree1, src_path)
        self.assertRevisionRoot(revtree1, dest_path)

    def test_copy_new_symlink_in_subdir(self):
        handler, branch = self.get_handler()
        src_path = 'a/a'
        dest_path = 'a/b'
        handler.process(self.file_command_iter(src_path, dest_path, 'symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (src_path,), (dest_path,)])
        self.assertSymlinkTarget(branch, revtree1, src_path, "aaa")
        self.assertSymlinkTarget(branch, revtree1, dest_path, "aaa")

    def test_copy_new_symlink_to_new_dir(self):
        handler, branch = self.get_handler()
        src_path = 'a/a'
        dest_path = 'b/a'
        handler.process(self.file_command_iter(src_path, dest_path, 'symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('a',), (src_path,), ('b',), (dest_path,)])
        self.assertSymlinkTarget(branch, revtree1, src_path, "aaa")
        self.assertSymlinkTarget(branch, revtree1, dest_path, "aaa")


class TestImportToPackCopyToDeleted(TestCaseForGenericProcessor):

    def file_command_iter(self, src_path, dest_path, kind='file'):
        # Revno 1: create two files or symlinks
        # Revno 2: delete one and copy the other one to its path
        def command_list():
            author = ['', 'bugs@a.com', time.time(), time.timezone]
            committer = ['', 'elmer@a.com', time.time(), time.timezone]
            def files_one():
                yield commands.FileModifyCommand(src_path, kind, False,
                        None, "aaa")
                yield commands.FileModifyCommand(dest_path, kind, False,
                        None, "bbb")
            yield commands.CommitCommand('head', '1', author,
                committer, "commit 1", None, [], files_one)
            def files_two():
                yield commands.FileDeleteCommand(dest_path)
                yield commands.FileCopyCommand(src_path, dest_path)
            yield commands.CommitCommand('head', '2', author,
                committer, "commit 2", ":1", [], files_two)
        return command_list

    def test_copy_to_deleted_file_in_root(self):
        handler, branch = self.get_handler()
        src_path = 'a'
        dest_path = 'b'
        handler.process(self.file_command_iter(src_path, dest_path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[(src_path,), (dest_path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[(dest_path,)],
            expected_added=[(dest_path,)])
        self.assertContent(branch, revtree1, src_path, "aaa")
        self.assertContent(branch, revtree1, dest_path, "bbb")
        self.assertContent(branch, revtree2, src_path, "aaa")
        self.assertContent(branch, revtree2, dest_path, "aaa")
        self.assertRevisionRoot(revtree1, src_path)
        self.assertRevisionRoot(revtree1, dest_path)

    def test_copy_to_deleted_symlink_in_root(self):
        handler, branch = self.get_handler()
        src_path = 'a'
        dest_path = 'b'
        handler.process(self.file_command_iter(src_path, dest_path, 'symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[(src_path,), (dest_path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[(dest_path,)],
            expected_added=[(dest_path,)])
        self.assertSymlinkTarget(branch, revtree1, src_path, "aaa")
        self.assertSymlinkTarget(branch, revtree1, dest_path, "bbb")
        self.assertSymlinkTarget(branch, revtree2, src_path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, dest_path, "aaa")
        self.assertRevisionRoot(revtree1, src_path)
        self.assertRevisionRoot(revtree1, dest_path)

    def test_copy_to_deleted_file_in_subdir(self):
        handler, branch = self.get_handler()
        src_path = 'd/a'
        dest_path = 'd/b'
        handler.process(self.file_command_iter(src_path, dest_path))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('d',), (src_path,), (dest_path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[(dest_path,)],
            expected_added=[(dest_path,)])
        self.assertContent(branch, revtree1, src_path, "aaa")
        self.assertContent(branch, revtree1, dest_path, "bbb")
        self.assertContent(branch, revtree2, src_path, "aaa")
        self.assertContent(branch, revtree2, dest_path, "aaa")

    def test_copy_to_deleted_symlink_in_subdir(self):
        handler, branch = self.get_handler()
        src_path = 'd/a'
        dest_path = 'd/b'
        handler.process(self.file_command_iter(src_path, dest_path, 'symlink'))
        revtree0, revtree1 = self.assertChanges(branch, 1,
            expected_added=[('d',), (src_path,), (dest_path,)])
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_removed=[(dest_path,)],
            expected_added=[(dest_path,)])
        self.assertSymlinkTarget(branch, revtree1, src_path, "aaa")
        self.assertSymlinkTarget(branch, revtree1, dest_path, "bbb")
        self.assertSymlinkTarget(branch, revtree2, src_path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, dest_path, "aaa")


class TestImportToPackCopyModified(TestCaseForGenericProcessor):
    """Test copy of file/symlink already modified in this commit."""

    def file_command_iter(self, src_path, dest_path, kind='file'):
        # Revno 1: create a file or symlink
        # Revno 2: modify and copy it
        def command_list():
            author = ['', 'bugs@a.com', time.time(), time.timezone]
            committer = ['', 'elmer@a.com', time.time(), time.timezone]
            def files_one():
                yield commands.FileModifyCommand(src_path, kind, False,
                        None, "aaa")
            yield commands.CommitCommand('head', '1', author,
                committer, "commit 1", None, [], files_one)
            def files_two():
                yield commands.FileModifyCommand(src_path, kind, False,
                        None, "bbb")
                yield commands.FileCopyCommand(src_path, dest_path)
            yield commands.CommitCommand('head', '2', author,
                committer, "commit 2", ":1", [], files_two)
        return command_list

    def test_copy_of_modified_file_in_root(self):
        handler, branch = self.get_handler()
        src_path = 'a'
        dest_path = 'b'
        handler.process(self.file_command_iter(src_path, dest_path))
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_modified=[(src_path,)],
            expected_added=[(dest_path,)])
        self.assertContent(branch, revtree1, src_path, "aaa")
        self.assertContent(branch, revtree2, src_path, "bbb")
        self.assertContent(branch, revtree2, dest_path, "bbb")
        self.assertRevisionRoot(revtree1, src_path)
        self.assertRevisionRoot(revtree2, dest_path)

    def test_copy_of_modified_file_in_subdir(self):
        handler, branch = self.get_handler()
        src_path = 'd/a'
        dest_path = 'd/b'
        handler.process(self.file_command_iter(src_path, dest_path))
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_modified=[(src_path,)],
            expected_added=[(dest_path,)])
        self.assertContent(branch, revtree1, src_path, "aaa")
        self.assertContent(branch, revtree2, src_path, "bbb")
        self.assertContent(branch, revtree2, dest_path, "bbb")

    def test_copy_of_modified_file_to_new_dir(self):
        handler, branch = self.get_handler()
        src_path = 'd1/a'
        dest_path = 'd2/a'
        handler.process(self.file_command_iter(src_path, dest_path))
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_modified=[(src_path,)],
            expected_added=[('d2',), (dest_path,)])
        self.assertContent(branch, revtree1, src_path, "aaa")
        self.assertContent(branch, revtree2, src_path, "bbb")
        self.assertContent(branch, revtree2, dest_path, "bbb")

    def test_copy_of_modified_symlink_in_root(self):
        handler, branch = self.get_handler()
        src_path = 'a'
        dest_path = 'b'
        handler.process(self.file_command_iter(src_path, dest_path, 'symlink'))
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_modified=[(src_path,)],
            expected_added=[(dest_path,)])
        self.assertSymlinkTarget(branch, revtree1, src_path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, src_path, "bbb")
        self.assertSymlinkTarget(branch, revtree2, dest_path, "bbb")
        self.assertRevisionRoot(revtree1, src_path)
        self.assertRevisionRoot(revtree2, dest_path)

    def test_copy_of_modified_symlink_in_subdir(self):
        handler, branch = self.get_handler()
        src_path = 'd/a'
        dest_path = 'd/b'
        handler.process(self.file_command_iter(src_path, dest_path, 'symlink'))
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_modified=[(src_path,)],
            expected_added=[(dest_path,)])
        self.assertSymlinkTarget(branch, revtree1, src_path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, src_path, "bbb")
        self.assertSymlinkTarget(branch, revtree2, dest_path, "bbb")

    def test_copy_of_modified_symlink_to_new_dir(self):
        handler, branch = self.get_handler()
        src_path = 'd1/a'
        dest_path = 'd2/a'
        handler.process(self.file_command_iter(src_path, dest_path, 'symlink'))
        revtree1, revtree2 = self.assertChanges(branch, 2,
            expected_modified=[(src_path,)],
            expected_added=[('d2',), (dest_path,)])
        self.assertSymlinkTarget(branch, revtree1, src_path, "aaa")
        self.assertSymlinkTarget(branch, revtree2, src_path, "bbb")
        self.assertSymlinkTarget(branch, revtree2, dest_path, "bbb")


class TestImportToPackFileKinds(TestCaseForGenericProcessor):

    def get_command_iter(self, path, kind, content):
        def command_list():
            committer = ['', 'elmer@a.com', time.time(), time.timezone]
            def files_one():
                yield commands.FileModifyCommand(path, kind, False,
                        None, content)
            yield commands.CommitCommand('head', '1', None,
                committer, "commit 1", None, [], files_one)
        return command_list

    def test_import_plainfile(self):
        handler, branch = self.get_handler()
        handler.process(self.get_command_iter('foo', 'file', 'aaa'))

    def test_import_symlink(self):
        handler, branch = self.get_handler()
        handler.process(self.get_command_iter('foo', 'symlink', 'bar'))


### TODO: Parameterise tests rather than below hack

class TestImportToRichRootModify(TestImportToPackModify):
    branch_format = "1.9-rich-root"

class TestImportToRichRootModifyTwice(TestImportToPackModifyTwice):
    branch_format = "1.9-rich-root"

class TestImportToRichRootModifyTricky(TestImportToPackModifyTricky):
    branch_format = "1.9-rich-root"

class TestImportToRichRootDelete(TestImportToPackDelete):
    branch_format = "1.9-rich-root"

class TestImportToRichRootDeleteNew(TestImportToPackDeleteNew):
    branch_format = "1.9-rich-root"

class TestImportToRichRootDeleteThenAdd(TestImportToPackDeleteThenAdd):
    branch_format = "1.9-rich-root"

class TestImportToRichRootDeleteDirectory(TestImportToPackDeleteDirectory):
    branch_format = "1.9-rich-root"

class TestImportToRichRootRename(TestImportToPackRename):
    branch_format = "1.9-rich-root"

class TestImportToRichRootRenameNew(TestImportToPackRenameNew):
    branch_format = "1.9-rich-root"

class TestImportToRichRootRenameToDeleted(TestImportToPackRenameToDeleted):
    branch_format = "1.9-rich-root"

class TestImportToRichRootRenameModified(TestImportToPackRenameModified):
    branch_format = "1.9-rich-root"

class TestImportToRichRootRenameTricky(TestImportToPackRenameTricky):
    branch_format = "1.9-rich-root"

class TestImportToRichRootCopy(TestImportToPackCopy):
    branch_format = "1.9-rich-root"

class TestImportToRichRootCopyNew(TestImportToPackCopyNew):
    branch_format = "1.9-rich-root"

class TestImportToRichRootCopyToDeleted(TestImportToPackCopyToDeleted):
    branch_format = "1.9-rich-root"

class TestImportToRichRootCopyModified(TestImportToPackCopyModified):
    branch_format = "1.9-rich-root"

class TestImportToRichRootFileKinds(TestImportToPackFileKinds):
    branch_format = "1.9-rich-root"

try:
    from bzrlib.repofmt.groupcompress_repo import RepositoryFormat2a

    class TestImportToChkModify(TestImportToPackModify):
        branch_format = "2a"

    class TestImportToChkModifyTwice(TestImportToPackModifyTwice):
        branch_format = "2a"

    class TestImportToChkModifyTricky(TestImportToPackModifyTricky):
        branch_format = "2a"

    class TestImportToChkDelete(TestImportToPackDelete):
        branch_format = "2a"

    class TestImportToChkDeleteNew(TestImportToPackDeleteNew):
        branch_format = "2a"

    class TestImportToChkDeleteThenAdd(TestImportToPackDeleteThenAdd):
        branch_format = "2a"

    class TestImportToChkDeleteDirectory(TestImportToPackDeleteDirectory):
        branch_format = "2a"

    class TestImportToChkRename(TestImportToPackRename):
        branch_format = "2a"

    class TestImportToChkRenameNew(TestImportToPackRenameNew):
        branch_format = "2a"

    class TestImportToChkRenameToDeleted(TestImportToPackRenameToDeleted):
        branch_format = "2a"

    class TestImportToChkRenameModified(TestImportToPackRenameModified):
        branch_format = "2a"

    class TestImportToChkRenameTricky(TestImportToPackRenameTricky):
        branch_format = "2a"

    class TestImportToChkCopy(TestImportToPackCopy):
        branch_format = "2a"

    class TestImportToChkCopyNew(TestImportToPackCopyNew):
        branch_format = "2a"

    class TestImportToChkCopyToDeleted(TestImportToPackCopyToDeleted):
        branch_format = "2a"

    class TestImportToChkCopyModified(TestImportToPackCopyModified):
        branch_format = "2a"

    class TestImportToChkFileKinds(TestImportToPackFileKinds):
        branch_format = "2a"

except ImportError:
    pass
