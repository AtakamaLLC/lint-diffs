### lint-diffs

lint-diffs is a simple command line tool for running a linter on diffs.


First you need some diffs, then you pipe it to lint-diffs:

`git diff origin/master | lint-diffs`


The default tool is "pylint".

Configuration:

lint-diffs can read a config file from ~/.config/lint-diffs

Example:

```
[pylint]
extensions=.py
command=pylint
regex=(?P<file>[^:]+):(?P<line>[^:]+):[^:]+: .: (?P<err>[^:]+)
always_report=E.*

[rubocop]
extensions=.rb
command=rubocop app spec
regex=(?P<file>[^:]+):(?P<line>[^:]+):[^:]+: (?P<err>.: [^:]+)
always_report=(E.*|W.*)
```
