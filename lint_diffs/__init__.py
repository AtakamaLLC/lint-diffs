#!/usr/bin/env python

"""
Runs one or more linters, but only outputs errors if diffs have lint issues.

Exports:
    main()
"""

import sys
import subprocess
import re
import os
import configparser
import logging

from typing import NamedTuple
from unidiff import PatchSet


log = logging.getLogger("lint_diffs")
__all__ = ["main"]
__version__ = "0.1.9"
USER_CONFIG = "~/.config/lint-diffs"


class LintResult(NamedTuple):
    """Summary results from running diff-lint."""

    skipped: int            # regex mismatch
    mine: int               # my line no
    always: int             # always match err
    total: int              # total lines in output
    other: int              # lint errs not in my lines
    returncode: int         # err code

    @property
    def linted(self):
        """Total of always + mine."""
        # bug in pylint + namedtuple
        return self.always + self.mine     # pylint: disable=no-member


def read_config():
    """Read the default config, then read the user config."""
    config = configparser.ConfigParser()

    config.read(
        [
            os.path.join(os.path.dirname(__file__), 'default_config'),
            os.path.expanduser(USER_CONFIG),
            ".lint_diffs",
        ]
    )

    final = {}
    for secname, sec in config.items():
        final[secname] = sec

        ext = sec.get("extensions")
        if not ext:
            log.debug("Ignoring section with no file extensions")
            continue
        cmd = sec.get("command")
        regex = sec.get("regex", "")
        ok = True
        if "file" not in regex:
            log.error("Invalid regex for %s, skipping", secname)
            ok = False
        if not cmd:
            log.error("Invalid command for %s, skipping", secname)
            ok = False

        if not ok:
            continue

        for ext in ext.split(" "):
            ext.strip()
            if ext not in final:
                final[ext] = []

            final[ext].append(secname)

    if "main" in final:
        for key, val in final["main"].items():
            final[key] = val

    return final


def read_diffs():
    """Read the diffs from stdin, must be parsable by unidiff."""
    patch_set = PatchSet(sys.stdin)
    diff_lines = {}
    for patch in patch_set:
        for hunk in patch:
            lnos = set()
            for line_info in hunk.target_lines():
                lnos.add(line_info.target_line_no)
        diff_lines[patch.path] = lnos
    return diff_lines


def do_lint(config, linter, diffs, files):
    """Given a linter config, run lint, and only output lines that are in the diffs.

    Args:
        config: main config dict
        linter: name of linter from config
        diffs: dict of filename to lineno set
        files: list of file paths
    """
    cmd = config[linter]["command"]
    always_report = config[linter].get("always_report")
    regex = config[linter]["regex"]

    log.debug("linter: %s %s %s", cmd, regex, always_report)

    cmd = cmd.split(" ")

    ret = subprocess.run(cmd + sys.argv[1:] + files, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf8", check=False)

    return parse_output(config, diffs, ret, regex, always_report)


def parse_output(config, diffs, ret, regex, always_report):
    """Parse linter output."""
    skipped_cnt = 0
    total_cnt = 0
    always_cnt = 0
    mine_cnt = 0
    other_cnt = 0
    for line in ret.stdout.split("\n"):
        total_cnt += 1
        match = re.match(regex, line)
        if not match:
            skipped_cnt += 1
            if config.get("debug"):
                print("#", line)
            continue

        fname, lno, err = match["file"], match["line"], match["err"]

        try:
            lno = int(lno)
        except ValueError:
            log.debug("lineno parse issue: %s", line)

        always_match = False

        if always_report:
            match = re.match(always_report, err)
            if match:
                always_match = True

        if lno not in diffs.get(fname, []):
            if not always_match:
                other_cnt += 1
                continue
            always_cnt += 1
        else:
            mine_cnt += 1

        print(line)

    return LintResult(returncode=ret.returncode, skipped=skipped_cnt, total=total_cnt, mine=mine_cnt, always=always_cnt, other=other_cnt)


def main():
    """Command line for lint-diffs.

    Usage:
        `git diff -U0 | lint-diffs`

    """
    # most stuff should be in the config, but we allow a special "--debug"
    # flag that doesn't get passed to the linter
    # if this is a problem, remove it
    debug = False
    logging.basicConfig()
    try:
        debug = sys.argv.index("--debug")
        sys.argv.pop(debug)
        log.setLevel(logging.DEBUG)
    except ValueError:
        pass

    config = read_config()
    if debug:
        config["debug"] = True
    diffs = read_diffs()

    log.debug("diffs: %s", list(diffs))

    linters = {}
    for fname in diffs:
        _, ext = os.path.splitext(fname)
        if ext in config:
            for linter_name in config[ext]:
                if linter_name not in linters:
                    linters[linter_name] = set()
                linters[linter_name].add(fname)

    if not linters:
        log.debug("no files need linting")
        return

    log.debug("linters: %s", linters)

    exitcode = 0
    for linter, files in linters.items():
        ret = do_lint(config, linter, diffs, list(files))
        if ret.linted > 0:
            exitcode = ret.returncode or 1
        print("=== %s: mine=%s, always=%s\n" % (linter, ret.mine, ret.always))

    if exitcode != 0:
        sys.exit(exitcode)


if __name__ == "__main__":
    main()
