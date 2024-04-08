#!/usr/bin/env python3
import yaml
import gha_scanner
import argparse

parser = argparse.ArgumentParser(description="Start the GHA Scanner")
parser.add_argument('-c', '--config', help="Alternate Config", default="gha_scanner.config")
args = parser.parse_args()

if __name__ == "__main__":
    gh = gha_scanner.Scanner(yaml.safe_load(open(args.config, "r").read()))
    gh.scan()
