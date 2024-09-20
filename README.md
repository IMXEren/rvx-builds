<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/IMXEren/rvx-builds/main/auto/profile/logo_big_dark-bg.svg">
  <img alt="rvx-builds_logo" src="https://raw.githubusercontent.com/IMXEren/rvx-builds/main/auto/profile/logo_big_light-bg.svg">
</picture>

# ⭐ NEW!! Custom Patch Resources

The Tool now supports resource config at app level. You can patch A app with X resources while patching B with Y resources. This can be done by providing supported download links for resources for the app. Another new major addition is to be able patch any supported app in the `patches.json`, irrespective of the official apps present in the repository configs. [**Read more...**](/auto/docs/customize-patches.md)

# Table of Contents

- [**Overview**](#overview)
- [**Requirements**](#requirements)
- [**Usage**](#usage)
- [**Updates & Changelogs**](#updates--changelogs)
- [**Credits**](#credits)
- [**Support**](#support)

## Overview

**Are you tired of patching ReVanced apps on your mobile devices? Which version to patch and which apk to provide for patching? Is the waiting period long enough and still the patch doesn't work as it should? Device compatibility issues? Auto-updates?...** All that can be accomplished with the help of this [**github repository**](https://github.com/IMXEren/rvx-builds) (for patching & building) and this [**RVX-Builds**](https://taskernet.com/shares/?user=AS35m8k0QSchKA1x02SixFIhiL41a828J1qapOYfcEuyL2zSn%2FfJTN5WVSi01o18x6EAFb4%3D&id=Project%3ARVX-Builds) project in Tasker (for interactive selection & automation).

**_Note: Neither the mentioned github repository nor the Tasker project are in anyway officially related to ReVanced Team. All this work falls under 3rd party so please don't ask for support from ReVanced Team regarding it._**

## Requirements

- [**GitHub Account**](https://github.com/join) (Free)
- **Tasker** ([Trial](https://tasker.joaoapps.com/download.html) -> [Paid](https://play.google.com/store/apps/details?id=net.dinglisch.android.taskerm))
- **Join** ([Trial -> Paid](https://play.google.com/store/apps/details?id=com.joaomgcd.join); Optional)

## Usage

### Pre-Forked

I think that there might be possibility that some people would've already forked the parent repository of @nikhilbadyal or it's child repository (for example, of @Spacellary). So, here are [listed files](/auto/docs/pre-forked.md) (may or may not replace originals) which you can copy to repository clone folder and push those changes. It'll make your repository eligible to be used in **Automation** and somewhat similar to mine. Proceed with patch methods.

### Methods

There are actually two ways to patch apps - **Manual** & **Automated**. The Manual way simply requires the GitHub Repository only and you've to do all the work yourself like customizing the patches, downloading & installing built apks. The Automated way requires the GitHub Repository as well as the RVX-Builds project in Tasker. In the automated way, you can easily customize and configure many more properties using Tasker.

If you're doing it for the first time, I'd suggest you to go with Manual method to make yourself accustomed with the different patching terms in the repository and configure some necessary setups before automating.

### 1. Manual

Here's the manual way to patch apps.

1. Create a [GitHub account](https://github.com/join) if you haven't.
2. Fork this [repository](https://github.com/IMXEren/rvx-builds) under any name.
3. Read this [page](/auto/docs/customize-patches.md) onwards. This is to customize the patching. After going through, you must have prepared an `.env` file.
4. Congrats, you're ready to patch these apps.
5. Go to `Actions` tab. Select `Build & Release`. Click on `Run Workflow` button.
6. Wait for sometime while it patches and build all those apps mentioned in the `.env` file.
7. Once complete and successful, you'll get your patched apks in the `Releases` section.
8. Download & install those apks. Now, you've installed the patched apps!!
9. Here are some [extra things](/auto/docs/extras.md) to configure.

### 2. Automated

It'll be better for yourself if you have some [basic knowledge about Tasker](https://www.youtube.com/watch?v=EVNUGUv-lIY) like knowing about tasks, profiles, events, states, projects.

1. Go to this [page](https://github.com/settings/tokens) and `Generate new token > Classic`. Enter `RVX-Builds` in Note, set any expiration period and select these scopes (sufficient) - `repo, workflow, write:packages`. Click `Generate Token`. Note the token - `ghp_*`
2. Import [**RVX-Builds**](https://taskernet.com/shares/?user=AS35m8k0QSchKA1x02SixFIhiL41a828J1qapOYfcEuyL2zSn%2FfJTN5WVSi01o18x6EAFb4%3D&id=Project%3ARVX-Builds) project on Tasker and setup the GitHub credentials. It'll popup itself for you to setup or you can run `RVX-Builds - Setup` Task in `Tasks` Tab inside `RVX-Builds` Project. Projects are listed horizontally on bottom bar.
3. Once completed, you're ready to customize patches. Run `RVX-Builds - Manager` task to do so. It'll consist of menu items -
   - Apps: To modify app related properties. (**Must configure**)
   - Downloads: To modify download & installation of app properties. (**Must configure**)
   - Merge: To merge your customization (locally on Tasker) with the `.env` file in your GitHub Repo. Only shown if you've made customization changes in _Apps_ or clicked it (i.e. always open **Apps** even when you don't need to change).
   - Releases: To build your patched apps and release them. Set the above options accordingly and make a stable or a pre-release.
4. If you have access to Join paid version, enable `RVX-Builds - New Release [Join]` Profile in `Profiles` Tab. Also enable `RVX-Builds - Check For Updates` if you want it to handle cancelled or errored out downloads due to any reason. Also, you need to add **JOIN API** [secrets](/auto/docs/extras.md#github-secrets). Here's [how to](/auto/docs/extras.md#join-api) do it.
5. If you don't have access to Join paid version, enable `RVX-Builds - Check For Updates` Profile in `Profiles` Tab. Disable `RVX-Builds - New Release [Join]` in this case.
6. After the successful release, the workflow would make an API call to Join (`RVX-Builds - New Release [Join]`) which would ultimately initialize an event and the downloader & installer task would run and work based upon your configuration of `Downloads` menu option in `RVX-Builds - Manager` task. Another workaround is that this profile `RVX-Builds - Check For Updates` would periodically (20 min; you can change) perform checks. It can also handle cancelled or errored out downloads.
7. Finally, after all the downloading or installation, there'll be a notification to let you know that it was successful. Note that, it requires ADB Wifi access to Tasker to let it install apps in the background.
8. Patched apps have been installed and apks are at `/storage/emulated/0/Tasker/rvx-builds/downloads/REPO_RELEASE_TAG_NAME/*.apk`. Note that you shouldn't delete any of those apks otherwise you'd face infinite-looping of downloads because of `6th - RVX-Builds - Check For Updates`. You may disable action `A11 - Handle Cancelled Downloads` in the linked task as a solution to it or select not to handle it in `Downloads` menu options.

**Note:**

1.  Initialization of the tasks may take sometime at some-points due to heavy scripting process. Kindly don't worry about all that. Also, make sure that you've a decent internet connection speed.
2.  [Read here](/auto/docs/tasker-automation.md) for more details on the automation functionalities.

### Patching

The patching is done using the CLI for all the builds. The `/apks` folder is used as the base folder in which you can source your `options.json` or whatever necessary files you need. Here's the list of [patch apps](../../tree/changelogs/auto/apps/README.md) and _incompletely_ generated [`options.json`](../../tree/changelogs/auto/apps/options) which you can look into.

**Note: A possible error while installing the released patched apks can be due to signature mismatch of the apk and it's installed app. In this case, either provide the same the keystore file to sign apks in `/apks` folder in GitHub repository and add `GLOBAL_KEYSTORE_FILE_NAME=*.keystore` in `.env` file OR simply delete (make backup if possible; one-time process) those already installed non-patched (same package) or patched apps.**

## Updates & Changelogs

The `RVX-Builds - Project Updates` profile will let you know of any updates I push so, make sure it's enabled.

> > Taskernet - [**RVX-Builds**](https://taskernet.com/shares/?user=AS35m8k0QSchKA1x02SixFIhiL41a828J1qapOYfcEuyL2zSn%2FfJTN5WVSi01o18x6EAFb4%3D&id=Project%3ARVX-Builds)<br>
> > [**Changelogs**](/auto/updates/CHANGELOG.md)

## Credits

- Thanks to [@ReVanced](https://github.com/revanced) for **ReVanced**.
- Thanks to [@inotia00](https://github.com/inotia00) for **ReVanced Extended**.
- Thanks to [@nikhilbadyal](https://github.com/nikhilbadyal/docker-py-revanced) for his amazing work.
- Thanks to [@Spacellary](https://github.com/Spacellary/ReVanced-Extended-Automated-Builds) for his work in making the customized parent fork.

## Support

I'll try my best to help you regarding this project. Make sure you've read everything here, repository synced & tasker project up-to-date and outcome is same from multiple reproductions. Still if any issues persist, you're free to open discussions, issues & PRs. Kindly have some patience after creating them.
