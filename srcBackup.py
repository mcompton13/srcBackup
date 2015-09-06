#!/usr/bin/env python

import argparse
from os import path
import subprocess
import sys
from tempfile import NamedTemporaryFile


INCLUDE_FILE_FORMAT = '+ {}\n'
INCLUDE_DIR_FORMAT = '+ {}/\n'


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


def rsync(source_dir_path, source_files, destination_dir_path):

    with NamedTemporaryFile() as tmpfile:

        source_dirs = []
        for source_file in source_files:
            #print str.format(INCLUDE_DIR_FORMAT, path.dirname(source_file))
            #print str.format(INCLUDE_FILE_FORMAT, source_file)

            tmpfile.write(str.format(INCLUDE_DIR_FORMAT, path.dirname(source_file)))
            tmpfile.write(str.format(INCLUDE_FILE_FORMAT, source_file))


        args = ["rsync",
            "--archive",
            "--delete",
            "--delete-excluded",
           # "--include-from",
           # tmpfile.name,
            "--include",
            str.format("/{}/", path.dirname(source_files[0])),
            "--include",
            str.format("{}", source_files[0]),
            "--exclude",
            "*",
            "--verbose",
            "--dry-run",
            source_dir_path,
            destination_dir_path
            ]

        debug("Calling rsync: " + str(args))

        print
        print

        result = subprocess.call(args)


def main(argv):
    print 'argv=%s' % argv

    # Parse command line args
    args = parser.parse_args(argv[1:])

    global is_verbose
    is_verbose = args.verbose

    debug('args=%s' % args)

    rsync('/Users/mcompton/Work/Simpson/src/devcsdata/',
        ['srcCSDataAccessManager/ProjectCustomFieldSortCriteria.cs'],
        '/Users/mcompton/Work/Simpson/src/srcBackup/')


if __name__ == "__main__":
    main(sys.argv)