"""Tests for lint_diffs."""

# pylint: disable=missing-docstring
# flake8: noqa=D103

import sys
import io
import logging

from tempfile import NamedTemporaryFile
from unittest.mock import patch

import pytest

from lint_diffs import main, read_diffs, read_config, _config_to_dict, _str_to_int_or_bool, parse_output


log = logging.getLogger("lint_diffs")
log.setLevel(logging.DEBUG)

DIFF_OUTPUT = """
diff --git a/test/badcode.py b/test/badcode.py
index 81e7297..dcdbd1f 100644
--- a/test/badcode.py
+++ b/test/badcode.py
@@ -2 +2 @@ def foo(baz):
-    print(bar);
+    print(bar)
    """

GOOD_DIFF_OUTPUT = """
diff --git a/test/goodcode.py b/test/goodcode.py
index 81e7297..dcdbd1f 100644
--- a/test/goodcode.py
+++ b/test/goodcode.py
@@ -2 +2 @@ def foo(baz):
-    print(bar);
+    print(bar)
    """

NOT_LINT_TXT_DIFF = """
diff --git a/test/some.txt b/test/some.txt
index 81e7297..dcdbd1f 100644
--- a/test/some.txt
+++ b/test/some.txt
@@ -2 +2 @@ def foo(baz):
-    print(bar);
+    print(bar)
    """


PYLINT_OUTPUT = """************* Module badcode
test/badcode.py:1:0: C0111: Missing module docstring (missing-docstring)
test/badcode.py:1:0: C0102: Black listed name "foo" (blacklisted-name)
test/badcode.py:1:0: C0102: Black listed name "baz" (blacklisted-name)
test/badcode.py:1:0: C0111: Missing function docstring (missing-docstring)
test/badcode.py:2:10: E0602: Undefined variable 'bar' (undefined-variable)
test/badcode.py:1:8: W0613: Unused argument 'baz' (unused-argument)
test/badcode.py:XX:ZZ: FFF: Bad lineno is allowed, but only reported if code matches

----------------------------------------------------------------------
Your code has been rated at -40.00/10 (previous run: -40.00/10, +0.00)"""

DIFF_CPP = """
diff --git a/src/vsss.cpp b/src/vsss.cpp
index 81e7297..dcdbd1f 100644
--- a/src/vsss.cpp
+++ b/src/vsss.cpp
@@ -6 +6 @@ void foo(int baz):
-    print(bar)
+    print(bar);
    """


CLANG_OUTPUT = """
32069 warnings generated.
src/vsss.cpp:725:18: note: the definition seen here
bool Vida::Kata::vsss_verify(const std::string & share_json) {
                 ^
src/vsss.cpp:6:1: warning: #includes are not sorted properly [llvm-include-order]
#include "json.hpp"
^        ~~~~~~~~~~
         "bignum.hpp"
src/vsss.cpp:31:24: warning: pass by value and use std::move [modernize-pass-by-value]
vsss_share::vsss_share(Bignum _index, Bignum _data, int _m, int _n, const ECPtr &_gen, const ECPtr &_gen_k,
                       ^
src/vsss.cpp:31:88: warning: pass by value and use std::move [modernize-pass-by-value]
"""


def test_parse_arg_str():
    assert _str_to_int_or_bool("true")
    assert not _str_to_int_or_bool("false")
    assert _str_to_int_or_bool("1") == 1
    with pytest.raises(ValueError):
        _str_to_int_or_bool("")

def test_parse_out():
    class Ret:  # pylint: disable=all
        stdout = PYLINT_OUTPUT
        returncode = 0

    config = {}
    regex = r"(?P<file>[^:]+):(?P<line>[^:]+):[^:]+: (?P<err>[^ :]+)"
    ret = parse_output(config, {"test/badcode.py": [2]}, Ret(), regex, "W0613")
    assert ret.skipped == 4
    assert ret.linted == 2
    assert "W0613" in ret.output
    assert "E0602" in ret.output


def test_diff_read():
    with patch.object(sys, "stdin", io.StringIO(DIFF_OUTPUT)):
        dlines = read_diffs()
        assert "test/badcode.py" in dlines
        assert dlines["test/badcode.py"] == {2}


def test_conf_read():
    with NamedTemporaryFile() as conf:
        conf.write(b"""
[main]
debug=True

[pylint]
always_report=W0613
        """)
        conf.flush()
        with patch("lint_diffs.USER_CONFIG", conf.name):
            conf = read_config()
            assert conf["pylint"]["always_report"] == 'W0613'
            assert conf["pylint"]["command"]
            assert conf["pylint"]["regex"]
            assert conf["main"]["debug"]


