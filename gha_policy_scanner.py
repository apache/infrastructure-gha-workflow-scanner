#!/usr/bin/env python3
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

DEFAULT_CONTACT = None  # Set to none to go to default project ML

SEND_MESSAGES = False

# LOG BITS
LOGFILE = "gha_scanner.log"
LOG = logging.getLogger(__name__)
VERBOSITY = {
    1: logging.CRITICAL,
    2: logging.ERROR,
    3: logging.WARNING,
    4: logging.INFO,
    5: logging.DEBUG,
}
STDOUT_FMT = logging.Formatter('{asctime} [{levelname}] {funcName}: {message}', style='{')

# POLICY VALUES
GHA_MAX_CONCURRENCY = 10
URL = "https://pubsub.apache.org:2070/git/commit"

### WORKFLOW CHECK FUNCTIONS
# Require only workflow yaml data
# Return True if the test is passed
# Return False is the test is failed


def check_prt(wdata):
    LOG.debug("Checking workflow for `pull_request_target` trigger")
    if "pull_request_target" in wdata.get(True, {}):
        return False
    else:
        return True


def check_concurrency(wdata):
    print(wdata)
    for job in wdata["jobs"]:
        if "matrix" in wdata["jobs"][job].get("strategy", {}):
            concurrency = 1
            for options in wdata["jobs"][job]["strategy"]["matrix"]:
                concurrency *= len(wdata["jobs"][job]["strategy"]["matrix"][options])
            if (
                concurrency >= GHA_MAX_CONCURRENCY
                and "max-parallel" not in wdata["jobs"][job]["strategy"]
            ):
                return False
            else:
                return True
        else:
            print(wdata["jobs"][job]["strategy"])
            return True


### WORKFLOW CHECK MAP

workflow_checks = {
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


### DO NOT EDIT BELOW THIS LINE ###
# TODO Create a GitHubber to manage session AND
#  * Fetch workflow listing by repo (list_flows)
#  * Fetch workflow file content (get_flow)
#  * Compare Workflows


class Scanner:
    # Handles API requests to GitHub
    def __init__(self, args):
        self.ghurl = "https://api.github.com"
        self.args = args
        self.s = requests.Session()
        self.s.headers.update({"Authorization": "token %s" % self.args.token})
        
        LOG.info("Connecting to %s" % URL)
        asfpy.pubsub.listen_forever(self.handler, URL, raw=True)


    def list_flows(self, commit):
        r = self.s.get(
            "%s/repos/apache/%s/actions/workflows?ref=%s"
            % (self.ghurl, commit["project"], commit["hash"])
        )
        return r.json()

    def fetch_flow(self, commit, w_data):
        r = self.s.get(
            "%s/repos/apache/%s/contents/%s?ref=%s"
            % (self.ghurl, commit["project"], w_data["path"], commit["hash"])
        )
        return r.json()

    def scan_flow(self, commit, w_data):
        flow_data = self.fetch_flow(commit, w_data)
        try:
            w_flow = base64.b64decode(flow_data['content'])
        except KeyError as e:
            LOG.critical(flow_data)

        LOG.debug(w_flow)

        result = {}
        m = []
        for check in workflow_checks:
            LOG.info("Checking %s:%s(%s): %s"%(commit['project'],w_data['name'],commit['hash'],check))
            c_data = workflow_checks[check]["func"](w_flow)
            # All workflow checks return a bool, False if the workflow failed.
            if not c_data:
                m.append(
                    "\t" + workflow + ": " + workflow_checks[check]["desc"]
                )
            result[check] = c_data

        return(result, m)

        if len(message["body"]) > 2:
            message["body"].extend(
                [
                    "Please remediate the above as soon as possible.",
                    "If the above is not remediated after 30 days, we will turn off builds",
                    "\nCheers,",
                    "\tASF Infrastructure",
                ]
            )
            self.send_report(message)

    def send_report(self, message):
        # Message should be a dict containing recips, subject, and body. body is expected to be a list of strings
        if SEND_MESSAGES:
            asfpy.messaging.mail(
                recipients=message["recips"],
                subject=message["subject"],
                message="\n".join(message["body"]),
            )
        else:
            if args.debug:
                print("TO: %s" % ",".join(message["recips"]))
                print("SUBJECT: %s" % message["subject"])
                print("MESSAGE: %s" % "\n".join(message["body"]))

    def handler(self, data):
        message = {
            "body": [
                "Greetings PMC!",
                "Our analysis has found that the following GitHub Actions workflows need remediation:",
            ],
            "recips": ["root@apache.org"],
            "subject": "GitHub Actions workflow policy violation",
        }

        if "commit" in data:
            results = {}
            r = [w for w in data["commit"].get("files", []) if ".github/workflows" in w]
            if len(r) > 0:
                if not self.args.lazy:
                    w_data = self.list_flows(data["commit"])
                    for workflow in w_data["workflows"]:
                        [ results[workflow['name']], m ] = self.scan_flow(data["commit"], workflow)
                        message['body'].extend(m)
                    print(results)
                    print(message)
                else:
                    print(data)
            else:
                LOG.info("Scanned commit: %s" % data["commit"]["hash"])
        else:
            LOG.info("Heartbeat Signal Detected")


if __name__ == "__main__":
    # Listen to commits where a file in .github/workflows/ is modified
    parser = argparse.ArgumentParser()
    logger = parser.add_mutually_exclusive_group()
    logger.add_argument("-d", "--debug", action='store_true', default=False, help="Debug Switch")
    logger.add_argument(
        "-v",
        action='count',
        default=4,
        help="Add logging verbosity",
    )

    parser.add_argument("-t", "--token", help="GitHub Token")
    parser.add_argument(
        "-L",
        "--lazy",
        action="store_true",
        default=False,
        help="Scan only changed workflow files",
    )
    args = parser.parse_args()

    # LOG JAZZ!
    if args.debug:
        to_stdout = logging.StreamHandler(sys.stdout)
        to_stdout.setLevel(VERBOSITY[5])
        to_stdout.setFormatter(STDOUT_FMT)
        LOG.setLevel(VERBOSITY[5])
        LOG.addHandler(to_stdout)
    else:
        LOG.setLevel(VERBOSITY[args.v])
        logging.basicConfig(filename=LOGFILE)
    
    gh = Scanner(args)
    gh.scan()
