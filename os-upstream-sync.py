#!/usr/bin/env python3

"""
Syncs a downstream fork of an OpenStack project with upstream.
"""

from __future__ import print_function
import argparse
import os
import subprocess
import sys


DEFAULT_RELEASE = os.environ.get("DEFAULT_RELEASE", "wallaby")
DEFAULT_BRANCH_PREFIX = "merge-upstream-{}"
DEFAULT_MESSAGE = "Merge upstream stable/{}"


def check_uncommitted():
    cmd = ["git", "diff-index", "--quiet", "HEAD"]
    return subprocess.check_output(cmd).strip()


def rev_parse(ref):
    cmd = ["git", "rev-parse", ref]
    return subprocess.check_output(cmd).strip()


def fetch(remote):
    print("Fetching from", remote)
    cmd = ["git", "fetch", remote]
    return subprocess.check_output(cmd).strip()


def merge_base(ref1, ref2):
    cmd = ["git", "merge-base", ref1, ref2]
    result = subprocess.check_output(cmd).strip()
    print("Merge base of", ref1, "and", ref2, "is", result)
    return result


def create_branch(branch, ref, force):
    print("Creating branch", branch, "at", ref)
    cmd = ["git", "branch", branch, ref]
    if force:
        cmd.append('--force')
    subprocess.check_call(cmd)


def checkout(ref):
    print("Checking out", ref)
    cmd = ["git", "checkout", ref]
    subprocess.check_call(cmd)


def merge(ref, message):
    print("Merging with", ref)
    cmd = ["git", "merge", ref, "-m", message]
    subprocess.check_call(cmd)


def commit(message):
    print("Committing changes")
    cmd = ["git", "commit", "-m", message]
    subprocess.check_call(cmd)


def push(remote, branch):
    print("Pushing branch", branch, "to remote", remote)
    cmd = ["git", "push", remote, branch]
    subprocess.check_call(cmd)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--branch",
                        help="Name of the branch to create. Default is " +
                             DEFAULT_BRANCH_PREFIX.format("-<release>"))
    parser.add_argument("--continue", action="store_true", dest="cont",
                        help="Continue from a previous failed merge attempt. "
                             "All merge issues should be resolved")
    parser.add_argument("-d", "--downstream-remote", default="stackhpc",
                        help="Name of the upstream git remote. Default is "
                             "'stackhpc'")
    parser.add_argument("-f", "--force", action="store_true",
                        help="Force creation of the branch")
    parser.add_argument("-m", "--message",
                        help="Git merge commit message. Default is " +
                             DEFAULT_MESSAGE.format("<release>"))
    parser.add_argument("-r", "--release", default=DEFAULT_RELEASE,
                        help="Name of the OpenStack release. "
                             "Default is '{}'".format(DEFAULT_RELEASE))
    parser.add_argument("-u", "--upstream-remote", default="origin",
                        help="Name of the upstream git remote. Default is "
                             "'origin'")
    return parser.parse_args()


def main():
    parsed_args = parse_args()
    release = parsed_args.release
    upstream_remote = parsed_args.upstream_remote
    downstream_remote = parsed_args.downstream_remote
    branch = parsed_args.branch
    cont = parsed_args.cont
    force = parsed_args.force
    message = parsed_args.message

    upstream_branch = "stable/{}".format(release)
    upstream_ref = rev_parse("{}/{}".format(upstream_remote, upstream_branch))

    downstream_branch = "stackhpc/{}".format(release)
    downstream_ref = rev_parse("{}/{}".format(downstream_remote, downstream_branch))

    if not branch:
        branch = DEFAULT_BRANCH_PREFIX.format(release)
    if not message:
        message = DEFAULT_MESSAGE.format(release)

    if not cont:
        try:
            check_uncommitted()
        except:
            print("Found uncommitted changes - aborting")
            sys.exit(1)

        fetch(upstream_remote)
        fetch(downstream_remote)

        merge_base_ref = merge_base(upstream_ref, downstream_ref)
        if merge_base_ref == upstream_ref:
            print("Latest upstream already synced")
            return

        create_branch(branch, downstream_ref, force)
        checkout(branch)
        merge(upstream_ref, message)
    else:
        try:
            check_uncommitted()
        except:
            pass
        else:
            print("Found no uncommitted changes - is a merge in progress?")
            sys.exit(1)

        commit(message)

    push(downstream_remote, branch)


if __name__ == "__main__":
    main()
