#!/usr/bin/env python3

"""
Determines an appropriate version to assign to a downstream fork of an
OpenStack project, then creates a tag and pushes it to the downstream
repository.
"""

from __future__ import print_function
import argparse
import os
import subprocess
import sys


DEFAULT_RELEASE = os.environ.get("DEFAULT_RELEASE", "victoria")


def rev_parse(ref):
    cmd = ["git", "rev-parse", ref]
    output = subprocess.check_output(cmd)
    return output.decode(encoding=sys.stdout.encoding).strip()


def fetch(remote):
    print("Fetching from", remote)
    cmd = ["git", "fetch", remote]
    output = subprocess.check_output(cmd)
    return output.decode(encoding=sys.stdout.encoding).strip()


def most_recent_tag(ref):
    cmd = ["git", "describe", ref, "--exclude=*[a-z]", "--abbrev=0", "--tags"]
    output = subprocess.check_output(cmd)
    return output.decode(encoding=sys.stdout.encoding).strip()


def merge_base(ref1, ref2):
    cmd = ["git", "merge-base", ref1, ref2]
    result = subprocess.check_output(cmd).strip()
    print("Merge base of", ref1, "and", ref2, "is", result)
    return result


def tag_exists(tag):
    cmd = ["git", "tag", "-l", tag]
    return False if not subprocess.check_output(cmd) else True


def add_tag(tag, ref):
    print("Adding tag", tag, "to", ref)
    cmd = ["git", "tag", tag, ref]
    return subprocess.check_output(cmd).strip()


def push_tag(remote, tag):
    print("Pushing tag", tag, "to remote", remote)
    cmd = ["git", "push", remote, tag]
    output = subprocess.check_output(cmd)
    return output.decode(encoding=sys.stdout.encoding).strip()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--downstream-remote", default="stackhpc",
                        help="Name of the downstream git remote. Default is "
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
        downstream_tag_without_prefix = downstream_tag[len(downstream_prefix):]
        dotted_split = downstream_tag_without_prefix.split('.')
        if len(dotted_split) != 4:
            print("Unable to parse most recent downstream tag", downstream_tag)
            sys.exit(1)
        downstream_base = ".".join(dotted_split[:3])
        downstream_patch = int(dotted_split[3])
    else:
        downstream_base, downstream_patch = downstream_tag, 0
        print("Found no downstream tag - basing off of upstream tag", downstream_base)

    merge_base_ref = merge_base(upstream_ref, downstream_ref)
    upstream_tag = most_recent_tag(merge_base_ref)
    print("Most recent upstream tag:", upstream_tag)

    if downstream_base == upstream_tag:
        new_patch = int(downstream_patch) + 1
    else:
        new_patch = 1

    new_tag = "{}{}.{}".format(downstream_prefix, upstream_tag, new_patch)

    if tag_exists(new_tag):
        print(f'Error: {new_tag} already exists as an unreachable tag, please delete and retry')
        sys.exit(1)
    
    add_tag(new_tag, downstream_ref)

    push_tag(downstream_remote, new_tag)


if __name__ == "__main__":
    main()
