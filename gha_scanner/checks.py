#!/usr/bin/env python3
import logging
log = logging.getLogger(__name__)

# POLICY VALUES
GHA_MAX_CONCURRENCY = 20

### WORKFLOW CHECK FUNCTION REQUIREMENTS ###
# Workflow check must be registered in WORKFLOW_CHECKS to run.
# Require only the yaml workflow.
# Return only True or False.
# * Return True if the test is passed.
# * Return False is the test is failed.


def check_prt(wdata):
    log.debug("Checking workflow for `pull_request_target` trigger")
    try:
        if "pull_request_target" in wdata.get(True, {}):
            log.debug("Pull Request Target test failed")
            return False
        else:
            log.debug("Pull Request Target test Passed")
            return True
    except:
        log.error(wdata)


def check_concurrency(wdata):
    log.debug("Checking workflow for max concurrency")
    for job in wdata["jobs"]:
        if "matrix" in wdata["jobs"][job].get("strategy", {}):
            concurrency = 1
            for options in wdata["jobs"][job]["strategy"]["matrix"]:
                concurrency *= len(wdata["jobs"][job]["strategy"]["matrix"][options])
            if (
                concurrency >= GHA_MAX_CONCURRENCY
                and "max-parallel" not in wdata["jobs"][job]["strategy"]
            ):
                log.debug("max-concurrency check Failed")
                return False
            else:
                log.debug("max-concurrency check Passed")
                return True
        else:
            return True


### WORKFLOW CHECK MAP
# "check_name": {
#     "func": functionName,
#     "desc": "check description / link to doc / remediation step"

WORKFLOW_CHECKS = {
    "pull_request_target": {
        "func": check_prt,
        "desc": "`pull_request_target` was found as a workflow trigger. see https://cwiki.apache.org/confluence/pages/viewpage.action?pageId=321719166#GitHubActionsSecurity-Buildstriggeredwithpull_request_target, for more details"
    },
    "max-parallel": {
        "func": check_concurrency,
        "desc": "`max-parallel: %s` is required for job matrices. https://infra.apache.org/github-actions-policy.html#:~:text=All%20workflows%C2%A0MUST%C2%A0have%20a%20job%20concurrency%20level%20less%20than%20or%20equal%20to%2020.%20This%20means%20a%20workflow%20cannot%20have%20more%20than%2020%20jobs%20running%20at%20the%20same%20time%20across%20all%20matrices."
        % GHA_MAX_CONCURRENCY,
    },
}
