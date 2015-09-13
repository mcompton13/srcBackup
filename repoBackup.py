#!/usr/bin/env python

import argparse
from datetime import datetime
from dateutil.parser import parse
from os import makedirs, path
import subprocess
import sys
from tempfile import NamedTemporaryFile


INCLUDE_FILE_FORMAT = '+ {}\n'
INCLUDE_DIR_FORMAT = '+ {}/\n'
EXCLUDE_ALL = '- *\n'

DIFF_FILENAME_FORMAT = '{}_{}.patch'
BUNDLE_FILENAME_FORMAT = 'bundle_{}_{}.hg'

HG_OUTGOING_TEMPLATE_FORMAT = '{}{{node|short}}\\n{}{{date|rfc3339date}}'

HG_OUTGOING_NODE_MARKER = ':NODE:'
HG_OUTGOING_DATE_MARKER = ':DATE:'


is_verbose = False

parser = argparse.ArgumentParser(
    description='A utility copy uncommitted changes from a Mercurial repo')

parser.add_argument('-v', '--verbose', action='store_true',
    help='Print additional debugging messages')

def debug(message):
    if is_verbose:
        print message


def error(message):
    sys.stderr.write(message + '\n')


def hg_list_uncommitted_files(repo_dir_path, include_removed=False, include_deleted=False):

    args = [ "hg",
        "status",
        "--repository",
        repo_dir_path,
        "--no-status",
        "--added",
        "--modified",
        "--unknown",
    ]

    if is_verbose:
        args += ["--verbose"]
    else:
        args += ["--quiet"]

    if include_removed:
        args += ["--removed"]

    if include_deleted:
        args += ["--deleted"]

    debug("Calling hg: " + str(args))

    result = subprocess.check_output(args).strip().split('\n')

    debug(result)

    return result


def to_utc_datetime(local_datetime):
    timezoneless_datetime = datetime(
        local_datetime.year, local_datetime.month, local_datetime.day, local_datetime.hour,
        local_datetime.minute, local_datetime.second, local_datetime.microsecond, tzinfo=None)

    utc_datetime = timezoneless_datetime

    if local_datetime.utcoffset() != None:
        utc_datetime = timezoneless_datetime - local_datetime.utcoffset()

    return utc_datetime


def hg_current_rev(repo_dir_path):

    args = [ "hg",
        "identify",
        "--repository",
        repo_dir_path,
        "--id",
    ]

    debug("Calling hg: " + str(args))

    current_rev_hash = None

    try:
        current_rev_hash = subprocess.check_output(args).strip()
    except Exception:
        pass

    return current_rev_hash


def hg_newest_unpushed_commit(repo_dir_path):

    args = [ "hg",
        "outgoing",
        "--repository",
        repo_dir_path,
        "--newest-first",
        "--limit", "1",
        "--template",
        str.format(HG_OUTGOING_TEMPLATE_FORMAT, HG_OUTGOING_NODE_MARKER, HG_OUTGOING_DATE_MARKER),
    ]

    if is_verbose:
        args += ["--verbose"]
    else:
        args += ["--quiet"]

    debug("Calling hg: " + str(args))

    output_lines = []

    try:
        output_lines = subprocess.check_output(args).strip().split('\n')
    except Exception:
        pass

    rev_hash = None
    rev_utc_datetime = None

    for line in output_lines:
        if line.startswith(HG_OUTGOING_NODE_MARKER):
            rev_hash = line[len(HG_OUTGOING_NODE_MARKER):]

        if line.startswith(HG_OUTGOING_DATE_MARKER):
            date_str = line[len(HG_OUTGOING_DATE_MARKER):]

            rev_utc_datetime = to_utc_datetime(parse(date_str))


    debug(str.format('Most recent unpushed commit: rev: {}\tdate: {}', rev_hash, rev_utc_datetime))

    return rev_hash, rev_utc_datetime


