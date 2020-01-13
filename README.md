[![Build Status](https://travis-ci.com/AtakamaLLC/lint-diffs.svg?branch=master)](https://travis-ci.com/AtakamaLLC/lint-diffs)
[![Code Coverage](https://codecov.io/gh/AtakamaLLC/lint-diffs/branch/master/graph/badge.svg)](https://codecov.io/gh/AtakamaLLC/lint-diffs)

# lint-diffs

lint-diffs is a simple command line tool for running a set of arbitrarty linters
on a set of 'unified diffs'.

Errors on diff-lines will always be reported.   Errors on non-diff lines can also
be reported, depending on severity.

First you need some diffs, then you pipe it to lint-diffs:

`git diff -U0 origin/master | lint-diffs`

... or in mercurial: `hg outgoing -p | lint-diffs`

The default and only preconfigured tool for python is "pylint".

Configuration:

`lint-diffs` will read a config files from `~/.config/lint-diffs` and/or `./.lint-diffs`.

Example:

```ini
[pylint]
always_report=E.*

[flake8]
extensions=.py

[rubocop]
extensions=.rb
always_report=(E.*|W.*)

[eslint]
extensions=.js

[shellcheck]
extensions=.sh
```

In this example, a flake8 and pylint are run on every diff file ending in `.py`.
Additionally, ruby, eslint and shell script linters have been enabled.   The
ruby linter has been modified to always report warnings, on any changed file,
not just changed lines.

To add new linters:

- The linter has to report to stdout
- The linter has to have a regex that produces a full file path, a line number
  and an error class
- The line numbers and file paths have to match diff target file paths

To enable or disable linters change the 'extensions' config.

Goals:

- Runs with good defaults for many people
- Should be easy to modify the config for any linter
- Should be easy to use with any vcs
