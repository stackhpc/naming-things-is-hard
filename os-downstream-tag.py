#!/usr/bin/env python

"""
Determines an appropriate version to assign to a downstream fork of an
OpenStack project, then creates a tag and pushes it to the downstream
repository.
"""

from __future__ import print_function
import argparse
import subprocess
import sys


DEFAULT_RELEASE = "rocky"


def rev_parse(ref):
    cmd = ["git", "rev-parse", ref]
    return subprocess.check_output(cmd).strip()


def fetch(remote):
    print("Fetching from", remote)
    cmd = ["git", "fetch", remote]
    return subprocess.check_output(cmd).strip()


def most_recent_tag(ref):
    cmd = ["git", "describe", ref, "--abbrev=0", "--tags"]
    return subprocess.check_output(cmd).strip()


def merge_base(ref1, ref2):
    cmd = ["git", "merge-base", ref1, ref2]
    result = subprocess.check_output(cmd).strip()
    print("Merge base of", ref1, "and", ref2, "is", result)
    return result


def add_tag(tag, ref):
    print("Adding tag", tag, "to", ref)
    cmd = ["git", "tag", tag, ref]
    return subprocess.check_output(cmd).strip()


def push(remote, branch):
    print("Pushing branch", branch, "to remote", remote)
    cmd = ["git", "push", remote, branch]
    return subprocess.check_output(cmd).strip()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--downstream-remote", default="stackhpc",
                        help="Name of the upstream git remote. Default is "
                             "'stackhpc'")
    parser.add_argument("-p", "--prefix", default="stackhpc/",
                        help="Prefix for downstream tags. "
                             "Default is 'stackhpc/'")
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
    downstream_prefix = parsed_args.prefix

    fetch(upstream_remote)
    fetch(downstream_remote)

    upstream_branch = "stable/{}".format(release)
    upstream_ref = rev_parse("{}/{}".format(upstream_remote, upstream_branch))

    downstream_branch = "stackhpc/{}".format(release)
    downstream_ref = rev_parse("{}/{}".format(downstream_remote, downstream_branch))

    downstream_tag = most_recent_tag(downstream_ref)
    downstream_tag_ref = rev_parse(downstream_tag)

    if downstream_tag_ref == downstream_ref:
        print("Latest downstream commit is already tagged as", downstream_tag)
        return

    if downstream_tag.startswith(downstream_prefix):
        print("Found downstream tag", downstream_tag)
        downstream_tag_without_suffix = downstream_tag[len(downstream_prefix):]
        downstream_base, downstream_patch = downstream_tag_without_suffix.split('-')
    else:
        downstream_base, downstream_patch = downstream_tag, 0
        print("Found no downstream tag - basing off of upstream tag", downstream_base)

    merge_base_ref = merge_base(upstream_ref, downstream_ref)
    upstream_tag = most_recent_tag(merge_base_ref)

    if downstream_base == upstream_tag:
        new_patch = int(downstream_patch) + 1
    else:
        new_patch = 1

    new_tag = "{}{}-{}".format(downstream_prefix, upstream_tag, new_patch)
    add_tag(new_tag, downstream_ref)

    push(downstream_remote, new_tag)


if __name__ == "__main__":
    main()
