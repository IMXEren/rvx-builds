<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/IMXEren/rvx-builds/main/profile/logo_big_dark-bg.svg">
  <img alt="rvx-builds_logo" src="https://raw.githubusercontent.com/IMXEren/rvx-builds/main/profile/logo_big_light-bg.svg">
</picture>

# Table of Contents

1. [**Overview**](#1-overview)
2. [**Requirements**](#2-requirements)
3. [**Usage**](#3-usage)
4. [**Updates & Changelogs**](#4-updates--changelogs)
5. [**Credits**](#5-credits)
6. [**Support**](#6-support)

## 1. Overview

**Are you tired of patching ReVanced apps on your mobile devices? Which version to patch and which apk to provide for patching? Is the waiting period long enough and still the patch doesn't work as it should? Device compatibility issues? Auto-updates?...** All that can be done with the help of this [github repository](https://github.com/IMXEren/rvx-builds) (for patching & building) and this [**RVX-Builds**](https://taskernet.com/shares/?user=AS35m8k0QSchKA1x02SixFIhiL41a828J1qapOYfcEuyL2zSn%2FfJTN5WVSi01o18x6EAFb4%3D&id=Project%3ARVX-Builds) project in Tasker (for interactive selection & automation).

***Note: Neither the mentioned github repo nor the Tasker project are in anyway officially related to ReVanced Team. All this work comes under 3rd party so please don't ask for support from ReVanced Team regarding it.***

## 2. Requirements

- [GitHub Account](https://github.com/join) (Free)
- [Tasker](https://play.google.com/store/apps/details?id=net.dinglisch.android.taskerm) (Trial -> Paid)
- [Join](https://play.google.com/store/apps/details?id=com.joaomgcd.join) (Trial -> Paid; Optional)

## 3. Usage

There are actually two ways to patch apps - **Manual** & **Automated**. The Manual way simply requires the GitHub Repository only and you've to do all the work yourself like customizing the patches, downloading & installing. The Automated way requires the GitHub Repository as well as the RVX-Builds project in Tasker. In the automated way, you can easily customize and configure many more properties using Tasker.

If you're doing it for the first time, I'd suggest you to go with Manual method to make yourself comfortable with the different patching terms in the repository and configure some necessary setups before automating.

### 1. Manual

Here's the manual way to patch apps.

1. Create a [GitHub account](https://github.com/join) if you haven't.
2. Fork this [repository](https://github.com/IMXEren/rvx-builds) under anyname.
3. Read this [page](/apps/docs/customize-patches.md) onwards. This is to customize the patching. After reading, you might have prepared an `.env` file.
4. Congrats, you're ready to patch these apps.
5. Go to `Actions` tab. Select `Build & Release`. Click on `Run Workflow` button.
6. Wait for sometime while it patches and build all those apps mentioned in the `.env` file.
7. Once complete and successful, you'll get your patched apks in the `Releases` section.
8. Download & install those apks. Now, you've installed the patched apps!!
9. Here are some [extra things](/apps/docs/extras.md) to configure.

### 2. Automated

It'll be better for yourself if you have some [basic knowledge about Tasker](https://www.youtube.com/watch?v=EVNUGUv-lIY) like knowing about tasks, profiles, events, states, projects.

1. Go to this [page](https://github.com/settings/tokens) and `Generate new token > Classic`. Enter `RVX-Builds` in Note, set any expiration period and select these scopes (sufficient) - `repo, workflow, write:packages`. Click `Generate Token`. Note the token - `ghp_*`
2. Import [**RVX-Builds**](https://taskernet.com/shares/?user=AS35m8k0QSchKA1x02SixFIhiL41a828J1qapOYfcEuyL2zSn%2FfJTN5WVSi01o18x6EAFb4%3D&id=Project%3ARVX-Builds) project on Tasker and setup the GitHub credentials. It'll popup itself for you to setup or you can run `RVX-Builds - Setup` Task in `Tasks` Tab inside `RVX-Builds` Project. Projects are listed horizontally on bottom bar.
3. Once completed, you're ready to customize patches. Run `RVX-Builds - Manager` to do so. It'll consist of menu items -
    - Apps: To modify app related properties.
    - Downloads: To modify download & installation of app properties.
    - Merge: To merge your customization (locally on Tasker) with the `.env` file in your GitHub Repo. Only shown if you've made customization changes in Apps.
    - Releases: To build your patched apps and release them. Set the above options accordingly and make a stable release.
4. If you have access to Join paid version, enable `RVX-Builds - New Release [Join]` Profile in `Profiles` Tab. Also enable `RVX-Builds - Check For Updates` if you want it to handle cancelled or errored out downloads due to any reason. Also, you need to add **JOIN API** [secrets](/apps/docs/extras.md#github-secrets). Here's [how to](/apps/docs/extras.md#join-api) do it.
5. If you don't have access to Join paid version, enable `RVX-Builds - Check For Updates` Profile in `Profiles` Tab. Disable `RVX-Builds - New Release [Join]` in this case.
6. After the successful release, the workflow would make an API call to Join (`RVX-Builds - New Release [Join]`) which would ultimately initialize an event and the downloader & installer task would run and work based upon your configuration of `Downloads` menu option in `RVX-Builds - Manager` task. Another workaround is that this profile `RVX-Builds - Check For Updates` would periodically (15 min; you can change) perform checks. It can also handle cancelled or errored out downloads.
7. Finally, after all the downloading or installation, there'll be a notification to let you know that it was successful. Note that, it requires ADB Wifi access to Tasker to let it install apps in the background.
8. Patched apps have been installed and apks are at `/storage/emulated/0/Tasker/rvx-builds/downloads/REPO_RELEASE_TAG_NAME/*.apk`. Note that you shouldn't delete any of those apks otherwise you'd face infinite-looping of downloads because of `6th - RVX-Builds - Check For Updates`. You may disable actions from `A17-28` in the linked task as a solution to it.

### Patching

The patching is done using the CLI for both revanced & revanced-extended resources. The `/apks` folder is used as the base folder in which you can source your `options.json` or whatever files you need. Here are *incompletely* generated revanced [`options.json`](../../tree/changelogs/apps/revanced/options.json) and revanced-extended [`options.json`](../../tree/changelogs/apps/revanced-extended/options.json). Here's the list of [patch apps](../../tree/changelogs/apps/docs/README.md) which you can look into.

**Note: A possible error while installing the released patched apks can be due to signature mismatch of the apk and it's installed app. In this case, either provide the same the keystore file to sign apks in `/apks` folder in GitHub repo and add `KEYSTORE_FILE_NAME=*.keystore` in `.env` file OR simply delete (make backup if possible; one-time process) those already installed non-patched (same package) or patched apps.**

## 4. Updates & Changelogs

The `RVX-Builds - Project Updates` profile will let you know of any updates I push so, make sure it's enabled.

>> Taskernet - [**RVX-Builds**](https://taskernet.com/shares/?user=AS35m8k0QSchKA1x02SixFIhiL41a828J1qapOYfcEuyL2zSn%2FfJTN5WVSi01o18x6EAFb4%3D&id=Project%3ARVX-Builds)  
[**Changelogs**](/apps/updates/CHANGELOG.md)

## 5. Credits

- Thanks to [@ReVanced](https://github.com/revanced) for **ReVanced**.
- Thanks to [@inotia00](https://github.com/inotia00) for **ReVanced Extended**.
- Thanks to [@nikhilbadyal](https://github.com/nikhilbadyal/docker-py-revanced) for his amazing work.
- Thanks to [@Spacellary](https://github.com/Spacellary/ReVanced-Extended-Automated-Builds) for his work in making the customized parent fork.

## 6. Support

I'll try my best to help you regarding this project. Make sure you've read everything here, repository synced & tasker project up-to-date and outcome is same from multiple reproductions. Still if any issues persist, you're free to open discussions, issues & PRs. Kindly have some patience after creating them.
