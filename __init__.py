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

r"""FastImport Plugin
=================

The fastimport plugin provides stream-based importing and exporting of
data into and out of Bazaar. As well as enabling interchange between
multiple VCS tools, fastimport/export can be useful for complex branch
operations, e.g. partitioning off part of a code base in order to Open
Source it.

The normal import recipe is::

  bzr fast-export-from-xxx SOURCE project.fi
  bzr fast-import project.fi project.bzr

If fast-export-from-xxx doesn't exist yet for the tool you're importing
from, the alternative recipe is::

  front-end > project.fi
  bzr fast-import project.fi project.bzr

In either case, if you wish to save disk space, project.fi can be
compressed to gzip format after it is generated like this::

  (generate project.fi)
  gzip project.fi
  bzr fast-import project.fi.gz project.bzr

The list of known front-ends and their status is documented on
http://bazaar-vcs.org/BzrFastImport/FrontEnds. The fast-export-from-xxx
commands provide simplified access to these so that the majority of users
can generate a fast-import dump file without needing to study up on all
the options - and the best combination of them to use - for the front-end
relevant to them. In some cases, a fast-export-from-xxx wrapper will require
that certain dependencies are installed so it checks for these before
starting. A wrapper may also provide a limited set of options. See the
online help for the individual commands for details::

  bzr help fast-export-from-cvs
  bzr help fast-export-from-darcs
  bzr help fast-export-from-hg
  bzr help fast-export-from-git
  bzr help fast-export-from-mnt
  bzr help fast-export-from-p4
  bzr help fast-export-from-svn

Once a fast-import dump file is created, it can be imported into a
Bazaar repository using the fast-import command. If required, you can
manipulate the stream first using the fast-import-filter command.
This is useful for creating a repository with just part of a project
or for removing large old binaries (say) from history that are no longer
valuable to retain. For further details on importing, manipulating and
reporting on fast-import streams, see the online help for the commands::

  bzr help fast-import
  bzr help fast-import-filter
  bzr help fast-import-info
  bzr help fast-import-query

Finally, you may wish to generate a fast-import dump file from a Bazaar
repository. The fast-export command is provided for that purpose.

To report bugs or publish enhancements, visit the bzr-fastimport project
page on Launchpad, https://launchpad.net/bzr-fastimport.
"""

version_info = (0, 9, 0, 'dev', 0)

from bzrlib import bzrdir
from bzrlib.commands import Command, register_command
from bzrlib.option import Option, ListOption, RegistryOption


def test_suite():
    import tests
    return tests.test_suite()


def _run(source, processor_factory, control, params, verbose):
    """Create and run a processor.
    
    :param source: a filename or '-' for standard input. If the
      filename ends in .gz, it will be opened as a gzip file and
      the stream will be implicitly uncompressed
    :param processor_factory: a callable for creating a processor
    :param control: the BzrDir of the destination or None if no
      destination is expected
    """
    import parser
    stream = _get_source_stream(source)
    proc = processor_factory(control, params=params, verbose=verbose)
    p = parser.ImportParser(stream, verbose=verbose)
    return proc.process(p.iter_commands)


def _get_source_stream(source):
    if source == '-':
        import sys
        stream = helpers.binary_stream(sys.stdin)
    elif source.endswith('.gz'):
        import gzip
        stream = gzip.open(source, "rb")
    else:
        stream = open(source, "rb")
    return stream


