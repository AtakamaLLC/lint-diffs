"""Tests for lint_diffs."""

import sys
import io
import logging

from tempfile import NamedTemporaryFile
from unittest.mock import patch
from lint_diffs import main, read_diffs, read_config, parse_output


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


def test_parse_out():
    """Test output parser."""
    class Ret:  # pylint: disable=all
        stdout = PYLINT_OUTPUT
        returncode = 0

    config = {}
    regex = r"(?P<file>[^:]+):(?P<line>[^:]+):[^:]+: (?P<err>[^ :]+)"
    ret = parse_output(config, {"test/badcode.py": [2]}, Ret(), regex, "W0613")
    assert ret.skipped == 4
    assert ret.linted == 2


def test_diff_read():
    """Read diffs from stdin test."""
    with patch.object(sys, "stdin", io.StringIO(DIFF_OUTPUT)):
        dlines = read_diffs()
        assert "test/badcode.py" in dlines
        assert dlines["test/badcode.py"] == {2}


def test_conf_read():
    """User config test."""
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
            assert conf["debug"]


def test_conf_invalid(caplog):
    """User config test invalid confs."""
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
        with patch("lint_diffs.USER_CONFIG", conf.name):
            cfg = read_config()
        errs = 0
        for ent in caplog.records:
            if ent.levelname == "ERROR":
                errs += 1

        # invalid extensions don't get loaded
        assert '.wack' not in cfg

        # ext with weird whitespace still works
        assert '.weird' in cfg

        # missing command + missing regex == 2
        assert errs == 2


def test_noconf(capsys):
    """Test with no conf"""
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
    """Basic main test."""
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
    """One bad code line, but not in diff."""
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
            main()

            cap = capsys.readouterr()

            assert "test/badcode.py" not in cap.out


def test_debug_mode(caplog):
    """Basic main test."""
    with patch.object(sys, "stdin", io.StringIO("")):
        sys.argv = ["whatever", "test/goodcode.py", "--debug"]
        main()
        assert "DEBUG" in caplog.text

