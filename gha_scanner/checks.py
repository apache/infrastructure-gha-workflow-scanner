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
        "desc": "`pull_request_target` was found as a workflow trigger.",
    },
    "max-parallel": {
        "func": check_concurrency,
        "desc": "`max-parallel: %s` is required for job matrices."
        % GHA_MAX_CONCURRENCY,
    },
}
