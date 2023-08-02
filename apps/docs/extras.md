# Extras

## GitHub Secrets

Secrets are variables that you create in an organization, repository, or repository environment. The secrets that you create are available to use in GitHub Actions workflows. GitHub Actions can only read a secret if you explicitly include the secret in a workflow.
- Navigate to your repo page
- Click on `Settings` tab > `Security` section > `Secrets and variables` drop-down > `Actions`
- OR Navigate to this page: https://github.com/OWNER/REPO/settings/secrets/actions
- Click on `New repository secret` button and create your secret

## Join API

To use Join API in conjugate with **RVX-Builds** project, add secrets `JOIN_API_KEY` & `JOIN_DEVICE_ID` in `GitHub Secrets` after obtaining your join api key and device id of the device that'll be running **RVX-Builds** project from [here](https://joinjoaomgcd.appspot.com/?devices).

## Scheduled Workflows

Some important scheduled workflows are -
- Get Patch Apps Info
- Update Checker

If you've forked the project, make sure that your scheduled workflows are enabled. 
- Click on `Actions` tab
- All the workflows are listed on the left panel
- Click on any scheduled workflow
- If they aren't enabled, a box would be shown with message `"This scheduled workflow is disabled because scheduled workflows are disabled by default in forks"`. Click on `Enable workflow` button to enable the respective workflow.