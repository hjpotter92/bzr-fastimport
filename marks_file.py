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

"""Routines for reading/writing a marks file."""


import re
from bzrlib.trace import warning


def import_marks(filename):
    """Read the mapping of marks to revision-ids from a file.

    :param filename: the file to read from
    :return: None if an error is encountered or a dictionary with marks
        as keys and revision-ids as values
    """
    # Check that the file is readable and in the right format
    try:
        f = file(filename)
    except IOError:
        warning("Could not import marks file %s - not importing marks",
            filename)
        return None

    # Read the revision info
    revision_ids = {}
    for line in f:
        line = line.rstrip('\n')
        mark, revid = line.split(' ', 1)
        if mark.startswith(':'):
            mark = mark[1:]
        revision_ids[mark] = revid
    f.close()
    return revision_ids


def export_marks(filename, revision_ids):
    """Save marks to a file.

    :param filename: filename to save data to
    :param revision_ids: dictionary mapping marks -> bzr revision-ids
    """
    try:
        f = file(filename, 'w')
    except IOError:
        warning("Could not open export-marks file %s - not exporting marks",
            filename)
        return

    # Write the revision info
    for mark, revid in revision_ids.iteritems():
        f.write(':%s %s\n' % (mark, revid))
    f.close()
