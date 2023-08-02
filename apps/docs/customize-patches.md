# Customizing Patches

(Pay attention to 3,4)<br>
By default, script build the version as recommended by Revanced team.

1. Supported values for **REVANCED_APPS_NAME** are listed under `Code` column [here](README.md#supported-apps)
    <br>The sources of original APKs are from one of these apkmirror, apkpure, uptodown & apksos sites. I'm not responsible for any damaged caused.
    If you know any better/safe source to download clean. Please raise a PR.

2. Remember to download the **_Microg_**. Otherwise, you will not be able to open YouTube or YouTube Music.
3. By default, it will build only `youtube` & `youtube_music`. To build other apps supported by revanced team.
   Add the apps you want to build in `.env` file or in `ENVS` in
   `GitHub secrets` in the format.
   ```ini
   PATCH_APPS=<REVANCED_APPS_NAME>
   ```
   Example:
   ```ini
   PATCH_APPS=youtube,twitter,reddit,reddit_sync
   ```
4. If you want to exclude any patch. Set comma separated patch in `.env` file (Recommended) or in `ENVS` in `GitHub secrets` in the format. 
   
   **Note** - If patches are provided space separated, make sure you type those in **_lower case_** & replace spaces with **-** **_(hyphen)_** separated here. It means a patch named `Hey There` will be entered as `hey-there` in the above example.
   ```ini
   EXCLUDE_PATCH_<REVANCED_APPS_NAME>=<PATCH_TO_EXCLUDE-1,PATCH_TO_EXCLUDE-2>
   ```
   Example:
   ```ini
    EXCLUDE_PATCH_YOUTUBE=custom-branding,hide-get-premium
    EXCLUDE_PATCH_YOUTUBE_MUSIC=yt-music-is-shit
   ```
   If you are using `Revanced Extended.` Add `_EXTENDED` in exclude options.
   Example:
   ```ini
    EXCLUDE_PATCH_YOUTUBE_EXTENDED=custom-branding-red,custom-branding-blue,materialyou
    EXCLUDE_PATCH_YOUTUBE_MUSIC_EXTENDED=custom-branding-music
   ```
   **_All the patches for an app are included by default._**.<br><br>If you want to apply a universal patch. You can
   include it
   manually. See below for more information. Note that universal patches are only provided by ReVanced and not by ReVanced Extended (RVX).<br>
   If you want to include any universal patch. Set comma separated patch in `.env` file or in `ENVS` in `GitHub
   secrets`
   (Recommended) in the format
   ```ini
   INCLUDE_PATCH_<REVANCED_APPS_NAME>=<PATCH_TO_EXCLUDE-1,PATCH_TO_EXCLUDE-2>
   ```
5. If you want to build a specific version. Add `version` in `.env` file (Recommended) or in `ENVS` in `GitHub secrets` in the format
   ```ini
   <APPNAME>_VERSION=<VERSION>
   ```
   Example:
   ```ini
   YOUTUBE_VERSION=17.31.36
   YOUTUBE_MUSIC_VERSION=X.X.X
   TWITTER_VERSION=X.X.X
   REDDIT_VERSION=X.X.X
   TIKTOK_VERSION=X.X.X
   WARNWETTER_VERSION=X.X.X
   ```
6. If you want to build `latest` version, whatever latest is available (including
   beta) .
   Add `latest` in `.env` file  (Recommended) or in `ENVS` in `GitHub secrets` in the format

   ```ini
   <APPNAME>_VERSION=latest
   ```

   Example:

   ```ini
   YOUTUBE_VERSION=latest
   YOUTUBE_MUSIC_VERSION=latest
   TWITTER_VERSION=latest
   REDDIT_VERSION=latest
   TIKTOK_VERSION=latest
   WARNWETTER_VERSION=latest
   ```

7. If you don't want to use default keystore. You can provide your own by placing it
   inside `apks` folder. And adding the name of `keystore-file` in `.env` file or in `ENVS` in `GitHub secrets`
   (Recommended) in the format
   ```ini
    KEYSTORE_FILE_NAME=revanced.keystore
   ```
8. If you want to use Revanced-Extended to patch apps, add the following code
   in `.env` file (Recommended) or in `ENVS` in `GitHub secrets` in the format. Note that if you set it to `True`, all apps available to be patched by RVX will be patched and rest using ReVanced. Here, available means that the app can be patched using rvx patches and the repo must contain the required configurations to do so, otherwise ReVanced will be used while patching.
   ```ini
    BUILD_EXTENDED=True
   ```
   or disable it with (default)
   ```ini
    BUILD_EXTENDED=False
   ```
9. For Telegram Upload.
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
    6. After Everything done successfully the actions secrets of the repository will look something like<br>
       <img src="https://i.imgur.com/dzC1KFa.png" width="400">
10. You can build only for a particular arch in order to get smaller apk files. This can be done with by adding comma
    separated `ARCHS_TO_BUILD` in `.env` file (Recommended) or in `ENVS` in `GitHub secrets` (Recommended) in the format.
    ```ini
     ARCHS_TO_BUILD=arm64-v8a,armeabi-v7a
    ```
    Possible values for `ARCHS_TO_BUILD` are: `armeabi-v7a`,`x86`,`x86_64`,`arm64-v8a`
    Make sure you are using `revanced-extended` as `revanced` doesn't support this and would be ignored for apps patched by `revanced`.
11. You can scan your built apks files with VirusTotal. For that, Add `VT_API_KEY` in `GitHub secrets`.
12. Configuration defined in `ENVS` in `GitHub secrets` will override the configuration in `.env` file. You can use this
    fact to define your normal configurations in `.env` file and sometimes if you want to build something different just
    once. Add it in `GitHub secrets`.<br>
    Or you can ignore what I said above and always use `GitHub secrets`.<br>
    **Note - If you want to use or will be using `Automated` method to patch, please do not define anything inside `ENVS`.**
13. If APKMirror or other apk source is blocked in your region or script somehow is unable to download from apkmirror.
    You can download apk manually from any source. Place them in `/apks` directory and provide environment variable
    in `.env` file or in `ENVS` in `GitHub secrets`(Recommended) in the format.
    ```ini
     EXISTING_DOWNLOADED_APKS=<Comma,Seperate,App,Name>
    ```
    Example:
    ```ini
     EXISTING_DOWNLOADED_APKS=youtube,youtube_music
    ```
    If you add above. Script will not download the `YouTube` & `YouTube Music`apk from internet and expects an apk in
    `/apks` folder with names `youtube.apk` & `youtube_music.apk` (apk naming format - `<REVANCED_APPS_NAME>.apk`) respectively.

    Name of the downloaded apk must match with the available app choices similar to what you can use for `PATCH_APPS`.
14. If you run script again & again. You might hit GitHub API limit. In that case you can provide your Personal
    GitHub Access Token by adding a secret `PERSONAL_ACCESS_TOKEN` in `GitHub secrets`.
15. Sample Envs<br>
    ```ini
    DRY_RUN=False
    KEYSTORE_FILE_NAME=revanced.keystore
    ARCHS_TO_BUILD=arm64-v8a
    BUILD_EXTENDED=True
    PATCH_APPS=reddit,twitter,trakt,youtube,youtube_music

    # REDDIT_VERSION=latest_supported

    # TWITTER_VERSION=latest_supported
    EXCLUDE_PATCH_TWITTER=hide-recommended-users,dynamic-color

    # TRAKT_VERSION=latest_supported

    # YOUTUBE_VERSION=latest_supported
    EXCLUDE_PATCH_YOUTUBE_EXTENDED=custom-branding-youtube-name,custom-branding-icon-mmt,custom-branding-icon-revancify-red,custom-package-name,enable-debug-logging,force-premium-heading,materialyou

    # YOUTUBE_MUSIC_VERSION=latest_supported
    EXCLUDE_PATCH_YOUTUBE_MUSIC_EXTENDED=custom-branding-music-name,custom-branding-icon-mmt,custom-branding-icon-revancify-red,custom-package-name,enable-debug-logging
    ```
    `#` are used to comment out lines.
16. Make your Action has write access. If not click
    [here](https://github.com/IMXEren/rvx-builds/settings/actions).
    In the bottom give read and write access to Actions.
    <img src="https://i.imgur.com/STSv2D3.png" width="400">
17. If you want to patch reddit apps using your own Client ID. You can provide your Client ID
    as secret `REDDIT_CLIENT_ID` in `GitHub secrets`.