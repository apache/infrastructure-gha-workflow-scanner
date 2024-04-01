from . import data
import gha_scanner
import yaml
import pytest
import json

config = yaml.safe_load(open("gha_scanner.config", "r").read())
gh = gha_scanner.Scanner(config)


def test_list_flows():
    result = gh.list_flows(data.test_commit)
    expected = data.list_flows_expected
    assert json.dumps(result, sort_keys=True) == json.dumps(expected, sort_keys=True)

def test_fetch_flow():
    result = gh.fetch_flow(data.test_commit, data.test_wdata)
    expected = data.fetch_flow_expected
    print(result)
    open("resultfile", "w+").write(json.dumps(result))
    assert result == expected


