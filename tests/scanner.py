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



# def test_list_flows():
# TODO This needs to test teh structure of the commit, not the data.
#    result = gh.list_flows(data.passing_commit)
#    expected = data.passing_list_flows
#    assert json.dumps(result, sort_keys=True) == json.dumps(expected, sort_keys=True)


def test_fetch_flow():
    result = gh.fetch_flow(data.passing_commit, data.passing_wdata)
    expected = data.passing_workflow
    assert json.dumps(result) == json.dumps(expected)


def test_check_prt_pass():
    result = gha_scanner.checks.check_prt(data.passing_workflow)
    expected = True
    assert result == expected
