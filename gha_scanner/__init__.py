#!/usr/bin/env python3
import re
import sys
import yaml
import asfpy.messaging
import asfpy.pubsub
import argparse
import requests
import logging
import json
import smtplib
import datetime
from . import checks


class Log:
    def __init__(self, config):
        self.config = config
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

        if self.config["logfile"] == "stdout":
            self.to_stdout = logging.StreamHandler(sys.stdout)
            self.to_stdout.setLevel(self.verbosity[self.config["verbosity"]])
            self.to_stdout.setFormatter(self.stdout_fmt)
            self.log.setLevel(self.verbosity[self.config["verbosity"]])
            self.log.addHandler(self.to_stdout)
        else:
            self.log.setLevel(self.verbosity[self.config["verbosity"]])
            logging.basicConfig(
                format="%(asctime)s [%(levelname)s] %(funcName)s: %(message)s",
                filename=self.config["logfile"],
            )


class Scanner:
    # Handles API requests to GitHub
    def __init__(self, config):
        self.config = config
        self.ghurl = "https://api.github.com"
        self.s = requests.Session()
        self.mail_map = {}
        raw_map = self.s.get(
            "https://whimsy.apache.org/public/committee-info.json"
        ).json()["committees"]
        [self.mail_map.update({item: raw_map[item]["mail_list"]}) for item in raw_map]
        self.s.headers.update({"Authorization": "token %s" % self.config["gha_token"]})
        self.pubsub = "https://pubsub.apache.org:2070/git/commit"
        self.logger = Log(config)
        self.message_foot = [
            "\nFor more information on the GitHub Actions workflow policy, visit:",
            "\thttps://infra.apache.org/github-actions-policy.html\n",
            "Please remediate the above as soon as possible.",
            "If after after 60 days these problems are not addressed, we will turn off builds",
            "\nCheers,",
            "\tASF Infrastructure",
        ]
        d = datetime.datetime.now() + datetime.timedelta(
            days=self.config["next_pester"]
        )
        self.msgcache = {"infrastructure": {"date": d}}

    def scan(self):
        self.logger.log.info("Connecting to %s" % self.pubsub)
        asfpy.pubsub.listen_forever(self.handler, self.pubsub, raw=True)

    # Fetch all workflows for the project the given hash
    def list_flows(self, commit):
        try:
            r = self.s.get(
                "%s/repos/apache/%s/actions/workflows?ref=%s"
                % (self.ghurl, commit["project"], commit["sha"])
            )
            return r.json()
        except requests.exceptions.RequestException as e:
            self.logger.log.error(f"An error occurred: {e}")
        return {}

    # Fetch the yaml workflow from github
    def fetch_flow(self, commit, w_data):
        try:
            rawUrl = "https://raw.githubusercontent.com/apache"
            self.logger.log.debug(
                "Fetching %s/%s/%s/%s"
                % (rawUrl, commit["project"], commit["sha"], w_data["path"])
            )
            r = self.s.get(
                "%s/%s/%s/%s"
                % (rawUrl, commit["project"], commit["sha"], w_data["path"])
            )
            r_content = yaml.safe_load(
                "\n".join(
                    [
                        line
                        for line in r.content.decode("utf-8").split("\n")
                        if not re.match(r"^\s*#", line)
                    ]
                )
            )

        except (KeyError, TypeError, yaml.parser.ParserError) as e:
            self.logger.log.critical(e)
            return None

        self.logger.log.debug(r_content.keys())
        if 404 in r_content.keys():
            self.logger.log.error(
                "%s doesn't exist in %s" % (w_data["path"], commit["hash"])
            )
            return None

        self.logger.log.debug("retrieved: %s" % w_data["path"])
        return r_content

    def scan_flow(self, commit, w_data):
        flow_data = self.fetch_flow(commit, w_data)
        result = {}
        m = []

        if flow_data:
            for check in checks.WORKFLOW_CHECKS:
                self.logger.log.info(
                    "Checking %s:%s(%s): %s"
                    % (commit["project"], w_data["name"], commit["hash"], check)
                )
                c_data = checks.WORKFLOW_CHECKS[check]["func"](flow_data)
                # All workflow checks return a bool, False if the workflow failed.
                if not c_data:
                    m.append(
                        "\t"
                        + w_data["name"]
                        + ": "
                        + checks.WORKFLOW_CHECKS[check]["desc"]
                    )
                result[check] = c_data
            return (result, m)
        else:
            return (None, None)

    def send_report(self, message, proj_name):
        # Message should be a dict containing recips, subject, and body. body is expected to be a list of strings
        # TODO: Get a message cache working so we don't annoy people
        if proj_name in self.msgcache.keys():
            # Fetch the next pester date
            def_now = datetime.datetime.now()
            np = getattr(self.msgcache[proj_name], "date", def_now)
            self.logger.log.debug(f"{np}")
            if np <= def_now:
                self.logger.log.info(
                    f"Waiting until {self.msgcache[proj_name]['date']}"
                )
                return
        # Set new next pester date
        next_pester = datetime.datetime.now() + datetime.timedelta(
            days=self.config["next_pester"]
        )
        self.msgcache[proj_name] = {"date": next_pester}
        self.logger.log.info(f"{self.msgcache}")

        try:
            self.logger.log.info(f"Sending Message to {message['recips'][-1]}")
            asfpy.messaging.mail(
                recipients=message["recips"],
                subject=message["subject"],
                message="\n".join(message["body"]),
            )
        except smtplib.SMTPRecipientsRefused as e:
            self.logger.log.error(f"An error has occurred: {e}")

    def handler(self, data):
        if "commit" in data:
            reponame = data["commit"]["project"].split("-")
            self.logger.log.debug(reponame)
            proj_name = None
            proj_mail = None

            if reponame[0] == "incubator":
                try:
                    proj_mail = f"private@{reponame[1]}.apache.org"
                    proj_name = reponame[1]
                except IndexError:
                    proj_mail = "private@incubator.apache.org"
                    proj_name = "Incubator"
            else:
                try:
                    proj_mail = f"private@{self.mail_map[reponame[0]]}.apache.org"
                    proj_name = self.mail_map[reponame[0]]
                except KeyError:
                    proj_mail = "root@apache.org"
                    proj_name = "Foundation"

            self.logger.log.debug(f"Divined project email: {proj_mail}")
            message = {
                "body": [
                    f"Greetings {proj_name.capitalize()} PMC!\n",
                    f"The repository: {data['commit']['project']} has been scanned.",
                    "Our analysis has found that the following GitHub Actions workflows need remediation:",
                ],
                #    "recips": ["notifications@infra.apache.org", proj_mail],
                "recips": ["notifications@infra.apache.org"],
                "subject": f"GitHub Actions workflow policy violations in {data['commit']['project']}",
            }
            p = re.compile(r"^\.github\/workflows\/.+\.ya?ml$")
            results = {}
            if not self.config["full_scan"]:
                r = [w for w in data["commit"].get("files", []) if p.match(w)]
                self.logger.log.debug("found %s modified workflow files" % len(r))
                self.logger.log.debug(f"{data['commit'].get('files', [])}")
            else:
                r = [True]
                self.logger.log.debug("Full scan enabled: scanning all workflow files")

            self.logger.log.debug(f"{data['commit'].get('files', [])}")
            if len(r) > 0:
                w_list = self.list_flows(data["commit"])
                self.logger.log.debug(f"{w_list}")
                if "workflows" in w_list.keys() and w_list["workflows"] is not None:
                    self.logger.log.debug(
                        [item["path"] for item in w_list["workflows"]]
                    )
                    for workflow in w_list["workflows"]:
                        # Handle the odd ''
                        if not workflow["path"]:
                            self.logger.log.debug(workflow)
                            continue

                        self.logger.log.debug("Handling: %s" % workflow["path"])
                        results[workflow["name"]], m = self.scan_flow(
                            data["commit"], workflow
                        )

                        if m:
                            message["body"].extend(m)
                        else:
                            self.logger.log.debug(
                                f"{workflow['path']} Passed all tests."
                            )
                else:
                    self.logger.log.info(
                        f"No workflows found in  {data['commit']['project']}: {data['commit']}"
                    )
            else:
                self.logger.log.info(
                    f"Scanned {data['commit']['project']} commit: {data['commit']['hash']}"
                )

            if len(message["body"]) >= 4:
                self.logger.log.info(
                    f"Failures detected, generating message to {proj_name}..."
                )
                message["body"].extend(self.message_foot)
                self.logger.log.debug(message["subject"])
                self.send_report(message, proj_name)
            else:
                self.logger.log.debug(results)
        else:
            self.logger.log.debug("Heartbeat Signal Detected")
