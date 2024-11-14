# ASF GitHub Actions Workflow Scanner

## Setting up
`pipenv install`

Create a Read-Only GitHub token

Enter your GitHub token into the gha_scanner.config file.
Optionally, copy the gha_scanner.config file somewhere else
and pass it to `scanner.py` with `-c/--config`.

## Testing
This product uses pytest. Ensure that checks run after modification.
e.g.:
	`pytest tests/checks.py` 

will test the configured checks.

## Starting
`pipenv run python3 ./scanner.py`

## Logging

The policy scanner logs to logs/gha_scanner.log by default.

## Description

When started as a service, the scanner will check GitHub Actions
Workflows for compliance with our policy checks. If a workflow
in the scanned repository is found to be non-compliant, an email
will be sent to the owning PMC and infrastructure.
