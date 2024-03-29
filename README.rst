=====================
Naming Things is Hard
=====================

Tools for versioning, tagging and maintaining OpenStack source code repository
forks.

Versioning
==========

We typically use the following patterns to manage downstream software.

Branches
    Use ``<prefix><release>``. For the ``stackhpc`` Github organisation,
    the prefix is ``stackhpc/``. The release is a lower case name of the
    OpenStack release. For the Rocky releae, we use ``stackhpc/rocky``.
    The corresponding upstream branch (e.g. ``stable/rocky``) is periodically
    merged into the fork.

Versions
    Use ``<prefix><upstream version>.<patch>``. For the ``stackhpc`` Github
    organisation, the prefix is ``stackhpc/``. The upstream version is taken
    from the most recent upstream tag on the stable branch. The patch number is
    a monotonically increasing number, starting at 1. When a new upstream tag
    is released, the patch number resets to 1. For example, with an upstream
    version of ``3.2.1``, we start our versioning at ``stackhpc/3.2.1.1``.

Tools
=====

``os-cherry-pop.py``
    Proposes a list of downstream patches to cherry pick for a new release
    branch. The list is generated based on the downstream patches in a previous
    release, and accounts for patches that have been merged into the new
    release. It also looks for newer versions of a patch on later branches.

``os-downstream-tag.py``
    Determines an appropriate version to assign to a downstream fork of an
    OpenStack project, then creates a tag and pushes it to the downstream
    repository.

``os-upstream-sync.py``
    Syncs a downstream fork of an OpenStack project with upstream. A new branch
    is created for the sync, on which the branches are merged, before being
    pushed to the downstream repository.
