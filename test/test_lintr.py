"""Tests for lint_diffs."""

import sys
import io
import logging

from tempfile import NamedTemporaryFile
from unittest.mock import patch
from lint_diffs import main, read_diffs, read_config


log = logging.getLogger("lint_diffs")
log.setLevel(logging.DEBUG)

diff = """
diff --git a/test/badcode.py b/test/badcode.py
index 81e7297..dcdbd1f 100644
--- a/test/badcode.py
+++ b/test/badcode.py
@@ -2 +2 @@ def foo(baz):
-    print(bar);
+    print(bar)
    """


def test_diff_read():
    """Read diffs from stdin test."""
    with patch.object(sys, "stdin", io.StringIO(diff)):
        dlines = read_diffs()
        assert "test/badcode.py" in dlines
        assert dlines["test/badcode.py"] == {2}


def test_conf_read():
    """User config test."""
    with NamedTemporaryFile() as conf:
        conf.write(b"""
[pylint]
always_report=W0613
        """)
        conf.flush()
        with patch("lint_diffs.USER_CONFIG", conf.name):
            conf = read_config()
            assert conf["pylint"]["always_report"] == 'W0613'
            assert conf["pylint"]["command"]
            assert conf["pylint"]["regex"]


def test_noconf(capsys):
    """Basic main test."""
    with patch.object(sys, "stdin", io.StringIO(diff)), \
            NamedTemporaryFile() as conf:
        conf.write(b"""
        """)
        conf.flush()
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
    with patch.object(sys, "stdin", io.StringIO(diff)), \
            NamedTemporaryFile() as conf:
        conf.write(b"""
[pylint]
always_report=W0613
        """)
        conf.flush()
        with patch("lint_diffs.USER_CONFIG", conf.name):
            try:
                main()
            except SystemExit as ex:
                assert ex.code != 0

            cap = capsys.readouterr()

            assert 'W0613' in cap.out
            assert 'E0602' in cap.out
