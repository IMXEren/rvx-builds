# crimera/piko

***Release Version: [v1.42.1](https://github.com/crimera/piko/releases/tag/v1.42.1)***  
***Release Date: October 24, 2024, 02:27:24 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

## [1.42.1](https://github.com/crimera/piko/compare/v1.42.0...v1.42.1) (2024-10-24)

### Bug Fixes

* **Bring back twitter:** Change the character "𝕏" into "Twitter". ([#441](https://github.com/crimera/piko/issues/441)) ([c20e16f](https://github.com/crimera/piko/commit/c20e16f80499df75176e9080f156e529f4f7d326))
* **Custom download folder:** Restore compatibility with versions prior to 10.64 ([b88b00b](https://github.com/crimera/piko/commit/b88b00ba97632d62517c0e52a924c453ea022d7a))
* **Custom downloader:** Improve fingerprint ([2a2a4a4](https://github.com/crimera/piko/commit/2a2a4a4e2cdc6587c5c3b91bb3888918d7cd720d))
* Resource strings getting corrupted, resulting on failure to patch on revanced manager ([#439](https://github.com/crimera/piko/issues/439)) ([1763137](https://github.com/crimera/piko/commit/1763137126b9a95df51fe23ce816853ccf0a8f44))
* **Twitter:** Add support for version 10.64.0-beta.1 ([c81378d](https://github.com/crimera/piko/commit/c81378d80275465acbf9caed5f48235b56395d56))

### Refactors

* **Custom Downloader:** Improve getting of tweet method declarations ([5237e49](https://github.com/crimera/piko/commit/5237e496140cc94fb9beb4a72057d927527dd78b))
</details>

# inotia00/revanced-patches

***Release Version: [v4.15.1](https://github.com/inotia00/revanced-patches/releases/tag/v4.15.1)***  
***Release Date: October 21, 2024, 11:32:19 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

YouTube
==
- chore(YouTube): replace with a fingerprint that supports a wider range of versions
- chore(YouTube/Inclusive Span): change to shared patch
- chore(YouTube/PlayerType): supplement PlayerType limits under certain conditions
- feat(YouTube/Hide comments components): add `Hide highlighted search links` setting https://github.com/inotia00/ReVanced_Extended/issues/2435
- feat(YouTube/Hide feed components): remove `Hide UPCOMING video` setting https://github.com/inotia00/ReVanced_Extended/issues/2427#issuecomment-2422285736
- feat(YouTube/Hide player flyout menu): add `Hide 1080p Premium menu` setting https://github.com/ReVanced/revanced-patches/issues/3760
- feat(YouTube/Player components): add `Sanitize video subtitle` setting https://github.com/ReVanced/revanced-patches/issues/2758
- feat(YouTube/Seekbar components): add `Disable seekbar chapters` setting https://github.com/inotia00/revanced-patches/pull/90
- feat(YouTube/Shorts components): add `Hide in channel` setting (Hide the Shorts shelf on the channel home tab)
- feat(YouTube/Spoof app version): add target version `19.13.37 - Restores old style Rolling number animations` https://github.com/inotia00/ReVanced_Extended/issues/2419#issuecomment-2408912233
- feat(YouTube/Spoof app version): show the dialog when the app is first launched (YouTube 19.16.39+) https://github.com/inotia00/ReVanced_Extended/issues/2419#issuecomment-2424322396
- feat(YouTube/Swipe controls): add `Swipe sensitivity` settings https://github.com/ReVanced/revanced-patches/issues/1646
- fix(YouTube/Hide ads): `Hide view products banner` setting not working https://github.com/inotia00/ReVanced_Extended/issues/2437
- fix(YouTube/Hide ads): new type of ads are not hidden
- fix(YouTube/Hide feed components): `Hide carousel shelf` setting hides the library shelf
- fix(YouTube/Hide feed components): new type of Playable is not hidden
- fix(YouTube/Hook YouTube Music actions): app crashes when first installed
- fix(YouTube/LithoFilter): remove unused keywords
- fix(YouTube/Shorts components): app crashes when `Replace channel handle` setting is turned on
- fix(YouTube/Shorts components): new type of shelf is not hidden
- fix(YouTube/Spoof streaming data): wrong register used
- feat(YouTube/Translations): update translation


YouTube Music
==
- chore(YouTube Music): replace with a fingerprint that supports a wider range of versions
- fix(YouTube Music/Spoof app version): app crashes when first installed
- fix(YouTube Music/Custom branding icon): patch fails on certain versions
- feat(YouTube Music/Navigation bar components): do not use hardcoded color `Enable black navigation bar` setting is turned off https://github.com/inotia00/ReVanced_Extended/issues/2440
- feat(YouTube Music/Translations): update translation


Shared
==
- chore(YouTube/YT Music): clarify and fix some strings https://github.com/inotia00/revanced-patches/pull/91
- chore(YouTube/YT Music - GmsCore support - GmsCore support): improve performance by using hashsets
- feat(YouTube/YT Music): add `Return YouTube Username` patch
- feat(YouTube/YT Music - GmsCore support): add patch option `Disable GmsService Broker` https://github.com/inotia00/ReVanced_Extended/issues/2442#issuecomment-2424694043
- feat(YouTube/YT Music - Return YouTube Dislike): add `Show estimated likes` setting https://github.com/ReVanced/revanced-patches/issues/3667
- feat(YouTube/YT Music - Return YouTube Username): add `Display format` setting
- fix(YouTube/YT Music - GmsCore support): unimplemented service in GmsCore causes memory leak https://github.com/ReVanced/revanced-patches/issues/3768
- fix(YouTube/YT Music - Return YouTube Username): patch does not work when `Display format` is `Username only`


Announcement
==
- **There is a change in `options.json`. If you see warnings related to patch options, remove the `options.json` file or `Patch options`.**
- YouTube's support version has been rolled back to **19.16.39** for the following reasons: https://github.com/inotia00/ReVanced_Extended/issues/2241.
- YouTube Music's support version has been rolled back to **7.16.53** for the following reasons: https://github.com/inotia00/ReVanced_Extended/issues/2382.
- Reddit 2024.18.0+ can only be patched via [CLI](https://github.com/inotia00/revanced-documentation/blob/main/docs/latest-reddit-patch-info.md) or rvx-builder.
- Compatible ReVanced Manager: [RVX Manager v1.22.2 (fork)](https://github.com/inotia00/revanced-manager/releases/tag/v1.22.2).


Contribute to translation
==
- [YouTube](https://crowdin.com/project/revancedextended)
- [YT Music](https://crowdin.com/project/revancedmusicextended)</details>

# ReVanced/revanced-patches

***Release Version: [v4.17.0](https://github.com/ReVanced/revanced-patches/releases/tag/v4.17.0)***  
***Release Date: October 20, 2024, 01:43:38 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

# [4.17.0](https://github.com/ReVanced/revanced-patches/compare/v4.16.0...v4.17.0) (2024-10-20)


### Bug Fixes

* **Twitter - Unlock downloads:** Support latest version ([#3782](https://github.com/ReVanced/revanced-patches/issues/3782)) ([5189122](https://github.com/ReVanced/revanced-patches/commit/5189122006b0f72d5bfb50422021c3b0f3a9ae4a))
* **YouTube - GmsCore support:** Add more replacements ([4d39770](https://github.com/ReVanced/revanced-patches/commit/4d39770602b39b6cb399eb0d8c52947b6ebafbb0))
* **YouTube - GmsCore support:** Remove unclear patch changes ([021d858](https://github.com/ReVanced/revanced-patches/commit/021d8584a7f5a6d1a028c5d18dc91a3b988b2884))
* **YouTube - Spoof video streams:** Fix playback for Android VR by removing invalid body as well ([#3769](https://github.com/ReVanced/revanced-patches/issues/3769)) ([5150a15](https://github.com/ReVanced/revanced-patches/commit/5150a15ad4ca73a747f0a89f933db7f2d686ec2d))


### Features

* **Backdrops - Pro unlock:** Support latest versions by removing version constraint ([a62b506](https://github.com/ReVanced/revanced-patches/commit/a62b50691c49d1ce529a7c9c4e49da0d0dd46df2))
* **Facebook:** Add `Hide sponsored stories` patch ([#3627](https://github.com/ReVanced/revanced-patches/issues/3627)) ([214c72b](https://github.com/ReVanced/revanced-patches/commit/214c72baeb7f87f21cd2ca34301ab11fa0ff1a4f))
* **Sync for Reddit:** Add `Fix video downloads` patch ([#3739](https://github.com/ReVanced/revanced-patches/issues/3739)) ([a47ee38](https://github.com/ReVanced/revanced-patches/commit/a47ee38b1cdd974a959008006ecaf58917addc60))
* **Twitter:** Add `Change link sharing domain` patch ([#3753](https://github.com/ReVanced/revanced-patches/issues/3753)) ([9269a07](https://github.com/ReVanced/revanced-patches/commit/9269a076b674ecdcf478bca842238f6e30869f44))
* **Willhaben:** Add `Hide ads` patch ([#3740](https://github.com/ReVanced/revanced-patches/issues/3740)) ([1fe3a52](https://github.com/ReVanced/revanced-patches/commit/1fe3a523e99ccfe556d88800686e34ac6ed77b2c))
* **YouTube - Hide layout components:** Add option to hide YouTube Doodles ([#3743](https://github.com/ReVanced/revanced-patches/issues/3743)) ([b8c8916](https://github.com/ReVanced/revanced-patches/commit/b8c89164cf3911ac3842df9b0d2ec42b52213505))
* **YouTube - Hide Shorts components:** Add option to hide `Use template`, `Upcoming`, `Green screen` buttons ([#3752](https://github.com/ReVanced/revanced-patches/issues/3752)) ([f71c406](https://github.com/ReVanced/revanced-patches/commit/f71c4068bc646d02954b59fac4756f1419c55dbe))
* **YouTube - Hide Shorts components:** Add option to hide like fountain ([#3731](https://github.com/ReVanced/revanced-patches/issues/3731)) ([00a99dd](https://github.com/ReVanced/revanced-patches/commit/00a99dd13be6e5c44fa691d74c92b23ce6ba659d))
* **YouTube - Hide Shorts components:** Hide `Hashtag` button ([#3787](https://github.com/ReVanced/revanced-patches/issues/3787)) ([828a634](https://github.com/ReVanced/revanced-patches/commit/828a634667c4005a90f3e469ad2c5d69387f0760))
* **YouTube:** Support versions `19.25` and `19.34` ([#3629](https://github.com/ReVanced/revanced-patches/issues/3629)) ([049e7f0](https://github.com/ReVanced/revanced-patches/commit/049e7f081358d2e1bf87d30e87b01c61b5eeafcc))


### Performance Improvements

* **YouTube - GmsCore support:** Improve performance by using hashsets ([2c5d390](https://github.com/ReVanced/revanced-patches/commit/2c5d390fb1275dc3da5a3b912e221b7d594a1561))



</details>

