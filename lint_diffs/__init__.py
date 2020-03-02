#!/usr/bin/env python

"""
Runs one or more linters, but only outputs errors if diffs have lint issues.

Exports:
    main()
"""

import sys
import subprocess
import io
import re
import os
import configparser
import logging
import argparse
import multiprocessing.dummy
from threading import Lock

from typing import NamedTuple
from unidiff import PatchSet


log = logging.getLogger("lint_diffs")
__all__ = ["main"]
__version__ = "0.1.18"
USER_CONFIG = "~/.config/lint-diffs"
CONSOLE_LOCK = Lock()
NOTFOUND = -9


class LintResult(NamedTuple):
    """Summary results from running diff-lint."""

    skipped: int            # regex mismatch
    mine: int               # my line no
    always: int             # always match err
    total: int              # total lines in output
    other: int              # lint errs not in my lines
    returncode: int         # err code
    output: str             # one line per error

    @property
    def linted(self):
        """Total of always + mine."""
        # bug in pylint + namedtuple
        return self.always + self.mine     # pylint: disable=no-member


def read_config() -> configparser.ConfigParser:
    """Read the default config, then read the user config."""
    config = configparser.ConfigParser()

    config.read(
        [
            os.path.join(os.path.dirname(__file__), 'default_config'),
            os.path.expanduser(USER_CONFIG),
            ".lint_diffs",
            ".lint-diffs",
        ]
    )

    if "main" not in config:
        config.add_section("main")

    return config


def _str_to_int_or_bool(val: str) -> int:
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    return int(val)


def _config_to_dict(config) -> dict:
    """Convert dict to internal dictionary."""
    final = {}
    for secname, sec in config.items():
        final[secname] = sec

        ext = sec.get("extensions")
        if not ext:
            log.debug("Ignoring %s section with no file extensions", secname)
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
            if key in ("parallel", "debug", "strict"):
                val = _str_to_int_or_bool(val)
            final[key] = val

    return final


def read_diffs():
    """Read the diffs from stdin, must be parsable by unidiff."""
    patch_set = PatchSet(sys.stdin)
    diff_lines = {}
    for patch in patch_set:
        lnos = set()
        for hunk in patch:
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
    placeholder_found = False
    joined = []
    for elem in cmd:
        if elem == '"$@"':
            joined += files
            placeholder_found = True
        else:
            joined.append(elem)

    if not placeholder_found:
        joined += files

    try:
        ret = subprocess.run(joined, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf8", check=False)
    except FileNotFoundError:
        return LintResult(returncode=NOTFOUND, skipped=0, total=0,
                          mine=0, always=0, other=0, output="Command not found for '%s'\n" % linter)

    return parse_output(diffs, ret, regex, always_report)


def parse_output(diffs, ret, regex, always_report):
    """Parse linter output."""
    skipped_cnt = 0
    total_cnt = 0
    always_cnt = 0
    mine_cnt = 0
    other_cnt = 0
    outf = io.StringIO()

    for line in ret.stdout.split("\n"):
        total_cnt += 1
        match = re.match(regex, line)
        if not match:
            skipped_cnt += 1
            print("#", line, file=outf)
            continue

        fname, lno, err = match["file"], match["line"], match["err"]
        fname = fname.translate(str.maketrans("\\", "/"))

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

        print(line, file=outf)

    return LintResult(returncode=ret.returncode, skipped=skipped_cnt, total=total_cnt,
                      mine=mine_cnt, always=always_cnt, other=other_cnt, output=outf.getvalue())


def _alter_config_with_args(args, config):
    # command line opts pushed into config here (maybe need schema?)
    if args.debug is not None:
        config["main"]["debug"] = "1"

    if args.parallel is not None:
        config["main"]["parallel"] = str(args.parallel)

    if args.strict is not None:
        config["main"]["strict"] = "1"

    if "debug" not in config["main"]:
        config["main"]["debug"] = "0"

    if "strict" not in config["main"]:
        config["main"]["strict"] = "0"

    for opt in args.option:
        name, opt = opt.split(":", 1)
        opt, val = opt.split("=", 1)
        if name not in config:
            config.add_section(name)
        config[name][opt] = val


def _parse_args():
    parser = argparse.ArgumentParser(
        description='Use unified diff from stdin to guide linting.',
        epilog="See https://github.com/AtakamaLLC/lint-diffs for configuration examples.")
    parser.add_argument("--debug", action="store_true", help="Debug regex parsing and lint-diff config", default=None)
    parser.add_argument("--parallel", action="store", type=int, help="Number of parallel jobs.", default="1")
    parser.add_argument("--strict", action="store_true", help="Fail if linter not installed.", default=None)
    parser.add_argument("--config", "-c", action="store", help="Location of config (~/.config/lint-diffs)", default="~/.config/lint-diffs")
    parser.add_argument("--option", "-o", action="append", help="Pass option to underlying linter (name:opt=value)", default=[])
    args = parser.parse_args()
    return args


def main():
    """Command line for lint-diffs.

    Usage:
        `git diff -U0 | lint-diffs`

    """
    # most stuff should be in the config, but we allow a special "--debug"
    # flag that doesn't get passed to the linter
    # if this is a problem, remove it
    logging.basicConfig()

    args = _parse_args()

    py_config = read_config()

    _alter_config_with_args(args, py_config)

    config = _config_to_dict(py_config)

    if config["debug"]:
        log.setLevel(logging.DEBUG)

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

    strict = config.get("strict", False)
    parallel = config.get("parallel", 1)

    log.debug("linters: %s, strict: %s, parallel: %s", linters, strict, parallel)

    def print_lint(item):
        """Run linter, print output to screen."""
        linter, files = item
        ret = do_lint(config, linter, diffs, list(files))
        with CONSOLE_LOCK:
            print(ret.output)
            print("=== %s: mine=%s, always=%s\n" % (linter, ret.mine, ret.always))
        if ret.returncode == NOTFOUND:
            return 1 if strict else 0
        return ret.linted > 0 and (ret.returncode or 1)

    if parallel > 1:
        pool = multiprocessing.dummy.Pool(parallel)
        mapper = pool.map
    else:
        mapper = map

    exitcode = max(mapper(print_lint, linters.items()))

    if exitcode != 0:
        sys.exit(exitcode)


if __name__ == "__main__":
    main()
