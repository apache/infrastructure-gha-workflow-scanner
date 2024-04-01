#!/usr/bin/env python3
import yaml
import gha_scanner

if __name__ == "__main__":
    gh = gha_scanner.Scanner(yaml.safe_load(open("gha_scanner.config","r").read()))
    gh.scan()