class cmd_fast_import(Command):
    """Backend for fast Bazaar data importers.

    This command reads a mixed command/data stream and creates
    branches in a Bazaar repository accordingly. The preferred
    recipe is::

      bzr fast-import project.fi project.bzr

    Numerous commands are provided for generating a fast-import file
    to use as input. These are named fast-export-from-xxx where xxx
    is one of cvs, darcs, git, hg, mnt, p4 or svn.
    To specify standard input as the input stream, use a
    source name of '-' (instead of project.fi). If the source name
    ends in '.gz', it is assumed to be compressed in gzip format.
    
    project.bzr will be created if it doesn't exist. If it exists
    already, it should be empty or be an existing Bazaar repository
    or branch. If not specified, the current directory is assumed.
 
    fast-import will intelligently select the format to use when
    creating a repository or branch. If you are running Bazaar 1.17
    up to Bazaar 2.0, the default format for Bazaar 2.x ("2a") is used.
    Otherwise, the current default format ("pack-0.92" for Bazaar 1.x)
    is used. If you wish to specify a custom format, use the `--format`
    option.

     .. note::
     
        To maintain backwards compatibility, fast-import lets you
        create the target repository or standalone branch yourself.
        It is recommended though that you let fast-import create
        these for you instead.

    :Branch mapping rules:

     Git reference names are mapped to Bazaar branch names as follows:
      
     * refs/heads/foo is mapped to foo
     * refs/remotes/origin/foo is mapped to foo.remote
     * refs/tags/foo is mapped to foo.tag
     * */master is mapped to trunk, trunk.remote, etc.
     * */trunk is mapped to git-trunk, git-trunk.remote, etc.

    :Branch creation rules:

     When a shared repository is created or found at the destination,
     branches are created inside it. In the simple case of a single
     branch (refs/heads/master) inside the input file, the branch is
     project.bzr/trunk.

     When a standalone branch is found at the destination, the trunk
     is imported there and warnings are output about any other branches
     found in the input file.

     When a branch in a shared repository is found at the destination,
     that branch is made the trunk and other branches, if any, are
     created in sister directories.

    :Working tree updates:

     The working tree is generated for the trunk branch. If multiple
     branches are created, a message is output on completion explaining
     how to create the working trees for other branches.

    :Custom exporters:

     The fast-export-from-xxx commands typically call more advanced
     xxx-fast-export scripts. You are welcome to use the advanced
     scripts if you prefer.

     If you wish to write a custom exporter for your project, see
     http://bazaar-vcs.org/BzrFastImport for the detailed protocol
     specification. In many cases, exporters can be written quite
     quickly using whatever scripting/programming language you like.

    :Blob tracking:

     As some exporters (like git-fast-export) reuse blob data across
     commits, fast-import makes two passes over the input file by
     default. In the first pass, it collects data about what blobs are
     used when, along with some other statistics (e.g. total number of
     commits). In the second pass, it generates the repository and
     branches.
     
     .. note::
     
        The initial pass isn't done if the --info option is used
        to explicitly pass in information about the input stream.
        It also isn't done if the source is standard input. In the
        latter case, memory consumption may be higher than otherwise
        because some blobs may be kept in memory longer than necessary.

    :Restarting an import:

     At checkpoints and on completion, the commit-id -> revision-id
     map is saved to a file called 'fastimport-id-map' in the control
     directory for the repository (e.g. .bzr/repository). If the import
     is interrupted or unexpectedly crashes, it can be started again
     and this file will be used to skip over already loaded revisions.
     As long as subsequent exports from the original source begin
     with exactly the same revisions, you can use this feature to
     maintain a mirror of a repository managed by a foreign tool.
     If and when Bazaar is used to manage the repository, this file
     can be safely deleted.

    :Examples:

     Import a Subversion repository into Bazaar::

       bzr fast-export-from-svn /svn/repo/path project.fi
       bzr fast-import project.fi project.bzr

     Import a CVS repository into Bazaar::

       bzr fast-export-from-cvs /cvs/repo/path project.fi
       bzr fast-import project.fi project.bzr

     Import a Git repository into Bazaar::

       bzr fast-export-from-git /git/repo/path project.fi
       bzr fast-import project.fi project.bzr

     Import a Mercurial repository into Bazaar::

       bzr fast-export-from-hg /hg/repo/path project.fi
       bzr fast-import project.fi project.bzr

     Import a Darcs repository into Bazaar::

       bzr fast-export-from-darcs /darcs/repo/path project.fi
       bzr fast-import project.fi project.bzr
    """
    hidden = False
    _see_also = ['fast-export', 'fast-import-filter', 'fast-import-info']
    takes_args = ['source', 'destination?']
    takes_options = ['verbose',
                    Option('info', type=str,
                        help="Path to file containing caching hints.",
                        ),
                    Option('trees',
                        help="Update all working trees, not just trunk's.",
                        ),
                    Option('count', type=int,
                        help="Import this many revisions then exit.",
                        ),
                    Option('checkpoint', type=int,
                        help="Checkpoint automatically every N revisions."
                             " The default is 10000.",
                        ),
                    Option('autopack', type=int,
                        help="Pack every N checkpoints. The default is 4.",
                        ),
                    Option('inv-cache', type=int,
                        help="Number of inventories to cache.",
                        ),
                    RegistryOption.from_kwargs('mode',
                        'The import algorithm to use.',
                        title='Import Algorithm',
                        default='Use the preferred algorithm (inventory deltas).',
                        classic="Use the original algorithm (mutable inventories).",
                        experimental="Enable experimental features.",
                        value_switches=True, enum_switch=False,
                        ),
                    Option('import-marks', type=str,
                        help="Import marks from file."
                        ),
                    Option('export-marks', type=str,
                        help="Export marks to file."
                        ),
                    RegistryOption('format',
                            help='Specify a format for the created repository. See'
                                 ' "bzr help formats" for details.',
                            lazy_registry=('bzrlib.bzrdir', 'format_registry'),
                            converter=lambda name: bzrdir.format_registry.make_bzrdir(name),
                            value_switches=False, title='Repository format'),
                     ]
    aliases = []
    def run(self, source, destination='.', verbose=False, info=None,
        trees=False, count=-1, checkpoint=10000, autopack=4, inv_cache=-1,
        mode=None, import_marks=None, export_marks=None, format=None):
        from bzrlib.errors import BzrCommandError, NotBranchError
        from bzrlib.plugins.fastimport.processors import generic_processor
        from bzrlib.plugins.fastimport.helpers import (
            open_destination_directory,
            )
        # If no format is given and the user is running a release
        # leading up to 2.0, select 2a for them. Otherwise, use
        # the default format.
        if format is None:
            import bzrlib
            bzr_version = bzrlib.version_info[0:2]
            if bzr_version in [(1,17), (1,18), (2,0)]:
                format = bzrdir.format_registry.make_bzrdir('2a')
        control = open_destination_directory(destination, format=format)

        # If an information file was given and the source isn't stdin,
        # generate the information by reading the source file as a first pass
        if info is None and source != '-':
            info = self._generate_info(source)

        # Do the work
        if mode is None:
            mode = 'default'
        params = {
            'info': info,
            'trees': trees,
            'count': count,
            'checkpoint': checkpoint,
            'autopack': autopack,
            'inv-cache': inv_cache,
            'mode': mode,
            'import-marks': import_marks,
            'export-marks': export_marks,
            }
        return _run(source, generic_processor.GenericProcessor, control,
            params, verbose)

    def _generate_info(self, source):
        from cStringIO import StringIO
        import parser
        from bzrlib.plugins.fastimport.processors import info_processor
        stream = _get_source_stream(source)
        output = StringIO()
        try:
            proc = info_processor.InfoProcessor(verbose=True, outf=output)
            p = parser.ImportParser(stream)
            return_code = proc.process(p.iter_commands)
            lines = output.getvalue().splitlines()
        finally:
            output.close()
            stream.seek(0)
        return lines


