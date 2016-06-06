#/usr/bin/env python2

import argparse
import datetime
import glob
import json
import logging
import os
import shutil
import subprocess
import sys
import time

from contextlib import contextmanager

BASE_DIR_NAME = "rolling-perf"

script_args = None
datastore = None

cli_repo = None
xunitperf_repo = None
empty_dir = None
log_file = None
store_path = None
results_dir = None

launch_time = time.time()

@contextmanager
def PushDir(path):
    prev = os.getcwd()
    try:
        logging.getLogger('shell').info('pushd "{}"'.format(path))
        os.chdir(path)
        yield
    finally:
        logging.getLogger('shell').info('popd')
        os.chdir(prev)

def RunCommand(cmdline, valid_exit_codes=[0], get_output=False, silent=False, suffix=None):
    should_pipe = (not silent) or get_output

    quoted_cmdline = subprocess.list2cmdline(cmdline)
    quoted_cmdline += ' > {}'.format(os.devnull) if not should_pipe else ''
    logging.getLogger('shell').info(quoted_cmdline)
    exe_name = os.path.basename(cmdline[0]).replace('.', '_')

    exe_log_file = log_file
    if suffix != None:
        exe_log_file = exe_log_file.replace('.log', '.{}.log'.format(suffix))

    exe_logger = logging.getLogger(exe_name)
    exe_logger.handlers = []
    fh = logging.FileHandler(exe_log_file)
    fh.setLevel(logging.INFO)
    if suffix == None:
        fh.setFormatter(logging.Formatter(fmt='%(levelname)s:%(name)s:%(message)s'))
    exe_logger.addHandler(fh)
    if suffix != None:
        LogStartMessage(exe_name)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO if script_args.verbose else logging.WARNING)
    ch.setFormatter(logging.Formatter(fmt='%(levelname)s:%(name)s:%(message)s'))
    exe_logger.addHandler(ch)

    lines = []
    with open(os.devnull) as devnull:
        proc = subprocess.Popen(
            cmdline,
            stdout=subprocess.PIPE if should_pipe else devnull,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )

        if proc.stdout != None:
            for line in iter(proc.stdout.readline, ''):
                line = line.rstrip()
                if get_output:
                    lines.append(line)
                exe_logger.info(line)
            proc.stdout.close()

        proc.wait()
        if not proc.returncode in valid_exit_codes:
            exe_logger.error("Exited with exit code {}".format(proc.returncode))
            raise subprocess.CalledProcessError(proc.returncode, quoted_cmdline)

    return lines

def LogStartMessage(name):
    start_msg = "Script started at {}".format(str(datetime.datetime.fromtimestamp(launch_time)))
    logging.getLogger(name).info('-' * len(start_msg))
    logging.getLogger(name).info(start_msg)
    logging.getLogger(name).info('-' * len(start_msg))

def GetEmptyDirPath():
    empty_dir_path = os.path.join(script_args.working_directory, 'empty')
    if not os.path.exists(empty_dir_path):
        os.makedirs(empty_dir_path)
    return empty_dir_path

def GetSubmissionRecord():
    return {
        'time': launch_time,
        'time_as_str': str(datetime.datetime.fromtimestamp(launch_time))
    }

def GetDotNetRuntimeId():
    artifacts_path = os.path.join(cli_repo.path, 'artifacts')
    dir_list = os.listdir(artifacts_path)
    if len(dir_list) != 2:
        raise FatalError("Failed to detect dotnet cli runid: not sure which of {} to use".format(
            ','.join(dir_list)
        ))
    for item in os.listdir(artifacts_path):
        if item != 'tests':
            return item

class FatalError(Exception):
    pass

class GitRepo:
    url = None
    path = None

    def __init__(self, url, path):
        self.url = url
        self.path = path

    def exists(self):
        return os.path.exists(self.path)

    def make_clean(self):
        if self.exists():
            # Only robocopy can reliably delete long file paths on Windows
            RunCommand(['robocopy', GetEmptyDirPath(), self.path, '/mir'], valid_exit_codes=[0,1,2,3], silent=True)
            os.rmdir(self.path)
        self.clone()

    def clone(self):
        if not os.path.exists(self.path):
            RunCommand(['git', 'clone', self.url, self.path])

    def sync(self, branch):
        with PushDir(self.path):
            RunCommand(['git', 'fetch', '--all'])
            RunCommand(['git', 'checkout', branch])
            RunCommand(['git', 'reset', '--hard', 'origin/' + branch])

    def rewind(self, number_of_commits = 1):
        if not isinstance(number_of_commits, int) or number_of_commits < 1:
            raise TypeError("number_of_commits must be an integer >= 1")
        with PushDir(self.path):
            RunCommand(['git', 'checkout', 'HEAD~{}'.format(number_of_commits)])

    def get_sha1(self):
        with PushDir(self.path):
            return RunCommand(['git', 'rev-parse', 'HEAD'], get_output=True)[0].strip()

