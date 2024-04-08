from . import data
import gha_scanner
import yaml
import pytest

config = yaml.safe_load(open("gha_scanner.config", "r").read())
gh = gha_scanner.Scanner(config)


def test_check_prt_pass():
    result = gha_scanner.checks.check_prt(data.passing_workflow)
    expected = True
    assert result == expected


def test_check_prt_fail():
    result = gha_scanner.checks.check_prt(data.failing_check_prt)
    expected = False
    assert result == expected


def test_check_concurrency_pass():
    result = gha_scanner.checks.check_concurrency(data.passing_workflow)
    expected = True
    assert result == expected


def test_check_concurrency_fail():
    result = gha_scanner.checks.check_concurrency(data.failed_concurrency)
    expected = False
    assert result == expected