class cmd_fast_import_filter(Command):
    """Filter a fast-import stream to include/exclude files & directories.

    This command is useful for splitting a subdirectory or bunch of
    files out from a project to create a new project complete with history
    for just those files. It can also be used to create a new project
    repository that removes all references to files that should not have
    been committed, e.g. security-related information (like passwords),
    commercially sensitive material, files with an incompatible license or
    large binary files like CD images.

    When filtering out a subdirectory (or file), the new stream uses the
    subdirectory (or subdirectory containing the file) as the root. As
    fast-import doesn't know in advance whether a path is a file or
    directory in the stream, you need to specify a trailing '/' on
    directories passed to the `--includes option`. If multiple files or
    directories are given, the new root is the deepest common directory.

    To specify standard input as the input stream, use a source name
    of '-'. If the source name ends in '.gz', it is assumed to be
    compressed in gzip format.

    Note: If a path has been renamed, take care to specify the *original*
    path name, not the final name that it ends up with.

    :Examples:

     Create a new project from a library (note the trailing / on the
     directory name of the library)::

       front-end | bzr fast-import-filter -i lib/xxx/ > xxx.fi
       bzr fast-import xxx.fi mylibrary.bzr
       (lib/xxx/foo is now foo)

     Create a new repository without a sensitive file::

       front-end | bzr fast-import-filter -x missile-codes.txt > clean.fi
       bzr fast-import clean.fi clean.bzr
    """
    hidden = False
    _see_also = ['fast-import']
    takes_args = ['source']
    takes_options = ['verbose',
                    ListOption('include_paths', short_name='i', type=str,
                        help="Only include commits affecting these paths."
                             " Directories should have a trailing /."
                        ),
                    ListOption('exclude_paths', short_name='x', type=str,
                        help="Exclude these paths from commits."
                        ),
                     ]
    aliases = []
    encoding_type = 'exact'
    def run(self, source, verbose=False, include_paths=None,
        exclude_paths=None):
        from bzrlib.plugins.fastimport.processors import filter_processor
        params = {
            'include_paths': include_paths,
            'exclude_paths': exclude_paths,
            }
        return _run(source, filter_processor.FilterProcessor, None, params,
            verbose)


