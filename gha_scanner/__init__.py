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
from . import checks

class Scanner:
    # Handles API requests to GitHub
    def __init__(self, config):
        self.config = config
        self.ghurl = "https://api.github.com"
        self.s = requests.Session()
        self.s.headers.update({"Authorization": "token %s" % self.config['gha_token']})
        self.pubsub = "https://pubsub.apache.org:2070/git/commits"
        self.log = logging.getLogger(__name__)
        self.verbosity = {
        0: logging.INFO,
        1: logging.CRITICAL,
        2: logging.ERROR,
        3: logging.WARNING,
        4: logging.INFO,
        5: logging.DEBUG,
        }

        self.stdout_fmt = logging.Formatter(
        "{asctime} [{levelname}] {funcName}: {message}", style="{"
        )

        if self.config['logfile'] == "stdout":
            self.to_stdout = logging.StreamHandler(sys.stdout)
            self.to_stdout.setLevel(self.verbosity[self.config['verbosity']])
            self.to_stdout.setFormatter(self.stdout_fmt)
            self.log.setLevel(self.verbosity[self.config['verbosity']])
            self.log.addHandler(self.to_stdout)
        else:
            self.log.setLevel(self.verbosity[self.config['verbosity']])
            logging.basicConfig(format="%(asctime)s [%(levelname)s] %(funcName)s: %(message)s", filename=self.config['logfile'])

    def scan(self):
        self.log.info("Connecting to %s" % self.pubsub)
        asfpy.pubsub.listen_forever(self.handler, self.pubsub, raw=True)

    # Fetch all workflows for the project the given hash
    def list_flows(self, commit):
        r = self.s.get(
            "%s/repos/apache/%s/actions/workflows?ref=%s"
            % (self.ghurl, commit["project"], commit["hash"])
        )
        return r.json()

    # Fetch the yaml workflow from github
    def fetch_flow(self, commit, w_data):
        try:
            rawUrl = "https://raw.githubusercontent.com/apache"
            self.log.debug("Fetching %s/%s/%s/%s"%(rawUrl, commit['project'], commit['hash'], w_data['path']))
            r = self.s.get(
                "%s/%s/%s/%s"
                % (rawUrl, commit['project'], commit['hash'], w_data['path'])
            )
            self.log(r.content)

            r_content = yaml.safe_load(
                "\n".join(
                    [
                        line
                        for line in base64.b64decode(r.content)
                        .decode("utf-8")
                        .split("\n")
                        if not re.match(r"^\s*#", line)
                    ]
                )
            )

        except KeyError as e:
            self.log.debug("%s"%e)
            return None

        except TypeError as e:
            self.log.debug("%s"%e)
            return None

        self.log.debug(r_content)
        return r_content
            
    def scan_flow(self, commit, w_data):
        flow_data = self.fetch_flow(commit, w_data)
         
        self.log.debug(flow_data)
        
        result = {}
        m = []
        if flow_data:
            for check in checks.WORKFLOW_CHECKS:
                self.log.info(
                    "Checking %s:%s(%s): %s"
                    % (commit["project"], w_data["name"], commit["hash"], check)
                )
                c_data = checks.WORKFLOW_CHECKS[check]["func"](flow_data)
                # All workflow checks return a bool, False if the workflow failed.
                if not c_data:
                    m.append("\t" + w_data["name"] + ": " + checks.WORKFLOW_CHECKS[check]["desc"])
                result[check] = c_data
            return (result, m)
        else:
            return (None, None)

    def send_report(self, message):
        # Message should be a dict containing recips, subject, and body. body is expected to be a list of strings
        if SEND_MESSAGES:
            asfpy.messaging.mail(
                recipients=message["recips"],
                subject=message["subject"],
                message="\n".join(message["body"]),
            )
        else:
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
            p = re.compile(r"^\.github\/workflows\/.+\.yml$")
            results = {}
            r = [w for w in data["commit"].get("files", []) if p.match(w)]
            self.log.debug("found %s workflow files" % len(r))
            if len(r) > 0:
                w_list = self.list_flows(data["commit"])
                self.log.debug([ item['path'] for item in w_list['workflows']])
                for workflow in w_list["workflows"]:
                    # Handle the odd ''
                    if not workflow['path']:
                        self.log.debug(workflow)
                        continue
                    
                    self.log.debug("Handling: %s"%workflow['path'])

                    results[workflow["name"]], m = self.scan_flow(
                        data["commit"], workflow
                    )

                    if m:
                        message["body"].extend(m)
                    else:
                        self.log.debug(results)
            else:
                self.log.info("Scanned commit: %s" % data["commit"]["hash"])


            if len(message['body']) >= 3:
                self.log.info("Failures detected, sending message")
                message["body"].extend(
                    [
                        "Please remediate the above as soon as possible.",
                        "If the above is not remediated after 30 days, we will turn off builds",
                        "\nCheers,",
                        "\tASF Infrastructure",
                    ]
                )
                self.log.debug(message)
                self.send_report(message)
        else:
            self.log.info("Heartbeat Signal Detected")

