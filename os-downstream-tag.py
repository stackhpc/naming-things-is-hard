#!/usr/bin/env python3

"""
Determines an appropriate version to assign to a downstream fork of an
OpenStack project, then creates a tag and pushes it to the downstream
repository.
"""

from __future__ import print_function
import argparse
import os
import re
import subprocess
import sys


DEFAULT_RELEASE = os.environ.get("DEFAULT_RELEASE", "wallaby")


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


def most_recent_downstream_tag(ref, downstream_prefix, upstream_tag):
    # List tags matching the expected pattern.
    prefix = f"{downstream_prefix}{upstream_tag}"
    cmd = ["git", "tag", "-l", f"{prefix}.*"]
    output = subprocess.check_output(cmd)

    # git tag -l <pattern> just does a shell match. Filter out any tags that
    # aren't properly formatted.
    tags = output.decode(encoding=sys.stdout.encoding).strip().splitlines()
    pattern = re.compile(r"^" + re.escape(prefix) + r"\.[\d]+$")
    tags = [t for t in tags if pattern.match(t)]
    if not tags:
        return

    def tag_patch_key(tag):
        # Sort based on the patch number.
        patch = tag.split(".")[-1]
        return int(patch, base=10)

    return sorted(tags, key=tag_patch_key, reverse=True)[0]


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

    upstream_refs = [
        "{}/stable/{}".format(upstream_remote, release),
        "{}/unmaintained/{}".format(upstream_remote, release),
        "{}-eol".format(release),
        str(release),
    ]
    for ref in upstream_refs:
        print(f"Checking for existence of upstream {ref}")
        try:
            upstream_ref = rev_parse(ref)
            break
        except subprocess.CalledProcessError:
            print(f"Failed to find ref for {ref}")
    else:
        print("Unable to find any upstream branches or tags")
        sys.exit(1)

    downstream_branch = "stackhpc/{}".format(release)
    downstream_ref = rev_parse("{}/{}".format(downstream_remote, downstream_branch))

    merge_base_ref = merge_base(upstream_ref, downstream_ref)
    upstream_tag = most_recent_tag(merge_base_ref)
    print("Most recent upstream tag:", upstream_tag)

    downstream_tag = most_recent_downstream_tag(downstream_ref, downstream_prefix, upstream_tag)

    if downstream_tag:
        downstream_tag_ref = rev_parse(downstream_tag)

        if downstream_tag_ref == downstream_ref:
            print("Latest downstream commit is already tagged as", downstream_tag)
            return

        print("Found downstream tag", downstream_tag)
        downstream_patch = int(downstream_tag.split('.')[-1])
        new_patch = int(downstream_patch) + 1
    else:
        print("Found no downstream tag - basing off of upstream tag")
        new_patch = 1

    new_tag = "{}{}.{}".format(downstream_prefix, upstream_tag, new_patch)

    if tag_exists(new_tag):
        print(f'Error: {new_tag} already exists as an unreachable tag, please delete and retry')
        sys.exit(1)
    
    add_tag(new_tag, downstream_ref)

    push_tag(downstream_remote, new_tag)


if __name__ == "__main__":
    main()