class cmd_fast_import_info(Command):
    """Output information about a fast-import stream.

    This command reads a fast-import stream and outputs
    statistics and interesting properties about what it finds.
    When run in verbose mode, the information is output as a
    configuration file that can be passed to fast-import to
    assist it in intelligently caching objects.

    To specify standard input as the input stream, use a source name
    of '-'. If the source name ends in '.gz', it is assumed to be
    compressed in gzip format.

    :Examples:

     Display statistics about the import stream produced by front-end::

      front-end | bzr fast-import-info -

     Create a hints file for running fast-import on a large repository::

       front-end | bzr fast-import-info -v - > front-end.cfg
    """
    hidden = False
    _see_also = ['fast-import']
    takes_args = ['source']
    takes_options = ['verbose']
    aliases = []
    def run(self, source, verbose=False):
        from bzrlib.plugins.fastimport.processors import info_processor
        return _run(source, info_processor.InfoProcessor, None, {}, verbose)


class cmd_fast_import_query(Command):
    """Query a fast-import stream displaying selected commands.

    To specify standard input as the input stream, use a source name
    of '-'. If the source name ends in '.gz', it is assumed to be
    compressed in gzip format.

    To specify a commit to display, give its mark using the
    --commit-mark option. The commit will be displayed with
    file-commands included but with inline blobs hidden.

    To specify the commands to display, use the -C option one or
    more times. To specify just some fields for a command, use the
    syntax::

      command=field1,...

    By default, the nominated fields for the nominated commands
    are displayed tab separated. To see the information in
    a name:value format, use verbose mode.

    Note: Binary fields (e.g. data for blobs) are masked out
    so it is generally safe to view the output in a terminal.

    :Examples:

     Show the commit with mark 429::

      bzr fast-import-query xxx.fi -m429

     Show all the fields of the reset and tag commands::

      bzr fast-import-query xxx.fi -Creset -Ctag

     Show the mark and merge fields of the commit commands::

      bzr fast-import-query xxx.fi -Ccommit=mark,merge
    """
    hidden = True
    _see_also = ['fast-import', 'fast-import-filter']
    takes_args = ['source']
    takes_options = ['verbose',
                    Option('commit-mark', short_name='m', type=str,
                        help="Mark of the commit to display."
                        ),
                    ListOption('commands', short_name='C', type=str,
                        help="Display fields for these commands."
                        ),
                     ]
    aliases = []
    def run(self, source, verbose=False, commands=None, commit_mark=None):
        from bzrlib.plugins.fastimport.processors import query_processor
        from bzrlib.plugins.fastimport import helpers
        params = helpers.defines_to_dict(commands) or {}
        if commit_mark:
            params['commit-mark'] = commit_mark
        return _run(source, query_processor.QueryProcessor, None, params,
            verbose)