def process_arguments():
    parser = argparse.ArgumentParser(
        description = "Monitors for changes in the dotnet/cli repo and launches perf tests if changes are found."
    )
    parser.add_argument(
        '--branch', '-b',
        help = "Branch to watch",
        required = True
    )
    parser.add_argument(
        '--working-directory', '--dir', '-d',
        help = "Set the working directory where transient content can be written",
        required = True
    )
    parser.add_argument(
        '--verbose', '-v',
        help = "Enable verbose console output",
        action = 'store_true'
    )
    parser.add_argument(
        '--look-back', '-n',
        help = "Number of builds to backfill",
        metavar = "N",
        default = 1,
        type = int
    )

    global script_args
    script_args = parser.parse_args()

    global results_dir
    results_dir = os.path.join(script_args.working_directory, 'results')

    global store_path
    store_path = os.path.join(script_args.working_directory, 'store.json')

    global cli_repo
    cli_repo = GitRepo(
        url = 'https://github.com/dotnet/cli.git',
        path = os.path.join(script_args.working_directory, 'repos', 'dotnet-cli')
    )
    global xunitperf_repo
    xunitperf_repo = GitRepo(
        url = 'https://github.com/Microsoft/xunit-performance.git',
        path = os.path.join(script_args.working_directory, 'repos', 'xunit-performance')
    )

def init_logging():
    logging.getLogger().setLevel(logging.INFO)

    log_dir = os.path.join(script_args.working_directory, 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    global log_file
    log_file = os.path.join(log_dir, datetime.datetime.fromtimestamp(launch_time).strftime('%Y%m%d') + '.log')

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO if script_args.verbose else logging.WARNING)
    ch.setFormatter(logging.Formatter(fmt='%(levelname)s:%(name)s:%(message)s'))
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(fmt='%(levelname)s:%(name)s:%(message)s'))
    logging.getLogger('shell').addHandler(ch)
    logging.getLogger('shell').addHandler(fh)
    logging.getLogger('shell').setLevel(logging.INFO)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(fmt='%(levelname)s:%(name)s:%(message)s'))
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(fmt='%(levelname)s:%(name)s:%(message)s'))
    logging.getLogger('script').addHandler(ch)
    logging.getLogger('script').addHandler(fh)
    logging.getLogger('script').setLevel(logging.INFO)

def check_dependencies():
    logging.getLogger('script').info("Making sure msbuild exists...")
    try:
        RunCommand(['msbuild', '-version'])
    except:
        raise FatalError("Can't find msbuild, please make sure it's installed and on PATH")

def refresh_repos():
    cli_repo.make_clean()
    cli_repo.sync(script_args.branch)
    xunitperf_repo.make_clean()
    xunitperf_repo.sync('master')

def load_datastore():
    global datastore
    if os.path.exists(store_path):
        with open(store_path, mode='rb') as storefile:
            datastore = json.load(storefile)
    else:
        datastore = dict()

def save_datastore():
    if not os.path.exists(os.path.dirname(store_path)):
        os.makedirs(os.path.dirname(store_path))
    with open(store_path, mode='wb') as storefile:
        json.dump(datastore, storefile, indent=2)

def check_history(commit):
    if datastore == None:
        load_datastore()
    return commit in datastore

def process_submission(sha1):
    record = GetSubmissionRecord()

    logging.getLogger('script').info("Building the cli repo...")
    with PushDir(cli_repo.path):
        RunCommand([
            'build.cmd',
            '-Configuration', 'Release'
        ], suffix='{}.build'.format(sha1))

    logging.getLogger('script').info("Running the perf tests...")
    with PushDir(os.path.join(cli_repo.path, 'test', 'Performance')):
        RunCommand([
            sys.executable,
            'run-perftests.py',
            '--runid', sha1,
            '--xunit-perf-path', xunitperf_repo.path,
            '--verbose',
            os.path.join(cli_repo.path, 'artifacts', GetDotNetRuntimeId(), 'stage2', 'dotnet')
        ], suffix='{}.run-perftests'.format(sha1))

        logging.getLogger('script').info("Publishing results...")
        job_result_dir = os.path.join(results_dir, 'new', sha1)
        job_result_dir_tmp = os.path.join(results_dir, 'temp', sha1)
        if os.path.exists(job_result_dir):
            shutil.rmtree(job_result_dir)
        if os.path.exists(job_result_dir_tmp):
            shutil.rmtree(job_result_dir_tmp)

        os.makedirs(job_result_dir_tmp)

        for csvfile in glob.glob('{}.test.csv'.format(sha1)):
            shutil.copy2(csvfile, job_result_dir_tmp)

        for xmlfile in glob.glob('{}.test.xml'.format(sha1)):
            shutil.copy2(xmlfile, job_result_dir_tmp)

        # The rename signals asynchronous listeners that the results are ready to be processed
        shutil.move(job_result_dir_tmp, job_result_dir)

    return record

def commit_to_history(commit, record):
    if datastore == None:
        load_datastore()
    datastore[commit] = record
    save_datastore()

def main():
    try:
        process_arguments()
        init_logging()
        check_dependencies()

        LogStartMessage('script')
        logging.getLogger('script').info("Refreshing git repos to look for new commits...")
        refresh_repos()

        for n in range(script_args.look_back):
            latest_sha1 = cli_repo.get_sha1()
            if not check_history(latest_sha1):
                logging.getLogger('script').info("Commit {} is new, kicking off submission...".format(latest_sha1))
                submission = process_submission(latest_sha1)
                commit_to_history(latest_sha1, submission)
                break
            else:
                logging.getLogger('script').info("Commit {} has already been processed.".format(latest_sha1))
            if n+1 < script_args.look_back:
                cli_repo.rewind()

    except FatalError as e:
        logging.getLogger('script').error(e.message)
        return 1

    except Exception as e:
        logging.getLogger('script').critical("Unhandled exception: {}".format(e))
        raise

if __name__ == '__main__':
    sys.exit(main())
