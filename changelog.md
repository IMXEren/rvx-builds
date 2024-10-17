# crimera/piko

***Release Version: [v1.42.0](https://github.com/crimera/piko/releases/tag/v1.42.0)***  
***Release Date: October 15, 2024, 23:05:25 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

## [1.42.0](https://github.com/crimera/piko/compare/v1.41.0...v1.42.0) (2024-10-15)

### Bug Fixes

* **Remove Google Ad:** Include ads in the comments ([79d6e35](https://github.com/crimera/piko/commit/79d6e35144ffc6c81d3bb36499fc2c22e5a089ac))

### Features

* **Bring back twitter:** Add Japanese ([4eb08b5](https://github.com/crimera/piko/commit/4eb08b554eaf92958e0e159647fc71b35340e2b2))

### Updates

* **Translations:** Update `Japanese` ([b326d10](https://github.com/crimera/piko/commit/b326d10599db407e1e922ac8d6d2694a67c6e42b))
</details>

# inotia00/revanced-patches

***Release Version: [v4.14.2](https://github.com/inotia00/revanced-patches/releases/tag/v4.14.2)***  
***Release Date: October 12, 2024, 17:34:32 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

YouTube
==
- chore(YouTube): replace with a fingerprint that supports a wider range of versions
- chore(YouTube/Spoof streaming data): update client constants
- feat(YouTube): replace with a fingerprint that supports a wider range of versions
- feat(YouTube/Custom Shorts action buttons):  add patch option `Cairo`
- feat(YouTube/Custom branding icon): remove patch option `YouTube (Minimal header)` due to copyright issues
- feat(YouTube/Overlay buttons): add patch option `WiderButtonsSpace` https://github.com/inotia00/revanced-patches/pull/87
- feat(YouTube/Shorts components): add `Hide stickers` setting https://github.com/ReVanced/revanced-patches/pull/3710
- feat(YouTube/Toolbar components): add `Hide YouTube Doodles` setting https://github.com/ReVanced/revanced-patches/pull/3743
- fix(YouTube): fix string typos and grammar https://github.com/inotia00/revanced-patches/pull/84
- fix(YouTube/Custom Shorts action buttons): low image quality for `Cairo` option on YouTube 18.29.38
- fix(YouTube/Hide feed components): `Hide Carousel Shelf` setting sometimes hides the library shelf when a user is playing a video in the library tab
- fix(YouTube/Hide feed components): `Hide Latest videos button` setting does not support tablets https://github.com/inotia00/revanced-patches/pull/89
- fix(YouTube/Hide feed components): `Hide UPCOMING video` setting now only hides the video when the thumbnail can be hidden (close https://github.com/inotia00/ReVanced_Extended/issues/2427)
- fix(YouTube/Hide feed components): `Hide related videos` setting does not work in landscape mode on tablet
- fix(YouTube/Hide feed components): change default offset for `Hide related videos` setting
- fix(YouTube/Settings): EditTextDialog's background color does not match when `Theme` patch is excluded https://github.com/inotia00/ReVanced_Extended/issues/2422
- fix(YouTube/Settings): If the title of the setting is too long, it will be displayed as `...`
- fix(YouTube/Settings): restart dialog is missing for some settings
- fix(YouTube/Shorts components): Shorts are hidden in Watch history shelf in Library tab
- fix(YouTube/Shorts components): `Hide paused header` setting does not work
- fix(YouTube/Shorts components): `Replace channel handle` setting no longer uses RSS feeds to retrieve usernames
- fix(YouTube/Spoof streaming data): `Authorization` key is always included when fetching an API, even if there is no `Authorization` in the header (e.g. the user is not logged in or using the Incognito Mode)
- fix(YouTube/Spoof streaming data): playback issues occur when data connection changes or RVX has been open for a long time https://github.com/inotia00/ReVanced_Extended/issues/2416
- fix(YouTube/Spoof streaming data): revert `reduce response timeout and cache size`
- fix(YouTube/Spoof streaming data): update side effects
- fix(YouTube/Spoof streaming data): use cache expiration
- fix(YouTube/Spoof streaming data): wrong package name used in User-Agent
- refactor(YouTube/Layout switch): refine settings
- feat(YouTube/Translations): update translation


YouTube Music
==
- chore(YouTube Music): replace with a fingerprint that supports a wider range of versions
- feat(YouTube Music/Spoof app version): add target version `7.16.53`
- fix(YouTube Music/Spoof app version): ListPreference sometimes selects wrong values
- fix(YouTube Music/Player components): `Hide Audio / Video toggle` setting not working in landscape mode
- fix(YouTube Music/Player components): `Remember shuffle state` setting does not remember the correct state
- fix(YouTube Music/Player components): patches do not apply properly in certain versions
- feat(YouTube Music/Translations): update translation


Shared
==
- build: bump dependencies
- fix(Hide settings menu): do not use strings for filtering (Close https://github.com/inotia00/ReVanced_Extended/issues/2043)


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

***Release Version: [v4.16.0](https://github.com/ReVanced/revanced-patches/releases/tag/v4.16.0)***  
***Release Date: September 30, 2024, 19:16:41 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

# [4.16.0](https://github.com/ReVanced/revanced-patches/compare/v4.15.0...v4.16.0) (2024-09-30)


### Bug Fixes

* **Soundcloud:** Support latest versions ([#3702](https://github.com/ReVanced/revanced-patches/issues/3702)) ([099ac5e](https://github.com/ReVanced/revanced-patches/commit/099ac5ea2cf55633a7c6a7e6f8e963599bcd5784))
* **Twitter - Open links with app chooser:** Fix incorrect version in compatibility list ([#3683](https://github.com/ReVanced/revanced-patches/issues/3683)) ([adafe85](https://github.com/ReVanced/revanced-patches/commit/adafe85d77f6a0031a5523b9b7da69475959d78d))
* **YouTube - SponsorBlock:** Fade out SB buttons without overlapping other buttons ([#3719](https://github.com/ReVanced/revanced-patches/issues/3719)) ([bf96108](https://github.com/ReVanced/revanced-patches/commit/bf9610894f0a9f9e751e2eed5b825c5d327a722c))
* **YouTube:** Show video chapter titles without clipping when overlay buttons are enabled ([#3674](https://github.com/ReVanced/revanced-patches/issues/3674)) ([4b88c31](https://github.com/ReVanced/revanced-patches/commit/4b88c316ed90c56e83e2aee266561833b36fc37d))


### Features

* **Google Photos:** Restore hidden 'Back up while charging' toggle ([#3678](https://github.com/ReVanced/revanced-patches/issues/3678)) ([f9e19ce](https://github.com/ReVanced/revanced-patches/commit/f9e19ce6e9185fdf31b2b0d5f2934f6e8a544b8e))
* **YouTube - Disable precise seeking gesture:** Hide "pull up" label that shows up when swiping ([#3668](https://github.com/ReVanced/revanced-patches/issues/3668)) ([3fa8af9](https://github.com/ReVanced/revanced-patches/commit/3fa8af9fe534b59ad093c36f1927f56f549a330d))
* **YouTube - Hide Shorts components:** Add `Hide save music`, `Hide stickers` ([#3710](https://github.com/ReVanced/revanced-patches/issues/3710)) ([8c99321](https://github.com/ReVanced/revanced-patches/commit/8c99321df4db696156330fc90dd547c1345d880e))
* **YouTube - Hide Shorts components:** Add patch option to hide Shorts app shortcut (long press app icon) ([#3699](https://github.com/ReVanced/revanced-patches/issues/3699)) ([0d4e1f5](https://github.com/ReVanced/revanced-patches/commit/0d4e1f5d03cf3dcc06fd41165e26a1ce901b976b))
* **YouTube - Hide Shorts components:** Add patch option to hide Shorts from app launcher widget ([#3707](https://github.com/ReVanced/revanced-patches/issues/3707)) ([838f183](https://github.com/ReVanced/revanced-patches/commit/838f1834a5df547ce2c3217b874c0594b6878a67))



</details>