class cmd_fast_export(Command):
    """Generate a fast-import stream from a Bazaar branch.

    This program generates a stream from a Bazaar branch in fast-import
    format used by tools such as bzr fast-import, git-fast-import and
    hg-fast-import.

    If no destination is given or the destination is '-', standard output
    is used. Otherwise, the destination is the name of a file. If the
    destination ends in '.gz', the output will be compressed into gzip
    format.
 
    :Round-tripping:

     Recent versions of the fast-import specification support features
     that allow effective round-tripping of many Bazaar branches. As
     such, fast-exporting a branch and fast-importing the data produced
     will create a new repository with equivalent history, i.e.
     "bzr log -v -p --include-merges --forward" on the old branch and
     new branch should produce similar, if not identical, results.

     .. note::
    
        Be aware that the new repository may appear to have similar history
        but internally it is quite different with new revision-ids and
        file-ids assigned. As a consequence, the ability to easily merge
        with branches based on the old repository is lost. Depending on your
        reasons for producing a new repository, this may or may not be an
        issue.

    :Interoperability:

     fast-export can use the following "extended features" to
     produce a richer data stream:

     * *multiple-authors* - if a commit has multiple authors (as commonly
       occurs in pair-programming), all authors will be included in the
       output, not just the first author

     * *commit-properties* - custom metadata per commit that Bazaar stores
       in revision properties (e.g. branch-nick and bugs fixed by this
       change) will be included in the output.

     * *empty-directories* - directories, even the empty ones, will be
       included in the output.

     To disable these features and produce output acceptable to git 1.6,
     use the --plain option. To enable these features, use --no-plain.
     Currently, --plain is the default but that will change in the near
     future once the feature names and definitions are formally agreed
     to by the broader fast-import developer community.

    :Examples:

     To produce data destined for import into Bazaar::

       bzr fast-export --no-plain my-bzr-branch my.fi.gz

     To produce data destined for Git 1.6::

       bzr fast-export --plain my-bzr-branch my.fi

     To import several unmerged but related branches into the same repository,
     use the --{export,import}-marks options, and specify a name for the git
     branch like this::
    
       bzr fast-export --export-marks=marks.bzr project.dev |
              GIT_DIR=project/.git git-fast-import --export-marks=marks.git

       bzr fast-export --import-marks=marks.bzr -b other project.other |
              GIT_DIR=project/.git git-fast-import --import-marks=marks.git

     If you get a "Missing space after source" error from git-fast-import,
     see the top of the commands.py module for a work-around.
    """
    hidden = False
    _see_also = ['fast-import', 'fast-import-filter']
    takes_args = ['source', 'destination?']
    takes_options = ['verbose', 'revision',
                    Option('git-branch', short_name='b', type=str,
                        argname='FILE',
                        help='Name of the git branch to create (default=master).'
                        ),
                    Option('checkpoint', type=int, argname='N',
                        help="Checkpoint every N revisions (default=10000)."
                        ),
                    Option('marks', type=str, argname='FILE',
                        help="Import marks from and export marks to file."
                        ),
                    Option('import-marks', type=str, argname='FILE',
                        help="Import marks from file."
                        ),
                    Option('export-marks', type=str, argname='FILE',
                        help="Export marks to file."
                        ),
                    Option('plain',
                        help="Exclude metadata to maximise interoperability."
                        ),
                     ]
    aliases = []
    encoding_type = 'exact'
    def run(self, source, destination=None, verbose=False,
        git_branch="master", checkpoint=10000, marks=None,
        import_marks=None, export_marks=None, revision=None,
        plain=True):
        from bzrlib.plugins.fastimport import bzr_exporter

        if marks:                                              
            import_marks = export_marks = marks
        exporter = bzr_exporter.BzrFastExporter(source,
            destination=destination,
            git_branch=git_branch, checkpoint=checkpoint,
            import_marks_file=import_marks, export_marks_file=export_marks,
            revision=revision, verbose=verbose, plain_format=plain)
        return exporter.run()


