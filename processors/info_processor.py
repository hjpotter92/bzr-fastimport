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

"""Import processor that dump stats about the input (and doesn't import)."""


from bzrlib.trace import (
    note,
    warning,
    )
from bzrlib.plugins.fastimport import (
    cache_manager,
    commands,
    helpers,
    processor,
    )


class InfoProcessor(processor.ImportProcessor):
    """An import processor that dumps statistics about the input.

    No changes to the current repository are made.

    As well as providing useful information about an import
    stream before importing it, this processor is useful for
    benchmarking the speed at which data can be extracted from
    the source.
    """

    def __init__(self, target=None, params=None, verbose=0, outf=None):
        # Allow creation without a target
        processor.ImportProcessor.__init__(self, target, params, verbose,
            outf=outf)

    def pre_process(self):
        self.note("Collecting statistics ...")
        # Init statistics
        self.cmd_counts = {}
        for cmd in commands.COMMAND_NAMES:
            self.cmd_counts[cmd] = 0
        self.file_cmd_counts = {}
        for fc in commands.FILE_COMMAND_NAMES:
            self.file_cmd_counts[fc] = 0
        self.parent_counts = {}
        self.max_parent_count = 0
        self.committers = set()
        self.separate_authors_found = False
        self.symlinks_found = False
        self.executables_found = False
        self.sha_blob_references = False
        self.lightweight_tags = 0
        # Blob usage tracking
        self.blobs = {}
        for usage in ['new', 'used', 'unknown', 'unmarked']:
            self.blobs[usage] = set()
        self.blob_ref_counts = {}
        # Head tracking - delegate to the cache manager
        self.cache_mgr = cache_manager.CacheManager(inventory_cache_size=0)
        # Stuff to cache: a map from mark to # of times that mark is merged
        self.merges = {}
        # Stuff to cache: these are maps from mark to sets
        self.rename_old_paths = {}
        self.copy_source_paths = {}

    def post_process(self):
        # Dump statistics
        cmd_names = commands.COMMAND_NAMES
        fc_names = commands.FILE_COMMAND_NAMES
        cmd_values = [self.cmd_counts[c] for c in cmd_names]
        fc_values = [self.file_cmd_counts[c] for c in fc_names]
        self._dump_stats_group("Command counts", cmd_names, cmd_values, str)
        self._dump_stats_group("File command counts", fc_names, fc_values, str)

        # Commit stats
        if self.cmd_counts['commit']:
            p_names = []
            p_values = []
            for i in xrange(0, self.max_parent_count + 1):
                if i in self.parent_counts:
                    count = self.parent_counts[i]
                    p_names.append("parents-%d" % i)
                    p_values.append(count)
            merges_count = len(self.merges.keys())
            p_names.append('total revisions merged')
            p_values.append(merges_count)
            flags = {
                'separate authors found': self.separate_authors_found,
                'executables': self.executables_found,
                'symlinks': self.symlinks_found,
                'blobs referenced by SHA': self.sha_blob_references,
                }
            self._dump_stats_group("Parent counts", p_names, p_values, str)
            self._dump_stats_group("Commit analysis", flags.keys(),
                flags.values(), _found)
            heads = helpers.invert_dictset(self.cache_mgr.heads)
            self._dump_stats_group("Head analysis", heads.keys(),
                heads.values(), None, _iterable_as_config_list)
            # note("\t%d\t%s" % (len(self.committers), 'unique committers'))
            self._dump_stats_group("Merges", self.merges.keys(),
                self.merges.values(), None)
            # We only show the rename old path and copy source paths when -vv
            # (verbose=2) is specified. The output here for mysql's data can't
            # be parsed currently so this bit of code needs more work anyhow ..
            if self.verbose >= 2:
                self._dump_stats_group("Rename old paths",
                    self.rename_old_paths.keys(),
                    self.rename_old_paths.values(), len,
                    _iterable_as_config_list)
                self._dump_stats_group("Copy source paths",
                    self.copy_source_paths.keys(),
                    self.copy_source_paths.values(), len,
                    _iterable_as_config_list)

        # Blob stats
        if self.cmd_counts['blob']:
            # In verbose mode, don't list every blob used
            if self.verbose:
                del self.blobs['used']
            self._dump_stats_group("Blob usage tracking", self.blobs.keys(),
                self.blobs.values(), len, _iterable_as_config_list)
        if self.blob_ref_counts:
            blobs_by_count = helpers.invert_dict(self.blob_ref_counts)
            self._dump_stats_group("Blob reference counts",
                blobs_by_count.keys(),
                blobs_by_count.values(), len, _iterable_as_config_list)

        # Other stats
        if self.cmd_counts['reset']:
            reset_stats = {
                'lightweight tags': self.lightweight_tags,
                }
            self._dump_stats_group("Reset analysis", reset_stats.keys(),
                reset_stats.values())

    def _dump_stats_group(self, title, names, values, normal_formatter=None,
        verbose_formatter=None):
        """Dump a statistics group.
        
        In verbose mode, do so as a config file so
        that other processors can load the information if they want to.
        :param normal_formatter: the callable to apply to the value
          before displaying it in normal mode
        :param verbose_formatter: the callable to apply to the value
          before displaying it in verbose mode
        """
        if self.verbose:
            self.outf.write("[%s]\n" % (title,))
            for name, value in zip(names, values):
                if verbose_formatter is not None:
                    value = verbose_formatter(value)
                if type(name) == str:
                    name = name.replace(' ', '-')
                self.outf.write("%s = %s\n" % (name, value))
            self.outf.write("\n")
        else:
            self.outf.write("%s:\n" % (title,))
            for name, value in zip(names, values):
                if normal_formatter is not None:
                    value = normal_formatter(value)
                self.outf.write("\t%s\t%s\n" % (value, name))

    def progress_handler(self, cmd):
        """Process a ProgressCommand."""
        self.cmd_counts[cmd.name] += 1

    def blob_handler(self, cmd):
        """Process a BlobCommand."""
        self.cmd_counts[cmd.name] += 1
        if cmd.mark is None:
            self.blobs['unmarked'].add(cmd.id)
        else:
            self.blobs['new'].add(cmd.id)
            # Marks can be re-used so remove it from used if already there.
            # Note: we definitely do NOT want to remove it from multi if
            # it's already in that set.
            try:
                self.blobs['used'].remove(cmd.id)
            except KeyError:
                pass

    def checkpoint_handler(self, cmd):
        """Process a CheckpointCommand."""
        self.cmd_counts[cmd.name] += 1

    def commit_handler(self, cmd):
        """Process a CommitCommand."""
        self.cmd_counts[cmd.name] += 1
        self.committers.add(cmd.committer)
        if cmd.author is not None:
            self.separate_authors_found = True
        for fc in cmd.file_iter():
            self.file_cmd_counts[fc.name] += 1
            if isinstance(fc, commands.FileModifyCommand):
                if fc.is_executable:
                    self.executables_found = True
                if fc.kind == commands.SYMLINK_KIND:
                    self.symlinks_found = True
                if fc.dataref is not None:
                    if fc.dataref[0] == ':':
                        self._track_blob(fc.dataref)
                    else:
                        self.sha_blob_references = True
            elif isinstance(fc, commands.FileRenameCommand):
                self.rename_old_paths.setdefault(cmd.id, set()).add(fc.old_path)
            elif isinstance(fc, commands.FileCopyCommand):
                self.copy_source_paths.setdefault(cmd.id, set()).add(fc.src_path)

        # Track the heads
        parents = self.cache_mgr.track_heads(cmd)

        # Track the parent counts
        parent_count = len(parents)
        if self.parent_counts.has_key(parent_count):
            self.parent_counts[parent_count] += 1
        else:
            self.parent_counts[parent_count] = 1
            if parent_count > self.max_parent_count:
                self.max_parent_count = parent_count

        # Remember the merges
        if cmd.merges:
            #self.merges.setdefault(cmd.ref, set()).update(cmd.merges)
            for merge in cmd.merges:
                if merge in self.merges:
                    self.merges[merge] += 1
                else:
                    self.merges[merge] = 1

    def reset_handler(self, cmd):
        """Process a ResetCommand."""
        self.cmd_counts[cmd.name] += 1
        if cmd.ref.startswith('refs/tags/'):
            self.lightweight_tags += 1
        else:
            if cmd.from_ is not None:
                self.cache_mgr.track_heads_for_ref(cmd.ref, cmd.from_)

    def tag_handler(self, cmd):
        """Process a TagCommand."""
        self.cmd_counts[cmd.name] += 1

    def feature_handler(self, cmd):
        """Process a FeatureCommand."""
        self.cmd_counts[cmd.name] += 1
        self.warning("assuming feature %s is supported" % cmd.feature_name)

    def _track_blob(self, mark):
        if mark in self.blob_ref_counts:
            self.blob_ref_counts[mark] += 1
            pass
        elif mark in self.blobs['used']:
            self.blob_ref_counts[mark] = 2
            self.blobs['used'].remove(mark)
        elif mark in self.blobs['new']:
            self.blobs['used'].add(mark)
            self.blobs['new'].remove(mark)
        else:
            self.blobs['unknown'].add(mark)

def _found(b):
    """Format a found boolean as a string."""
    return ['no', 'found'][b]

def _iterable_as_config_list(s):
    """Format an iterable as a sequence of comma-separated strings.
    
    To match what ConfigObj expects, a single item list has a trailing comma.
    """
    items = sorted(s)
    if len(items) == 1:
        return "%s," % (items[0],)
    else:
        return ", ".join(items)
