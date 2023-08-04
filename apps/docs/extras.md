# Extras

## GitHub Secrets

Secrets are variables that you create in an organization, repository, or repository environment. The secrets that you create are available to use in GitHub Actions workflows. GitHub Actions can only read a secret if you explicitly include the secret in a workflow.
- Navigate to your repo page
- Click on `Settings` tab > `Security` section > `Secrets and variables` drop-down > `Actions`
- OR Navigate to this page: https://github.com/OWNER/REPO/settings/secrets/actions
- Click on `New repository secret` button and create your secret

## Join API

To use Join API in conjugate with **RVX-Builds** project, add secrets `JOIN_API_KEY` & `JOIN_DEVICE_ID` in `GitHub Secrets` after obtaining your join api key and device id of the device that'll be running **RVX-Builds** project from [here](https://joinjoaomgcd.appspot.com/?devices).

## Workflow Permissions

Make your Action has write access. If not click here: https://github.com/OWNER/REPO/settings/actions. In the bottom give read and write access to Actions.
    
<img src="https://i.imgur.com/STSv2D3.png" width="400">

## Scheduled Workflows

Some important scheduled workflows are -
- Get Patch Apps Info
- Update Checker

If you've forked the project, make sure that your scheduled workflows are enabled. 
- Click on `Actions` tab
- All the workflows are listed on the left panel
- Click on any scheduled workflow
- If they aren't enabled, a box would be shown with message `"This scheduled workflow is disabled because scheduled workflows are disabled by default in forks"`. Click on `Enable workflow` button to enable the respective workflow.

**Get Patch Apps Info** is required when you want to automate the building. Therefore, sometimes you'd encounter that your configured `.env` or patch properties wouldn't show as updated in Tasker for a time period (2-5 mins).

**Update Checker** workflow will periodically check for new patch releases and trigger a new Build & Release when necessary. This requires you to set your `PERSONAL_ACCESS_TOKEN` secret to trigger builds.

## Google Play Protect

Google Play Protect may cause hindrance while installation of patched apks. If it does or you want to suppress it, you need to disable it on your mobile device. Here's how to do -

- Open the Google Play Store app.
- At the top right, tap the profile icon.
- Tap _Play Protect_ and then _Settings_.
- Turn _Scan apps with Play Protect_ off.

### Send unknown apps to Google

If you install apps from unknown sources outside of the Google Play Store, Google Play Protect may ask you to send unknown apps to Google. When you turn on the “Improve harmful app detection” setting, you allow Google Play Protect to automatically send unknown apps to Google. I'd suggest you to disable this too, if the issues while installation persist.

- Open the Google Play Store app.
- At the top right, tap the profile icon.
- Tap _Play Protect_ and then _Settings_.
- Turn _Improve harmful app detection_ off.
