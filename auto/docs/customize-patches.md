# Customizing Patches

Here's the [sample env](#sample-env) to help you. Reminder to check if you have [workflow permissions](#workflow-permission).

**Note - If you want to use or will be using `Automated` method to patch, please do not define anything inside `ENVS`. You are free to use `.env` file to do so.**

## Default

If you don't define anything in `.env` file or `ENVS` in `GitHub Secrets`, these configurations will be used:

- YouTube & YouTube Music apps will be patched
- With latest versions recommended by ReVanced
- Using latest resources provided by ReVanced
- With all patches included except for universal patches

**Note that _MicroG_ won't be released by default and you've to use `EXTRA_FILES` config for that to happen.**

## Configurations

### Global Config

| **Env Name**                                              |                  **Description**                  | **Default**                                                                                              |
| :-------------------------------------------------------- | :-----------------------------------------------: | :------------------------------------------------------------------------------------------------------- |
| [PATCH_APPS](#patch-apps)                                 |                Apps to patch/build                | youtube                                                                                                  |
| [EXISTING_DOWNLOADED_APKS ](#existing-downloaded-apks)    |           Already downloaded clean apks           | []                                                                                                       |
| [PERSONAL_ACCESS_TOKEN](#personal-access-token)           |             GitHub/GitLab Token to be used        | None                                                                                                     |
| DRY_RUN                                                   |                   Do a dry run                    | False                                                                                                    |
| [EXTRA_FILES](#extra-files)                               |    Extra files apk to upload in GitHub upload.    | None                                                                                                     |
| [GLOBAL_CLI_DL\*](#global-resources)                      |     DL for CLI to be used for patching apps.      | [Revanced CLI](https://github.com/revanced/revanced-cli)                                                                        |
| [GLOBAL_PATCHES_DL\*](#global-resources)                  |   DL for Patches to be used for patching apps.    | [ReVanced API patches bundle](https://api.revanced.app/v5/patches.rvp)                                                         |
| [GLOBAL_NORMALIZE_PATCH_NAMES\*](#global-resources)       |   Normalize patch names to lowercase dash-form   | True                                                                                                     |
| [GLOBAL_KEYSTORE_FILE_NAME\*](#global-keystore-file-name) |       Key file to be used for signing apps        | [Builder's own key](https://github.com/IMXEren/rvx-builds/blob/main/apks/revanced.keystore)                                          |
| [GLOBAL_OLD_KEY\*](#global-keystore-file-name)            | Whether key was generated with cli v4(new) or not | False [[Builder's own key (v3)](https://github.com/IMXEren/rvx-builds/blob/main/apks/revanced.keystore)]                           |
| [GLOBAL_OPTIONS_FILE\*](#global-options-file)             |              Options file to be used              | [Builder's options.yml](https://github.com/IMXEren/rvx-builds/blob/main/apks/options.yml)                                       |
| [GLOBAL_ARCHS_TO_BUILD\*](#global-archs-to-build)         |         Arch to keep in the patched apk.          | All                                                                                                      |
| [GLOBAL_CLI_ARGSF\*](#cli-arg-compatibility)              |               CLI argument profile                 | revanced-cli                                                                                             |
| [GLOBAL_CLI_LPARGS\*](#cli-arg-compatibility)             |   Override map for `list-patches` command args    | None                                                                                                     |
| [GLOBAL_CLI_PARGS\*](#cli-arg-compatibility)              |       Override map for `patch` command args       | None                                                                                                     |
| [REDDIT_CLIENT_ID](#reddit-client)                        |       Reddit Client ID to patch reddit apps       | None                                                                                                     |
| [VT_API_KEY](#virus-total)                                |           Virus Total Key to scan APKs            | None                                                                                                     |
| [TELEGRAM_CHAT_ID](#telegram-support)                     |            Receiver in Telegram upload            | None                                                                                                     |
| [TELEGRAM_BOT_TOKEN](#telegram-support)                   |          APKs Sender for Telegram upload          | None                                                                                                     |
| [TELEGRAM_API_ID](#telegram-support)                      |         Used for telegram Authentication          | None                                                                                                     |
| [TELEGRAM_API_HASH](#telegram-support)                    |         Used for telegram Authentication          | None                                                                                                     |
| [APPRISE_URL](#apprise)                                   |                   Apprise URL .                   | None                                                                                                     |
| [APPRISE_NOTIFICATION_TITLE](#apprise)                    |           Apprise Notification Title .            | None                                                                                                     |
| [APPRISE_NOTIFICATION_BODY](#apprise)                     |            Apprise Notification Body .            | None                                                                                                     |
| CLI_TEMP_FOLDER_NAME                                      |   Parent folder for per-app CLI temporary files   | patch-source-temporary-files                                                                             |
| MAX_RESOURCE_WORKERS                                      |     Maximum workers for downloading resources     | 3                                                                                                        |
| MAX_PARALLEL_APPS                                         |   Maximum number of apps to process in parallel   | 4                                                                                                        |
| DISABLE_CACHING                                           |       Disable download and resource caching       | False                                                                                                    |
| OBTAINIUM_EXPORT                                          |   Export html of apk sources pointing to GitHub   | False                                                                                                    |
| OBTAINIUM_GITHUB_TAG                                      |   The release tag to be pointed to on export      | latest                                                                                                   |

`*` - Can be overridden for individual app.

### App Level Config

| Env Name                                                        |                        Description                        | Default                        |
| :-------------------------------------------------------------- | :-------------------------------------------------------: | :----------------------------- |
| [_APP_NAME_\_CLI_DL](#global-resources)                         |     DL for CLI to be used for patching **APP_NAME**.      | GLOBAL_CLI_DL                  |
| [_APP_NAME_\_PATCHES_DL](#global-resources)                     |   DL for Patches to be used for patching **APP_NAME**.    | GLOBAL_PATCHES_DL              |
| [_APP_NAME_\_KEYSTORE_FILE_NAME](#global-keystore-file-name)    |       Key file to be used for signing **APP_NAME**.       | GLOBAL_KEYSTORE_FILE_NAME      |
| [_APP_NAME_\_OLD_KEY](#global-keystore-file-name)               | Whether key used was generated with cli v4 (new) or not.  | GLOBAL_OLD_KEY                 |
| [_APP_NAME_\_OPTIONS_FILE](#global-options-file)                |           Options file to be used **APP_NAME**.           | GLOBAL_OPTIONS_FILE            |
| [_APP_NAME_\_OPTIONS_RAW](#global-options-file)                 |     Raw Options (overrides) to be used **APP_NAME**.      | ""                             |
| [_APP_NAME_\_ARCHS_TO_BUILD](#global-archs-to-build)            |         Arch to keep in the patched **APP_NAME**.         | GLOBAL_ARCHS_TO_BUILD          |
| [**APP_NAME**\_CLI_ARGSF](#cli-arg-compatibility)               |          CLI argument profile for **APP_NAME**.           | GLOBAL_CLI_ARGSF               |
| [**APP_NAME**\_CLI_LPARGS](#cli-arg-compatibility)              |     Override map for **APP_NAME** list-patches args.      | GLOBAL_CLI_LPARGS              |
| [**APP_NAME**\_CLI_PARGS](#cli-arg-compatibility)               |         Override map for **APP_NAME** patch args.         | GLOBAL_CLI_PARGS               |
| [_APP_NAME_\_NORMALIZE_PATCH_NAMES](#custom-exclude-patching)   |   Normalize patch names for **APP_NAME**.                 | GLOBAL_NORMALIZE_PATCH_NAMES    |
| [_APP_NAME_\_EXCLUDE_PATCH\*](#custom-exclude-patching)         |      Patches to exclude while patching **APP_NAME**.      | []                             |
| [_APP_NAME_\_INCLUDE_PATCH\*\*](#custom-include-patching)       |      Patches to include while patching **APP_NAME**.      | []                             |
| [_APP_NAME_\_VERSION](#app-version)                             |         Version to use for download for patching.         | Recommended by patch resources |
| [_APP_NAME_\_PACKAGE_NAME\*\*\*](#any-patch-apps)               |           Package name of the app to be patched           | None                           |
| [_APP_NAME_\_DL_SOURCE\*\*\*](#any-patch-apps)                  |     Download source of any of the supported scrapper      | None                           |
| [_APP_NAME_\_DL\*\*\*](#app-dl)                                 |            Direct download Link for clean apk             | None                           |

`*` - By default all patches for a given app are included.<br>
`**` - Can be used to included universal patch.<br>
`***` - Can be used for unavailable apps in the repository (unofficial apps).

## Customization

1. **Officially** Supported values for **APP_NAME\*** are listed under `Code` column [here](../../../changelogs/auto/apps/README.md#supported-apps).
   <br>Note that the page syncs itself with the usage of `PATCHES_DL` resources in the `.env` file.
   <br>The sources of original APKs are from one of these apkmirror, apkpure, uptodown & apksos sites. I'm not responsible for any damaged caused.
   If you know any better/safe source to download clean. Open a discussion.

   <br>`*` - <a id="any-patch-apps"></a>You can also patch any other app which is **not** supported officially.To do so, you need to provide
   few more inputs to the tool which are mentioned below. These config will override the sources config from the tool.

   ```ini
   <APP_NAME>_DL_SOURCE=<apk-link-to-any-of-the-suppored-scraper-sites>
   <APP_NAME>_PACKAGE_NAME=<package-name-of-the-application>
   ```

   You can also provide `DL` to the clean apk instead of providing `DL_SOURCES` as mentioned in this [note](#app-dl).

   ```ini
   <APP_NAME>_DL=<direct-download-apk-link-to-any-site>
   <APP_NAME>_PACKAGE_NAME=<package-name-of-the-application>
   ```

   <br>Supported Scrappers are:
   1. APKMIRROR - Supports downloading any available version
      1. Link Format - `https://www.apkmirror.com/apk/<organisation-name>/app-name/`
      2. Example Link - https://www.apkmirror.com/apk/google-inc/youtube/
   2. UPTODOWN - Supports downloading any available version
      1. Link Format - `https://<app-name>.en.uptodown.com/android`
      2. Example Link - https://spotify.en.uptodown.com/android
   3. APKPURE - Supports downloading any available version
       1. Link Format - `https://apkpure.net/-/<package-name>`
       2. Example Link - https://apkpure.net/-/com.google.android.youtube
   4. APKEEP - Supports downloading any available version using [APKEEP](https://github.com/EFForg/apkeep)
       1. Link Format - `apkeep`
       2. Example Link - `apkeep`
       3. You need to provide `APKEEP_EMAIL` and `APKEEP_TOKEN` in `GitHub secrets` for authentication.

   <br>Please verify the source of original APKs yourself with links provided. I'm not responsible for any damage
   caused.If you know any better/safe source to download clean. Open a discussion.

2. By default, script build the latest version mentioned in `patches.json` file.
3. Remember to download the **_Microg_**. Otherwise, you may not be able to open YouTube/YouTube Music.
4. <a id="patch-apps"></a>By default, tool will build only `youtube,youtube_music`. To build other apps supported by patching
   resources.Add the apps you want to build in `.env` file or in `ENVS` in `GitHub secrets` in the format
   ```ini
   PATCH_APPS=<APP_NAME>
   ```
   Example:
   ```ini
   PATCH_APPS=youtube,twitter,reddit
   ```
5. <a id="existing-downloaded-apks"></a>If APKMirror or other apk sources are blocked in your region or script
   somehow is unable to download from apkmirror. You can download apk manually from any source. Place them in
   `/apks` directory and provide environment variable in `.env` file or in `ENVS` in `GitHub secrets` in the format.
   ```ini
    EXISTING_DOWNLOADED_APKS=<Comma,Seperate,App,Name>
   ```
   Example:
   ```ini
    EXISTING_DOWNLOADED_APKS=youtube,youtube_music
   ```
   If you add above. Script will not download the `YouTube` & `YouTube Music` apks from internet and expects an apk in
   `/apks` folder with names `youtube.apk` & `youtube_music.apk` (apk naming format - `<APP_NAME>.apk`) respectively.
6. <a id="personal-access-token"></a>If you run script again & again. You might hit GitHub/GitLab API limits.
   In that case you can provide your Personal Access Token by adding a secret `PERSONAL_ACCESS_TOKEN` in `GitHub secrets`.
7. <a id="global-resources"></a>You can provide Direct download to the resource to used for patching apps `.env` file
   or in `ENVS` in `GitHub secrets` in the format -

   ```ini
    GLOBAL_CLI_DL=https://github.com/revanced/revanced-cli
    GLOBAL_PATCHES_DL=https://api.revanced.app/v5/patches.rvp
   ```

   The ReVanced API `.rvp` endpoint is the default patches source because it provides the binary patch bundle directly.
   GitLab release URLs are also supported for resources. The tool resolves the latest release through GitLab's
   release API and filters release links/sources with the same asset extension regex used for GitHub.

   ```ini
    GLOBAL_CLI_DL=https://gitlab.com/example/revanced-cli
    GLOBAL_PATCHES_DL=https://gitlab.com/example/revanced-patches/-/releases/permalink/latest
   ```

   Resources downloaded from envs and will be used for patching for any **APP_NAME**.
   Unless provided different resource for the individual app.<br><br>
   Tool also support resource config at app level. You can patch A app with X resources while patching B with Y
   resources.
   This can be done by providing Direct download link for resources for app.<br>
   Example:

   ```ini
    YOUTUBE_CLI_DL=https://github.com/inotia00/revanced-cli
    YOUTUBE_PATCHES_DL=https://github.com/inotia00/revanced-patches/releases/latest
   ```

   With the config tool will try to patch YouTube with resources from inotia00 while other global resource will used
   for patching other apps.<br>
   **Multi-Patching Support**: You can now use multiple patch bundles from different creators for the same app:

   ```ini
    # Comma-separated URLs
    YOUTUBE_PATCHES_DL=https://gitlab.com/revanced/revanced-patches,https://github.com/indrastorm/Dropped-patches
   ```

   The tool will download all specified patch bundles and apply them together using the ReVanced CLI's multiple `-p` argument support.<br>
   If you have want to provide resource locally in the apks folder. You can specify that by mentioning filename
   prefixed with `local://`.<br>
   _Note_ - The link provided must be direct DLs, unless they are from GitHub or GitLab.<br>
   _Note_ - If your patches resource are available on GitHub/GitLab and you want to select latest resource without
    excluding pre-release you can add `latest-prerelease` to the URL.<br>

   Example:
   ```ini
    YOUTUBE_PATCHES_DL=https://github.com/inotia00/revanced-patches/releases/latest-prerelease
   ```
   For above example tool while selecting latest patches will consider pre-releases/beta too.
   For GitLab, `latest-prerelease` maps to GitLab's latest release because GitLab releases do not expose a separate
   pre-release flag in the release API.
    ```ini
    YOUTUBE_PATCHES_DL=https://github.com/inotia00/revanced-patches/releases/latest
   ```
   For above example tool while selecting latest patches will exclude any pre-release/beta ie. will consider only
    stable releases..<br>

   _Note_ - Some patch sources use **-** seperated names while others use space-separated names.
   Set `GLOBAL_NORMALIZE_PATCH_NAMES=False` to match patch names exactly as they appear in the source.

   <a id="cli-arg-compatibility"></a>CLI argument compatibility profiles and overrides:
   This builder now supports multiple CLI syntax families and key-value override maps.

   ```ini
   GLOBAL_CLI_ARGSF=morphe-cli
   GLOBAL_CLI_ARGSF=revanced-cli
   ```

   Built-in profile values:
   - `revanced-cli` (default, v6-style list-patches requires `-p/--patches`)
   - `morphe-cli` (morphe-style list-patches requires `--patches`)

   Override maps use unordered `KEY=value` pairs in a single string:

   ```ini
   GLOBAL_CLI_LPARGS="CMD=list-patches INDEX=-i PACKAGES=-p UNIVERSAL=-u VERSIONS=-v OPTIONS=-o PATCHES=__POSITIONAL__ PATCHES_POST="
   GLOBAL_CLI_PARGS="CMD=patch PATCHES=-p PATCHES_POST= ENABLED=-e DISABLED=-d OPTIONS=-O PURGE=--purge KEYSTORE=--keystore KEYSTORE_OLD='--keystore-entry-alias=alias --keystore-entry-password=ReVanced --keystore-password=ReVanced' EXCLUSIVE=--exclusive APK=__POSITIONAL__ OUTPUT=-o FORCE=--force RIP_LIB=--rip-lib"
   ```

   `PATCHES_POST` is an optional companion argument appended after every patch bundle (used by ReVanced v6 with `-b`).
   App-level overrides are also supported and take precedence:

   ```ini
   YOUTUBE_CLI_ARGSF=morphe-cli
   YOUTUBE_CLI_LPARGS="PATCHES=--patches"
   YOUTUBE_CLI_PARGS="PATCHES=-p STRIPLIBS=--striplibs FORCE='--force --continue-on-error'"
   ```

8. <a id="global-keystore-file-name"></a>If you don't want to use default keystore. You can provide your own by
   placing it inside `/apks` folder. And adding the filename of `keystore-file` in `.env` file or in `ENVS` in `GitHub
secrets` in the format -
   ```ini
    GLOBAL_KEYSTORE_FILE_NAME=revanced.keystore
   ```
   Tool also support providing secret key at app level. You can sign A app with X key while signing B with Y
   key.<br>
   Example:
   ```ini
    YOUTUBE_KEYSTORE_FILE_NAME=youtube.keystore
   ```
   Note - If you are using your own keystore and it was generated with cli v4, add
   Example:
   ```ini
    GLOBAL_OLD_KEY=False
   ```
   If you are using different key for different apps. You need to specify at app level.
   ```ini
   YOUTUBE_OLD_KEY=False
   ```
9. <a id="global-options-file"></a>If you don't want to use default `apks/options.yml` file. You can
   provide your own by placing it inside `apks` folder and adding the name of `options-file` in `.env` file
   or in `ENVS` in `GitHub secrets` in the format.

   ```ini
    GLOBAL_OPTIONS_FILE=my_options.yml
   ```

   Tool also supports configuring at app level with file as well as raw options (overrides).<br>

   Example:

   ```ini
    YOUTUBE_OPTIONS_FILE=my_cool_yt_options.yml
    YOUTUBE_OPTIONS_RAW="
    Custom branding:
      App name: YouTube
      Some setting: some value
    "
   ```

   **Options Merging & Precedence** — Options are resolved at three levels, each overriding the previous:

   ```
   Level 1: INI defaults from env vars / GitHub Secrets
   Level 2: YAML file (per-app with merging)
   Level 3: RAW string overrides (highest priority)
   ```

   When an app-specific options file is provided, its contents are **merged** with the global options file instead of replacing it. App-specific options override global options for the same patch/option key, while all non-conflicting global options are preserved.

   **Options Merging Example:**
   If your global `options.yml` defines Theme and SponsorBlock options, and your app-specific `my_cool_yt_options.yml` contains only a custom package name entry, the final merged set will include all three:

   ```
   Global options.yml         App options.yml           Final Merged Options
   ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
   │ Theme           │       │ Change package  │  =>   │ Theme           │
   │ SponsorBlock    │   +   │ name            │       │ SponsorBlock    │
   │ Custom branding │       └─────────────────┘       │ Change package  │
   └─────────────────┘                                 │ name            │
                                                       └─────────────────┘
   ```

   RAW overrides (Level 3) are applied on top of the merged result, giving you fine-grained control without duplicating entire option files.

   Note that this customization isn't available in the `RVX-Builds` tasker project. For now, use the `Universal` option
   for Patch Options to include options.yml entries from all patch resources being used.

10. <a id="global-archs-to-build"></a>You can build only for a particular arch in order to get smaller apk files. This
    can be done with by adding comma separated `ARCHS_TO_BUILD` in `.env` file or `ENVS` in `GitHub secrets` in the
    format.

    ```ini
     GLOABAL_ARCHS_TO_BUILD=arm64-v8a,x86_64
    ```

    Tool also support configuring at app level.<br>

    Example:

    ```ini
     YOUTUBE_ARCHS_TO_BUILD=arm64-v8a,armeabi-v7a
    ```

    _Note_ -
    1. Possible values are: `arm64-v8a`,`armeabi-v7a`,`x86_64`,`x86`.
    2. Make sure the patching resource (CLI) support this feature.

11. <a id="extra-files"></a>If you want to include any extra file (apks only) to the Github upload (releases). Set comma arguments
    in `.env` file or in `ENVS` in `GitHub secrets` in the format -
    ```ini
    EXTRA_FILES=<url>@<appName>.apk
    ```
    Example:
    ```ini
     EXTRA_FILES=https://github.com/inotia00/mMicroG/releases/latest@Mmicrog.apk,https://github.com/inotia00/VancedMicroG/releases/tag/v0.2.27.230755@Vmicrog.apk
    ```
12. <a id="custom-exclude-patching"></a>If you want to exclude any patch. Set comma separated patch in `.env` file
    or in `ENVS` in `GitHub secrets` in the format -
    ```ini
    <APP_NAME>_EXCLUDE_PATCH=<PATCH_TO_EXCLUDE-1,PATCH_TO_EXCLUDE-2,...>
    ```
    Example:
    ```ini
     YOUTUBE_EXCLUDE_PATCH=custom-branding,hide-get-premium
     YOUTUBE_MUSIC_EXCLUDE_PATCH=yt-music-is-shit
    ```
    <br>**Bundle-scoped exclusions** — When using multiple patch bundles, you can target a specific bundle
    by prefixing the patch name with a selector and colon:
    ```ini
     YOUTUBE_EXCLUDE_PATCH=2:disable-ads,^1-3:disable-analytics
    ```
    Where the selector before the colon is:
    - `N` — bundle index (1-indexed) only
    - `N-M` — bundle range
    - `^selector` — negation (except)
    - `*` — all bundles (same as bare patch name)

     <br>**Allowlist mode** — Prefix the first entry with ``EXCEPT::`` to flip the list from
     "deny these" to "keep only these":
     ```ini
      # Only keep custom-branding, deny everything else
      YOUTUBE_EXCLUDE_PATCH=EXCEPT::custom-branding
      # Only keep custom-branding from bundle 2 and ads from bundle 1
      YOUTUBE_EXCLUDE_PATCH=EXCEPT::2:custom-branding,1:disable-ads
     ```

     <br>**Name normalization** — Patch names are automatically normalized to lowercase
     dash-separated form. This lets you write names without worrying about the exact
     formatting used by the patch source:
     ```
     "Fix /s/ links"                  →  fix-s-links
     "Enable Android debugging"       →  enable-android-debugging
     "Custom Branding Icon (fork)"    →  custom-branding-icon-fork
     "Hide 'premium' banner!"         →  hide-premium-banner
     ```
     Set ``GLOBAL_NORMALIZE_PATCH_NAMES=False`` or
     ``<APP_NAME>_NORMALIZE_PATCH_NAMES=False`` to disable normalization and
     match patch names exactly as they appear in the source.

    Note -
    1. **All** the patches for an app are **included** by default.<br>
    2. Some patch sources use **-** separated names while others use space-separated names.
       Set `<APP_NAME>_NORMALIZE_PATCH_NAMES=False` to match patch names exactly as they appear in the source.
    3. Some patches are provided as space separated, make sure you type those in lowercase and **-** (hyphen or dash) separated here.
       It means a patch named `Hey There` must be entered as `hey-there` in the above example.
13. <a id="custom-include-patching"></a>If you want to include any universal patch. Set comma separated patch in `.env`
    file or in `ENVS` in `GitHub secrets` in the format -
    ```ini
    <APP_NAME>_INCLUDE_PATCH=<PATCH_TO_INCLUDE-1,PATCH_TO_INCLUDE-2>
    ```
    Example:
    ```ini
     YOUTUBE_INCLUDE_PATCH=remove-screenshot-restriction
    ```

    The same [bundle-scoped selectors](#custom-exclude-patching) and name normalization
    from ``EXCLUDE_PATCH`` also apply here. For example, to include a universal patch
    only from bundle 2:
    ```ini
     YOUTUBE_INCLUDE_PATCH=2:some-universal-patch
    ```

    Note -
    1. Some of the patch sources (like inotia00) may provide **-** seperated patches while some (ReVanced) shifted to
       Space formatted patches. Set `<APP_NAME>_NORMALIZE_PATCH_NAMES=False` to match patch names exactly as they appear in the source, if different from global.
    2. Some patches are provided as space separated, make sure you type those in lowercase and **-** (hyphen or dash) separated here.
       It means a patch named `Hey There` must be entered as `hey-there` in the above example.
    3. Not all patch sources provide universal patches.
    4. Go with `EXCLUDE_PATCH` if you didn't understand `INCLUDE_PATCH` purpose as that requires only regular patches.
14. <a id="app-version"></a>If you want to build a specific version or latest version. Add `version` in `.env` file
    or in `ENVS` in `GitHub secrets` in the format -
    ```ini
    <APP_NAME>_VERSION=<VERSION>
    ```
    Example:
    ```ini
    YOUTUBE_VERSION=17.31.36
    YOUTUBE_MUSIC_VERSION=X.X.X
    TWITTER_VERSION=latest # whatever latest is available (including beta)
    ```
15. <a id="app-dl"></a>If you have your personal source for apk to be downloaded. You can also provide that and tool
    will not scrape links from apk sources. Add `dl` in `.env` file or in `ENVS` in `GitHub secrets` in
    the format -
    ```ini
    <APP_NAME>_DL=<direct-app-download>
    ```
    Example:
    ```ini
    YOUTUBE_DL=https://d.apkpure.com/b/APK/com.google.android.youtube?version=latest
    ```
    Note that they are supposed to be direct DLs.
16. <a id="telegram-support"></a>For Telegram Upload.
    1. Set up a telegram channel, send a message to it and forward the message to
       this telegram [bot](https://t.me/username_to_id_bot)
    2. Copy `id` and save it to `TELEGRAM_CHAT_ID`<br>
       <img src="https://i.imgur.com/22UiaWs.png" width="300" style="left"><br>
    3. `TELEGRAM_BOT_TOKEN` - Telegram provides BOT_TOKEN. It works as sender. Open [bot](https://t.me/BotFather) and
       create one copy api key<br>
       <img src="https://i.imgur.com/A6JCyK2.png" width="300" style="left"><br>
    4. `TELEGRAM_API_ID` - Telegram API_ID is provided by telegram [here](https://my.telegram.org/apps)<br>
       <img src="https://i.imgur.com/eha3nnb.png" width="300" style="left"><br>
    5. `TELEGRAM_API_HASH` - Telegram API_HASH is provided by telegram [here](https://my.telegram.org/apps)<br>
       <img src="https://i.imgur.com/7n5k1mp.png" width="300" style="left"><br>
    6. After Everything done successfully a part of the actions secrets of the repository may look like<br>
       <img src="https://i.imgur.com/Cjifz1M.png" width="400">
17. Configuration defined in `ENVS` in `GitHub secrets` will override the configuration in `.env` file. You can use this
    fact to define your normal configurations in `.env` file and sometimes if you want to build something different just
    once, add it in `GitHub secrets`.<br>
    Or you can ignore what I wrote in above configs and always use `GitHub secrets`.<br><br>
    **Note - If you want to use or will be using `Automated` method to patch, please do not define anything inside `ENVS`.**
18. <a id="virus-total"></a>You can scan your built apks files with VirusTotal. For that, Add `VT_API_KEY` in `GitHub secrets`.
19. <a id="reddit-client"></a>If you want to patch reddit apps using your own Client ID. You can provide your Client ID
    as secret `REDDIT_CLIENT_ID` in `GitHub secrets`.
20. <a id="apprise"></a>[Apprise](https://github.com/caronc/apprise)<br>
    We also have apprise support to upload built apk anywhere. To use apprise, add below envs in `GitHub secrets`.
    ```ini
    APPRISE_URL=tgram://bot-token/chat-id
    APPRISE_NOTIFICATION_BODY=What a great Body
    APPRISE_NOTIFICATION_TITLE=What a great title
    ```
21. <a id="sample-env"></a>Sample Envs

    <img src="https://i.imgur.com/FxOtiGs.png" width="600" style="left">

    Here's the [another sample](/.env.example) in file format.<br>
    `#` are used to comment out lines. For example, `# APP_NAME_VERSION=latest_supported` is simply used to depict the latest supported the patch version.

22. <a id="workflow-permission"></a>Make your Action has write access. If not click here: https://github.com/OWNER/REPO/settings/actions. In the bottom give read and write access to Actions.

    <img src="https://i.imgur.com/STSv2D3.png" width="400">

    You may also require to [enable scheduled workflows](extras.md#scheduled-workflows) for the first time.

23. <a id="obtainium"></a>[Obtainium](https://github.com/ImranR98/Obtainium)<br>
    We support generating HTML files for Obtainium to scrape and download the latest patched APKs directly from your
    GitHub Releases. Enable this only when you are comfortable exposing a public APK discovery URL for your fork or
    self-hosted setup. Add below envs in `.env` file or in `ENVS` in `GitHub secrets` in the format
    ```ini
    OBTAINIUM_EXPORT=true
    ```
    This will generate an `obtainium_sources/` folder in the `changelogs` branch containing HTML files (e.g., `youtube.html`).
    You can then add the raw GitHub URL of these HTML files to Obtainium as an "HTML" source.
    Example URL: `https://raw.githubusercontent.com/<user>/<repo>/changelogs/obtainium_sources/youtube.html`
    Obtainium's HTML source can use the APK link hash as its release ID, so patch-only updates are detected through
    the generated release asset name without requiring a custom version extraction regex.

    **Optional Configuration**:
    ```ini
    OBTAINIUM_GITHUB_TAG=latest
    ```
    By default, links point to the `latest` release. If you want to link to a specific tag, set this variable.
    > **Warning**: Ensure your CI workflow is configured to release with the exact tag you specify. The default CI uses dynamic timestamp-based tags.