def test_conf_invalid(caplog):
    with NamedTemporaryFile() as conf:
        conf.write(b"""
[invalid_config]
extensions=.wack \t \t
always_report=yeah

[ok_config]
extensions=\t \t.weird \t \t
command=yo
regex=(?P<file>[^:]+):(?P<line>\\d+):[^:]+: (?P<err>[^ :]+)
""")
        conf.flush()

        caplog.clear()
        with patch("lint_diffs.USER_CONFIG", conf.name):
            cfg = read_config()
        exts = _config_to_dict(cfg)

        errs = 0
        for ent in caplog.records:
            if ent.levelname == "ERROR":
                errs += 1

        # invalid extensions don't get loaded
        assert '.wack' not in exts

        # ext with weird whitespace still works
        assert '.weird' in exts

        # missing command + missing regex == 2
        assert errs == 2


def test_noconf(capsys):
    logging.getLogger().setLevel(logging.INFO)
    with patch.object(sys, "stdin", io.StringIO(DIFF_OUTPUT)), \
            NamedTemporaryFile() as conf:
        conf.write(b"""
        """)
        conf.flush()
        sys.argv = ["whatever"]
        with patch("lint_diffs.USER_CONFIG", conf.name):
            try:
                main()
            except SystemExit as ex:
                assert ex.code != 0

            cap = capsys.readouterr()

            assert 'W0613' not in cap.out
            assert 'E0602' in cap.out


def test_always_report(capsys):
    logging.getLogger().setLevel(logging.INFO)
    with patch.object(sys, "stdin", io.StringIO(DIFF_OUTPUT)), \
            NamedTemporaryFile() as conf:
        conf.write(b"""
[main]
debug=True

[pylint]
always_report=W0613
        """)
        conf.flush()
        sys.argv = ["whatever"]
        with patch("lint_diffs.USER_CONFIG", conf.name):
            try:
                main()
            except SystemExit as ex:
                assert ex.code != 0

            cap = capsys.readouterr()

            log.info(cap.out)

            assert 'W0613' in cap.out
            assert 'E0602' in cap.out


def test_noline_noerr(capsys):
    logging.getLogger().setLevel(logging.INFO)
    # One bad code line, but not in diff
    pylint_output = """************* Module badcode
test/badcode.py:1:10: E0602: Undefined variable 'bar' (undefined-variable)

----------------------------------------------------------------------
Your code has been rated at -40.00/10 (previous run: -40.00/10, +0.00)"""

    class Ret:  # pylint: disable=all
        stdout = pylint_output
        returncode = 1

        def __init__(self, *a, **k):
            pass

    with patch.object(sys, "stdin", io.StringIO(DIFF_OUTPUT)):
        with patch("subprocess.run", Ret):
            sys.argv = ["whatever"]
            main()

            cap = capsys.readouterr()

            assert "test/badcode.py" not in cap.out


def test_nolint_txt(caplog):
    with patch.object(sys, "stdin", io.StringIO(NOT_LINT_TXT_DIFF)):
        sys.argv = ["whatever", "--debug"]
        main()

        assert "no files need linting" in caplog.text


def test_debug_mode(caplog):
    sys.argv = ["whatever", "--debug"]
    with patch.object(sys, "stdin", io.StringIO(GOOD_DIFF_OUTPUT)):
        main()
    assert "DEBUG" in caplog.text


def test_custom_opts(caplog):
    sys.argv = ["whatever", "--debug", "-o", "txt:extensions=.txt", "-o", "txt:command=echo hi", "-o", r"txt:regex=(?P<file>[^:]+):(?P<line>\d+):[^:]+: (?P<err>[^ :]+)"]
    with patch.object(sys, "stdin", io.StringIO(NOT_LINT_TXT_DIFF)):
        main()
    assert "echo" in caplog.text

def test_clang():
    sys.argv = ["whatever", "-o", "clang-tidy:extensions=.cpp .hpp"]

    class Ret:  # pylint: disable=all
        stdout = CLANG_OUTPUT
        returncode = 1
        def __init__(self, *a, **k):
            pass

    with patch.object(sys, "stdin", io.StringIO(DIFF_CPP)), patch("subprocess.run", Ret), patch("sys.exit") as exited:
        main()
        exited.assert_called_once_with(1)

def test_parallel(capsys):
    sys.argv = ["whatever", "--parallel", "2", "-o", "flake8:extensions=.py"]

    with patch.object(sys, "stdin", io.StringIO(DIFF_OUTPUT)), patch("sys.exit") as exited:
        main()

    cap = capsys.readouterr()
    assert 'E0602' in cap.out       # pylint
    assert 'F821' in cap.out        # flake8

def test_strict():
    sys.argv = ["whatever", "--strict", "-o", "pylint:command=no-such-command"]

    with patch.object(sys, "stdin", io.StringIO(DIFF_OUTPUT)), patch("sys.exit") as exited:
        main()
        exited.assert_called_once_with(1)

def test_not_strict():
    sys.argv = ["whatever", "-o", "pylint:command=no-such-command"]

    with patch.object(sys, "stdin", io.StringIO(DIFF_OUTPUT)), patch("sys.exit") as exited:
        main()
        exited.assert_not_called()
