# Copyright (C) 2009 Canonical Ltd
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

"""A manager of caches."""

import os
import shutil
import tempfile
import time

from bzrlib import lru_cache, trace
from bzrlib.plugins.fastimport import helpers


class _Cleanup(object):
    """This class makes sure we clean up when CacheManager goes away.

    We use a helper class to ensure that we are never in a refcycle.
    """

    def __init__(self, disk_blobs):
        self.disk_blobs = disk_blobs
        self.tempdir = None
        self.small_blobs = None

    def __del__(self):
        self.finalize()

    def finalize(self):
        if self.disk_blobs is not None:
            for info in self.disk_blobs.itervalues():
                if info[-1] is not None:
                    os.unlink(info[-1])
            self.disk_blobs = None
        if self.small_blobs is not None:
            self.small_blobs.close()
            self.small_blobs = None
        if self.tempdir is not None:
            shutils.rmtree(self.tempdir)
        

class CacheManager(object):
    
    _small_blob_threshold = 75*1024
    _sticky_cache_size = 300*1024*1024
    _sticky_flushed_size = 100*1024*1024

    def __init__(self, info=None, verbose=False, inventory_cache_size=10):
        """Create a manager of caches.

        :param info: a ConfigObj holding the output from
            the --info processor, or None if no hints are available
        """
        self.verbose = verbose

        # dataref -> data. datref is either :mark or the sha-1.
        # Sticky blobs are referenced more than once, and are saved until their
        # refcount goes to 0
        self._blobs = {}
        self._sticky_blobs = {}
        self._sticky_memory_bytes = 0
        # if we overflow our memory cache, then we will dump large blobs to
        # disk in this directory
        self._tempdir = None
        # id => (offset, n_bytes, fname)
        #   if fname is None, then the content is stored in the small file
        self._disk_blobs = {}
        self._cleanup = _Cleanup(self._disk_blobs)
        # atexit.register(self._cleanup.finalize)
        # The main problem is that it won't let cleanup go away 'normally', so
        # we really need a weakref callback...
        # Perhaps just registering the shutil.rmtree?

        # revision-id -> Inventory cache
        # these are large and we probably don't need too many as
        # most parents are recent in history
        self.inventories = lru_cache.LRUCache(inventory_cache_size)

        # import commmit-ids -> revision-id lookup table
        # we need to keep all of these but they are small
        self.revision_ids = {}

        # (path, branch_ref) -> file-ids - as generated.
        # (Use store_file_id/fetch_fileid methods rather than direct access.)

        # Head tracking: last ref, last id per ref & map of commit ids to ref*s*
        self.last_ref = None
        self.last_ids = {}
        self.heads = {}

        # Work out the blobs to make sticky - None means all
        self._blob_ref_counts = {}
        if info is not None:
            try:
                blobs_by_counts = info['Blob reference counts']
                # The parser hands values back as lists, already parsed
                for count, blob_list in blobs_by_counts.items():
                    n = int(count)
                    for b in blob_list:
                        self._blob_ref_counts[b] = n
            except KeyError:
                # info not in file - possible when no blobs used
                pass

    def dump_stats(self, note=trace.note):
        """Dump some statistics about what we cached."""
        # TODO: add in inventory stastistics
        note("Cache statistics:")
        self._show_stats_for(self._sticky_blobs, "sticky blobs", note=note)
        self._show_stats_for(self.revision_ids, "revision-ids", note=note)
        # These aren't interesting so omit from the output, at least for now
        #self._show_stats_for(self._blobs, "other blobs", note=note)
        #self._show_stats_for(self.last_ids, "last-ids", note=note)
        #self._show_stats_for(self.heads, "heads", note=note)

    def _show_stats_for(self, dict, label, note=trace.note, tuple_key=False):
        """Dump statistics about a given dictionary.

        By the key and value need to support len().
        """
        count = len(dict)
        if tuple_key:
            size = sum(map(len, (''.join(k) for k in dict.keys())))
        else:
            size = sum(map(len, dict.keys()))
        size += sum(map(len, dict.values()))
        size = size * 1.0 / 1024
        unit = 'K'
        if size > 1024:
            size = size / 1024
            unit = 'M'
            if size > 1024:
                size = size / 1024
                unit = 'G'
        note("    %-12s: %8.1f %s (%d %s)" % (label, size, unit, count,
            helpers.single_plural(count, "item", "items")))

    def clear_all(self):
        """Free up any memory used by the caches."""
        self._blobs.clear()
        self._sticky_blobs.clear()
        self.revision_ids.clear()
        self.last_ids.clear()
        self.heads.clear()
        self.inventories.clear()

    def _flush_blobs_to_disk(self):
        blobs = self._sticky_blobs.keys()
        sticky_blobs = self._sticky_blobs
        total_blobs = len(sticky_blobs)
        blobs.sort(key=lambda k:len(sticky_blobs[k]))
        if self._tempdir is None:
            self._tempdir = tempfile.mkdtemp(prefix='bzr_fastimport_blobs-')
            self._cleanup.tempdir = self._tempdir
            self._cleanup.small_blobs = tempfile.TemporaryFile(
                prefix='small-blobs-', dir=self._tempdir)
        count = 0
        bytes = 0
        n_small_bytes = 0
        while self._sticky_memory_bytes > self._sticky_flushed_size:
            id = blobs.pop()
            blob = self._sticky_blobs.pop(id)
            n_bytes = len(blob)
            self._sticky_memory_bytes -= n_bytes
            if n_bytes < self._small_blob_threshold:
                f = self._cleanup.small_blobs
                f.seek(0, os.SEEK_END)
                self._disk_blobs[id] = (f.tell(), n_bytes, None)
                f.write(blob)
                n_small_bytes += n_bytes
            else:
                fd, name = tempfile.mkstemp(prefix='blob-', dir=self._tempdir)
                os.write(fd, blob)
                os.close(fd)
                self._disk_blobs[id] = (0, n_bytes, name)
            bytes += n_bytes
            del blob
            count += 1
        trace.note('flushed %d/%d blobs w/ %.1fMB (%.1fMB small) to disk'
                   % (count, total_blobs, bytes / 1024. / 1024,
                      n_small_bytes / 1024. / 1024))
        

    def store_blob(self, id, data):
        """Store a blob of data."""
        # Note: If we're not reference counting, everything has to be sticky
        if not self._blob_ref_counts or id in self._blob_ref_counts:
            self._sticky_blobs[id] = data
            self._sticky_memory_bytes += len(data)
            if self._sticky_memory_bytes > self._sticky_cache_size:
                self._flush_blobs_to_disk()
        elif data == '':
            # Empty data is always sticky
            self._sticky_blobs[id] = data
        else:
            self._blobs[id] = data

    def _decref(self, id, cache, fn):
        if not self._blob_ref_counts:
            return False
        count = self._blob_ref_counts.get(id, None)
        if count is not None:
            count -= 1
            if count <= 0:
                del cache[id]
                if fn is not None:
                    os.unlink(fn)
                del self._blob_ref_counts[id]
                return True
            else:
                self._blob_ref_counts[id] = count
        return False

    def fetch_blob(self, id):
        """Fetch a blob of data."""
        if id in self._blobs:
            return self._blobs.pop(id)
        if id in self._disk_blobs:
            (offset, n_bytes, fn) = self._disk_blobs[id]
            if fn is None:
                f = self._cleanup.small_blobs
                f.seek(offset)
                content = f.read(n_bytes)
            else:
                fp = open(fn, 'rb')
                try:
                    content = fp.read()
                finally:
                    fp.close()
            self._decref(id, self._disk_blobs, fn)
            return content
        content = self._sticky_blobs[id]
        if self._decref(id, self._sticky_blobs, None):
            self._sticky_memory_bytes -= len(content)
        return content

    def track_heads(self, cmd):
        """Track the repository heads given a CommitCommand.
        
        :param cmd: the CommitCommand
        :return: the list of parents in terms of commit-ids
        """
        # Get the true set of parents
        if cmd.from_ is not None:
            parents = [cmd.from_]
        else:
            last_id = self.last_ids.get(cmd.ref)
            if last_id is not None:
                parents = [last_id]
            else:
                parents = []
        parents.extend(cmd.merges)

        # Track the heads
        self.track_heads_for_ref(cmd.ref, cmd.id, parents)
        return parents

    def track_heads_for_ref(self, cmd_ref, cmd_id, parents=None):
        if parents is not None:
            for parent in parents:
                if parent in self.heads:
                    del self.heads[parent]
        self.heads.setdefault(cmd_id, set()).add(cmd_ref)
        self.last_ids[cmd_ref] = cmd_id
        self.last_ref = cmd_ref