class cmd_fast_export_from_cvs(Command):
    """Generate a fast-import file from a CVS repository.

    Destination is a dump file, typically named xxx.fi where xxx is
    the name of the project. If '-' is given, standard output is used.

    cvs2svn 2.3 or later must be installed as its cvs2bzr script is used
    under the covers to do the export.
    
    The source must be the path on your filesystem to the part of the
    repository you wish to convert. i.e. either that path or a parent
    directory must contain a CVSROOT subdirectory. The path may point to
    either the top of a repository or to a path within it. In the latter
    case, only that project within the repository will be converted.

    .. note::
       Remote access to the repository is not sufficient - the path
       must point into a copy of the repository itself. See
       http://cvs2svn.tigris.org/faq.html#repoaccess for instructions
       on how to clone a remote CVS repository locally.

    By default, the trunk, branches and tags are all exported. If you
    only want the trunk, use the `--trunk-only` option.

    By default, filenames, log messages and author names are expected
    to be encoded in ascii. Use the `--encoding` option to specify an
    alternative. If multiple encodings are used, specify the option
    multiple times. For a list of valid encoding names, see
    http://docs.python.org/lib/standard-encodings.html.

    Windows users need to install GNU sort and use the `--sort`
    option to specify its location. GNU sort can be downloaded from
    http://unxutils.sourceforge.net/.
    """
    hidden = False
    _see_also = ['fast-import', 'fast-import-filter']
    takes_args = ['source', 'destination']
    takes_options = ['verbose',
                    Option('trunk-only',
                        help="Export just the trunk, ignoring tags and branches."
                        ),
                    ListOption('encoding', type=str, argname='CODEC',
                        help="Encoding used for filenames, commit messages "
                             "and author names if not ascii."
                        ),
                    Option('sort', type=str, argname='PATH',
                        help="GNU sort program location if not on the path."
                        ),
                    ]
    aliases = []
    encoding_type = 'exact'
    def run(self, source, destination, verbose=False, trunk_only=False,
        encoding=None, sort=None):
        from bzrlib.plugins.fastimport.exporters import fast_export_from
        custom = []
        if trunk_only:
            custom.append("--trunk-only")
        if encoding:
            for enc in encoding:
                custom.extend(['--encoding', enc])
        if sort:
            custom.extend(['--sort', sort])
        fast_export_from(source, destination, 'cvs', verbose, custom)


class cmd_fast_export_from_darcs(Command):
    """Generate a fast-import file from a Darcs repository.

    Destination is a dump file, typically named xxx.fi where xxx is
    the name of the project. If '-' is given, standard output is used.

    Darcs 2.2 or later must be installed as various subcommands are
    used to access the source repository. The source may be a network
    URL but using a local URL is recommended for performance reasons.
    """
    hidden = False
    _see_also = ['fast-import', 'fast-import-filter']
    takes_args = ['source', 'destination']
    takes_options = ['verbose',
                    Option('encoding', type=str, argname='CODEC',
                        help="Encoding used for commit messages if not utf-8."
                        ),
                    ]
    aliases = []
    encoding_type = 'exact'
    def run(self, source, destination, verbose=False, encoding=None):
        from bzrlib.plugins.fastimport.exporters import fast_export_from
        custom = None
        if encoding is not None:
            custom = ['--encoding', encoding]
        fast_export_from(source, destination, 'darcs', verbose, custom)


class cmd_fast_export_from_hg(Command):
    """Generate a fast-import file from a Mercurial repository.

    Destination is a dump file, typically named xxx.fi where xxx is
    the name of the project. If '-' is given, standard output is used.

    Mercurial 1.2 or later must be installed as its libraries are used
    to access the source repository. Given the APIs currently used,
    the source repository must be a local file, not a network URL.
    """
    hidden = False
    _see_also = ['fast-import', 'fast-import-filter']
    takes_args = ['source', 'destination']
    takes_options = ['verbose']
    aliases = []
    encoding_type = 'exact'
    def run(self, source, destination, verbose=False):
        from bzrlib.plugins.fastimport.exporters import fast_export_from
        fast_export_from(source, destination, 'hg', verbose)


class cmd_fast_export_from_git(Command):
    """Generate a fast-import file from a Git repository.

    Destination is a dump file, typically named xxx.fi where xxx is
    the name of the project. If '-' is given, standard output is used.

    Git 1.6 or later must be installed as the git fast-export
    subcommand is used under the covers to generate the stream.
    The source must be a local directory.

    .. note::
    
       Earlier versions of Git may also work fine but are
       likely to receive less active support if problems arise.
    """
    hidden = False
    _see_also = ['fast-import', 'fast-import-filter']
    takes_args = ['source', 'destination']
    takes_options = ['verbose']
    aliases = []
    encoding_type = 'exact'
    def run(self, source, destination, verbose=False):
        from bzrlib.plugins.fastimport.exporters import fast_export_from
        fast_export_from(source, destination, 'git', verbose)


