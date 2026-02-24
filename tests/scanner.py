from . import data
import gha_scanner
import yaml
import pytest
import json
import re
import os

config = yaml.safe_load(open("gha-workflow-scanner.yaml", "r").read())
gh = gha_scanner.Scanner(config)


def test_ghtoken():
    token = config["gha_token"]
    try:
        result = gh.s.get(gh.ghurl)
        print(result.status_code)
    except ConnectionError as e:
        print(e)

    assert result.status_code == 200


def test_excluded_flow():
    result = gh.scan_flow(data.excluded_workflow['commit'], data.excluded_workflow['wdata'])
    expected = [{"max-parallel": True}, []]
    assert json.dumps(result) == json.dumps(expected)

def test_fetch_flow():
    result = gh.fetch_flow(data.passing_commit, data.passing_wdata)
    expected = data.passing_workflow
    assert json.dumps(result) == json.dumps(expected)

