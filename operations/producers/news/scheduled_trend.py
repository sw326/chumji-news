#!/usr/bin/env python3
"""Backward-compatible trend-only scheduled entrypoint."""
import argparse
import sys

try:
    from .scheduled_profile import main as profile_main
except ImportError:
    from scheduled_profile import main as profile_main


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    return profile_main(["trend"])


if __name__ == "__main__":
    sys.exit(main())