class cmd_fast_export_from_mnt(Command):
    """Generate a fast-import file from a Monotone repository.

    Destination is a dump file, typically named xxx.fi where xxx is
    the name of the project. If '-' is given, standard output is used.

    Monotone 0.43 or later must be installed as the mnt git_export
    subcommand is used under the covers to generate the stream.
    The source must be a local directory.
    """
    hidden = False
    _see_also = ['fast-import', 'fast-import-filter']
    takes_args = ['source', 'destination']
    takes_options = ['verbose']
    aliases = []
    encoding_type = 'exact'
    def run(self, source, destination, verbose=False):
        from bzrlib.plugins.fastimport.exporters import fast_export_from
        fast_export_from(source, destination, 'mnt', verbose)


class cmd_fast_export_from_p4(Command):
    """Generate a fast-import file from a Perforce repository.

    Source is a Perforce depot path, e.g., //depot/project

    Destination is a dump file, typically named xxx.fi where xxx is
    the name of the project. If '-' is given, standard output is used.

    bzrp4 must be installed as its p4_fast_export.py module is used under
    the covers to do the export.  bzrp4 can be downloaded from
    https://launchpad.net/bzrp4/.
    
    The P4PORT environment variable must be set, and you must be logged
    into the Perforce server.

    By default, only the HEAD changelist is exported.  To export all
    changelists, append '@all' to the source.  To export a revision range,
    append a comma-delimited pair of changelist numbers to the source,
    e.g., '100,200'.
    """
    hidden = False
    _see_also = ['fast-import', 'fast-import-filter']
    takes_args = ['source', 'destination']
    takes_options = []
    aliases = []
    encoding_type = 'exact'
    def run(self, source, destination, verbose=False):
        from bzrlib.plugins.fastimport.exporters import fast_export_from
        custom = []
        fast_export_from(source, destination, 'p4', verbose, custom)


class cmd_fast_export_from_svn(Command):
    """Generate a fast-import file from a Subversion repository.

    Destination is a dump file, typically named xxx.fi where xxx is
    the name of the project. If '-' is given, standard output is used.

    Python-Subversion (Python bindings to the Subversion APIs)
    1.4 or later must be installed as this library is used to
    access the source repository. The source may be a network URL
    but using a local URL is recommended for performance reasons.
    """
    hidden = False
    _see_also = ['fast-import', 'fast-import-filter']
    takes_args = ['source', 'destination']
    takes_options = ['verbose',
                    Option('trunk-path', type=str, argname="STR",
                        help="Path in repo to /trunk.\n"
                              "May be `regex:/cvs/(trunk)/proj1/(.*)` in "
                              "which case the first group is used as the "
                              "branch name and the second group is used "
                              "to match files.",
                        ),
                    Option('branches-path', type=str, argname="STR",
                        help="Path in repo to /branches."
                        ),
                    Option('tags-path', type=str, argname="STR",
                        help="Path in repo to /tags."
                        ),
                    ]
    aliases = []
    encoding_type = 'exact'
    def run(self, source, destination, verbose=False, trunk_path=None,
        branches_path=None, tags_path=None):
        from bzrlib.plugins.fastimport.exporters import fast_export_from
        custom = []
        if trunk_path is not None:
            custom.extend(['--trunk-path', trunk_path])
        if branches_path is not None:
            custom.extend(['--branches-path', branches_path])
        if tags_path is not None:
            custom.extend(['--tags-path', tags_path])
        fast_export_from(source, destination, 'svn', verbose, custom)


register_command(cmd_fast_import)
register_command(cmd_fast_import_filter)
register_command(cmd_fast_import_info)
register_command(cmd_fast_import_query)
register_command(cmd_fast_export)
register_command(cmd_fast_export_from_cvs)
register_command(cmd_fast_export_from_darcs)
register_command(cmd_fast_export_from_hg)
register_command(cmd_fast_export_from_git)
register_command(cmd_fast_export_from_mnt)
register_command(cmd_fast_export_from_p4)
register_command(cmd_fast_export_from_svn)
