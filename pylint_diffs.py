#!/usr/bin/env python

import sys
import subprocess
import re


def main():
    ret = subprocess.run(['pylint'] + sys.argv[1:], stdout=subprocess.PIPE, encoding="utf8", check=False)

    for line in ret.stdout.split("\n"):
        match = re.match(r"([^:]+):*(\d+):\d+: ([^ :]+)", line)
        if not match:
            print(line)
            continue

        fn, lno, code = match.groups()

        print(line)

    if ret.returncode != 0:
        sys.exit(ret.returncode)


if __name__ == "__main__":
    main()
