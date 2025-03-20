# crimera/piko

***Release Version: [v1.51.0](https://github.com/crimera/piko/releases/tag/v1.51.0)***  
***Release Date: March 20, 2025, 09:52:41 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

## [1.51.0](https://github.com/crimera/piko/compare/v1.50.0...v1.51.0) (2025-03-20)

### Bug Fixes

* Add back settings for the custom sharemenu buttons ([bc7e777](https://github.com/crimera/piko/commit/bc7e777e59091801238d4692823415b0d7d2855b))
* Adding debug menu patch results in a crash ([caf82eb](https://github.com/crimera/piko/commit/caf82ebd95bd113dbd5cacda1deffa9194cb280b))
* **Bring back twitter:** Resource compilation fails on ReVanced Manager ([a364bec](https://github.com/crimera/piko/commit/a364becc7f6f70724c37b9499e79885fb09f0436))
* **Enable Reader Mode:** Specify the compatible version, show a warning instead of throwing an exception when failed ([b1c52e7](https://github.com/crimera/piko/commit/b1c52e73daabe3222e925ba5d6b866af31a35045))
* **Remove Detailed posts:** Change the settings label from "detailed" to "related" ([3cf5f9e](https://github.com/crimera/piko/commit/3cf5f9ec9e383deb17919f2b3c5254954502c825))
* Remove obsolete `Open browser chooser on opening links` patch ([a1e2b76](https://github.com/crimera/piko/commit/a1e2b766a872c3ee2facef1444bfa92ab4236144))

### Features

* **Settings:** Add a description to "Native features" page ([be7aa54](https://github.com/crimera/piko/commit/be7aa5472c9b12ff6207992b21292b4fb4d337cf))

### Updates

* Improve adding new buttons in share menu ([16cc3bd](https://github.com/crimera/piko/commit/16cc3bd01c03bfc800d61f0844b455c5d086422a))
</details>

# inotia00/revanced-patches

***Release Version: [v5.5.1](https://github.com/inotia00/revanced-patches/releases/tag/v5.5.1)***  
***Release Date: March 16, 2025, 04:09:18 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

YouTube
==
- feat(YouTube): Add `Change form factor` patch, Remove `Change layout` patch
- feat(YouTube): Replace with a fingerprint that supports a wider range of versions (..20.10)
- feat(YouTube - Spoof streaming data): Separate `Skip Onesie response encryption` setting from `Spoof streaming data` setting (For YouTube 19.34.42+, Closes https://github.com/inotia00/ReVanced_Extended/issues/2823)
- feat(YouTube - Spoof streaming data): Update innerTube client
- feat(YouTube - Spoof streaming data): Update side effects
- fix(YouTube - Custom branding icon): `Restore old splash animation` does not apply to dark theme
- fix(YouTube - Description components): `Hide Attributes section` setting not working for some users
- fix(YouTube - Overlay buttons): App crashes due to incorrect Context access https://github.com/inotia00/ReVanced_Extended/issues/2831
- fix(YouTube - Theme): Resolve dark mode startup crash with Android 9.0 (Match with ReVanced)


YouTube Music
==
- feat(YouTube Music): Add support version `8.10.51`
- feat(YouTube Music): Add `Spoof player parameter` patch https://github.com/inotia00/ReVanced_Extended/issues/2832
- feat(YouTube Music - Navigation bar components): Add `Replace Samples button` and `Replace Upgrade button` settings https://github.com/ReVanced/revanced-patches/issues/870
- feat(YouTube Music - Spoof client): Excluded by default https://github.com/inotia00/ReVanced_Extended/issues/2832
- fix(YouTube Music - Change start page): YouTube Music 6.20.51 does not allow changing the start page to `Search` (Not implemented)
- fix(YouTube Music - Disable music video in album): Redirects even from playlists other than `Album` https://github.com/inotia00/ReVanced_Extended/issues/2835


Reddit
==
- feat(Reddit): Replace with a fingerprint that supports a wider range of versions (..2025.10) https://github.com/inotia00/ReVanced_Extended/issues/2772#issuecomment-2724239839
- fix(Reddit - Hide ads): Promoted ads showing in comments


Shared
==
- build: Bump Dependency


Announcement
==
- YouTube Music's support version has been upgraded to **7.25.53, 8.05.51, 8.10.51**, but please read the following issue and upgrade only if necessary: [About 7.25.53](https://github.com/inotia00/ReVanced_Extended/issues/2554), [About 8.05.51, 8.10.51](https://github.com/inotia00/ReVanced_Extended/issues/2769).
- Compatible ReVanced Manager: [RVX Manager v1.23.5 (fork)](https://github.com/inotia00/revanced-manager/releases/tag/v1.23.5).


Contribute to translation
==
- [YouTube](https://crowdin.com/project/revancedextended)
- [YT Music](https://crowdin.com/project/revancedmusicextended)
</details>

# ReVanced/revanced-patches

***Release Version: [v5.14.0](https://github.com/ReVanced/revanced-patches/releases/tag/v5.14.0)***  
***Release Date: March 09, 2025, 12:22:24 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

# [5.14.0](https://github.com/ReVanced/revanced-patches/compare/v5.13.0...v5.14.0) (2025-03-09)


### Bug Fixes

* **Boost for reddit - Client spoof:** Use a different user agent to combat Reddit's API issues ([5d3c817](https://github.com/ReVanced/revanced-patches/commit/5d3c8175b34a3f6ae2732b25db0851773a8c000d))
* **YouTube - Change form factor:** Restore Automotive form factor watch history menu, channel pages, and community posts ([#4541](https://github.com/ReVanced/revanced-patches/issues/4541)) ([aa5c001](https://github.com/ReVanced/revanced-patches/commit/aa5c001968446e5270c756256724e917009612cd))
* **YouTube - Hide ads:** Hide new type of buttoned ad ([#4528](https://github.com/ReVanced/revanced-patches/issues/4528)) ([4387a7b](https://github.com/ReVanced/revanced-patches/commit/4387a7b131f49729e902e008bb4cec073635c040))
* **YouTube - Hide layout components:** Do not hide Movie/Courses start page content if 'Hide horizontal shelves' is enabled ([62a6164](https://github.com/ReVanced/revanced-patches/commit/62a6164b88b64200b517a5ba6b800d8214dbbad8))
* **YouTube - Theme:** Resolve dark mode startup crash with Android 9.0 ([741c2d5](https://github.com/ReVanced/revanced-patches/commit/741c2d59406f5d602554bb3a3c0b8982f42848b4))
* **YouTube:** Change language settings menu to use native language names ([#4568](https://github.com/ReVanced/revanced-patches/issues/4568)) ([6f3f8fd](https://github.com/ReVanced/revanced-patches/commit/6f3f8fdce05501e4fa4423c2170a916fbea3b199))
* **YouTube:** Combine `Restore old video quality menu` and `Remember video quality` into `Video quality` patch ([#4552](https://github.com/ReVanced/revanced-patches/issues/4552)) ([ee67b76](https://github.com/ReVanced/revanced-patches/commit/ee67b763d5c5947a5b1ef4420b1efa820ed6af83))


### Features

* **Infinity for Reddit:** Add support for package name on IzzyOnDroid ([#4554](https://github.com/ReVanced/revanced-patches/issues/4554)) ([cf9f959](https://github.com/ReVanced/revanced-patches/commit/cf9f959923076c10a7f0a29f6ba277f5a055ec07))
* **Spotify:** Add `Spoof signature` patch ([#4576](https://github.com/ReVanced/revanced-patches/issues/4576)) ([3646c70](https://github.com/ReVanced/revanced-patches/commit/3646c70556b67a6b7ecf9b86869ebf03c3611333))
* **YouTube - Remember video quality:** Add separate Shorts default quality settings ([#4543](https://github.com/ReVanced/revanced-patches/issues/4543)) ([88142ab](https://github.com/ReVanced/revanced-patches/commit/88142ab464192b564b1b8d56a6b45663f77f5e00))



</details>

