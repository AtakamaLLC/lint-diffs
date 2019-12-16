[![Build Status](https://travis-ci.com/AtakamaLLC/lint-diffs.svg?branch=master)](https://travis-ci.com/AtakamaLLC/lint-diffs)
[![Code Coverage](https://codecov.io/gh/AtakamaLLC/lint-diffs/branch/master/graph/badge.svg)](https://codecov.io/gh/AtakamaLLC/lint-diffs)"

### lint-diffs

lint-diffs is a simple command line tool for running an arbitrarty linter 
on a set of 'unified diffs'.

First you need some diffs, then you pipe it to lint-diffs:

`git diff -U0 origin/master | lint-diffs`

The default and only preconfigured tool for python is "pylint".

Configuration:

`lint-diffs` will read a config files from `~/.config/lint-diffs` and/or `./.lint-diffs`.

Example:

```
[pylint]
always_report=E.*

[flake8]
extensions=.py

[rubocop]
extensions=.rb
command=rubocop app spec
regex=(?P<file>[^:]+):(?P<line>[^:]+):[^:]+: (?P<err>.: [^:]+)
always_report=(E.*|W.*)
```

In this example, a flake8 and pylint are run on every diff file ending in `.py`.   
Additionally, a ruby linter has been added.

To add new linters:
 - The linter has to report to stdout
 - The linter has to have a regex that produces a full file path, a line number and an error class
 - The line numbers and file paths have to match diff target file paths

Goals:
 - Runs with good defaults for many people
 - Should be easy to modify the config for new linters
 - Should be easy to use with other vcs
