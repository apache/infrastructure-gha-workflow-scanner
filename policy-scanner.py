#!/usr/bin/env python3
import re
import os
import sys
import yaml
import subprocess
import asfpy.messaging
import asfpy.pubsub
import argparse
import requests
import logging
import base64
import json
import gha_scanner

DEFAULT_CONTACT = None  # Set to none to go to default project ML

SEND_MESSAGES = False

# LOG BITS
LOGFILE = "logs/gha_scanner.log"
LOG = logging.getLogger(__name__)
VERBOSITY = {
    0: logging.INFO,
    1: logging.CRITICAL,
    2: logging.ERROR,
    3: logging.WARNING,
    4: logging.INFO,
    5: logging.DEBUG,
}
STDOUT_FMT = logging.Formatter(
    "{asctime} [{levelname}] {funcName}: {message}", style="{"
)

if __name__ == "__main__":
    # Listen to commits where a file in .github/workflows/ is modified
    parser = argparse.ArgumentParser()
    logger = parser.add_mutually_exclusive_group()
    logger.add_argument(
        "-d", "--debug", action="store_true", default=False, help="Debug Switch"
    )
    logger.add_argument(
        "-v",
        action="count",
        default=0,
        help="Add logging verbosity",
    )

    parser.add_argument("-t", "--token", help="GitHub Token")

    args = parser.parse_args()
    token = os.environ['dfoulks1']
    # LOG JAZZ!
    if args.debug:
        to_stdout = logging.StreamHandler(sys.stdout)
        to_stdout.setLevel(VERBOSITY[5])
        to_stdout.setFormatter(STDOUT_FMT)
        LOG.setLevel(VERBOSITY[5])
        LOG.addHandler(to_stdout)
    else:
        LOG.setLevel(VERBOSITY[args.v])
        logging.basicConfig(format="%(asctime)s [%(levelname)s] %(funcName)s: %(message)s", filename=LOGFILE)

    gh = gha_scanner.Scanner(token)
    gh.scan()
