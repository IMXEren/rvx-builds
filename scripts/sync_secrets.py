"""Sync custom secrets with Github Secrets."""

import json
import os
import sys
from pathlib import Path

from loguru import logger
from ruamel.yaml import YAML


def main() -> None:
    """Sync custom secrets with Github Secrets."""
    secrets_json = os.environ.get("ALL_SECRETS", "{}")

    try:
        secrets_dict = json.loads(secrets_json)
    except json.JSONDecodeError:
        logger.error("Error: ALL_SECRETS environment variable is not valid JSON.")
        sys.exit(1)

    custom_secrets = [k for k in secrets_dict if k.startswith("SECRET_")]
    base_secrets = ["ENVS", "DOCKER_PY_REVANCED_SECRETS"]
    all_expected = set(base_secrets + custom_secrets)

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096 # prevent auto-wrapping long lines

    file_path = ".github/workflows/build-artifact.yml"

    if not Path(file_path).exists():
        logger.error(f"Error: {file_path} does not exist. Are you running this from the repo root?")
        sys.exit(1)

    with Path(file_path).open() as f:
        data = yaml.load(f)

    workflow_call = data.get("on", {}).get("workflow_call", {})
    if "secrets" not in workflow_call or workflow_call["secrets"] is None:
        workflow_call["secrets"] = {}

    current_secrets = workflow_call["secrets"]

    if all_expected == set(current_secrets):
        logger.info("Already up-to-date with custom secrets!")
        return

    # Add any missing expected secrets
    for sec in all_expected:
        if sec not in current_secrets:
            current_secrets[sec] = {"required": False}

    # Remove any SECRET_ variables that no longer exist in GitHub Secrets
    keys_to_remove = [sec for sec in current_secrets if sec.startswith("SECRET_") and sec not in all_expected]

    for k in keys_to_remove:
        del current_secrets[k]

    with Path(file_path).open("w") as f:
        yaml.dump(data, f)

    logger.info(f"Successfully synced {len(all_expected)} secrets to {file_path}")

if __name__ == "__main__":
    main()