def hg_bundle_unpushed_commits(repo_dir_path, destination_bundle_filename):

    # Make sure the bundle hasn't already been backed up
    if path.exists(destination_dir_path):
        return

    destination_dir_path = path.dirname(destination_bundle_filename)
    if not path.exists(destination_dir_path):
        makedirs(destination_dir_path, 0777)

    args = [ "hg",
        "bundle",
        "--repository",
        repo_dir_path,
        # Don't need compression
        "--type",
        "none",
    ]

    if is_verbose:
        args += ["--verbose"]
    else:
        args += ["--quiet"]

    args += [destination_bundle_filename]

    debug("Calling hg: " + str(args))

    try:
        subprocess.check_output(args)
    except Exception, ex:
        error(ex)


def hg_diff_uncommitted_files(repo_dir_path, destination_diff_filename):
    if path.exists(destination_diff_filename):
        return

    destination_dir_path = path.dirname(destination_diff_filename)
    if not path.exists(destination_dir_path):
        makedirs(destination_dir_path, 0777)

    with open(destination_diff_filename, 'w') as f:
        args = [ "hg",
            "diff",
        ]

        debug("Calling hg: " + str(args))

        try:
            subprocess.call(args, stdout=f)
        except Exception, ex:
            error(ex)


def make_hg_bundle_filename(commit_rev_hash, commit_datetime_utc):
    result = str.format(BUNDLE_FILENAME_FORMAT, commit_datetime_utc.isoformat(), commit_rev_hash)

    debug('Bundle filename: ' + result)

    return result


def make_hg_diff_filename(commit_rev_hash):
    commit_rev_hash = commit_rev_hash[0:12]
    result = str.format(DIFF_FILENAME_FORMAT, datetime.utcnow().isoformat(), commit_rev_hash)

    debug('Bundle filename: ' + result)

    return result


def rsync(source_dir_path, source_files, destination_dir_path):

    if not source_files:
        return

    with NamedTemporaryFile() as tmpfile:

        source_dirs = []
        for source_file in source_files:
            tmpfile.write(str.format(INCLUDE_DIR_FORMAT, path.dirname(source_file)))
            tmpfile.write(str.format(INCLUDE_FILE_FORMAT, source_file))


        # Add line to exclude all files that were NOT included above
        tmpfile.write(EXCLUDE_ALL)

        tmpfile.flush()

        args = ["rsync",
            "--archive",
            "--verbose",
           # "--dry-run",
            "--delete",
            "--delete-excluded",
            "--include-from",
            tmpfile.name,
            source_dir_path,
            destination_dir_path
            ]

        debug("Calling rsync: " + str(args))

        try:
            subprocess.call(args)
        except Exception, ex:
            error(ex)


def main(argv):
    debug(str.format('argv={}', str(argv)))

    # Parse command line args
    args = parser.parse_args(argv[1:])

    global is_verbose
    is_verbose = args.verbose

    debug('args=%s' % args)

    repo = 'devcsdata/'

    repo_to_backup = path.join('/Users/mcompton/Work/Simpson/src/', repo)

    backup_base_dirpath = path.join('/Users/mcompton/Work/Simpson/srcBackup/', repo)

    uncommitted_files_dirpath = path.join(backup_base_dirpath, 'uncommittedFiles/')
    uncommitted_diffs_dirpath = path.join(backup_base_dirpath, 'uncommittedDiffs/')
    unpushed_commits_dirpath = path.join(backup_base_dirpath, 'unpushedCommits/')


    rev_hash, rev_date = hg_newest_unpushed_commit(repo_to_backup)

    if rev_hash:
        bundle_filename = path.join(unpushed_commits_dirpath, make_hg_bundle_filename(rev_hash, rev_date))

        if not path.exists(bundle_filename):
            hg_bundle_unpushed_commits(repo_to_backup, bundle_filename)

    current_rev_hash = hg_current_rev(repo_to_backup)

    # Hg adds a plus to the end of the revision hash if there are changes
    if current_rev_hash.endswith('+'):
        diff_filename = path.join(uncommitted_diffs_dirpath, make_hg_diff_filename(current_rev_hash))
        hg_diff_uncommitted_files(repo_to_backup, diff_filename)

    files_to_backup = hg_list_uncommitted_files(repo_to_backup)

    rsync(repo_to_backup, files_to_backup, uncommitted_files_dirpath)



if __name__ == "__main__":
    main(sys.argv)
