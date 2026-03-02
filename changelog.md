# crimera/piko

***Release Version: [v3.0.0-dev.9](https://github.com/crimera/piko/releases/tag/v3.0.0-dev.9)***  
***Release Date: February 26, 2026, 06:08:18 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

# [3.0.0-dev.9](https://github.com/crimera/piko/compare/v3.0.0-dev.8...v3.0.0-dev.9) (2026-02-26)


### Bug Fixes

* fix webview resource id ([6c1c81d](https://github.com/crimera/piko/commit/6c1c81d057f3bee73ed8fb53cc95665b89e9c973))



</details>

# MorpheApp/morphe-cli

***Release Version: [v1.4.0](https://github.com/MorpheApp/morphe-cli/releases/tag/v1.4.0)***  
***Release Date: February 21, 2026, 07:09:05 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

# [1.4.0](https://github.com/MorpheApp/morphe-cli/compare/v1.3.0...v1.4.0) (2026-02-21)


### Bug Fixes

* Allow enabling/disabling patches using case insensitive patch names ([#48](https://github.com/MorpheApp/morphe-cli/issues/48)) ([03a280a](https://github.com/MorpheApp/morphe-cli/commit/03a280abea6c9187eec22548707eb889b0252c3f))
* Do not log patch name more than once if disabled ([#49](https://github.com/MorpheApp/morphe-cli/issues/49)) ([b980bb8](https://github.com/MorpheApp/morphe-cli/commit/b980bb8e0b3bf8eb4c7af1fe289ff1b63c437fa3))


### Features

* Add `--continue-on-error` argument, return non zero exit code if patching fails ([#47](https://github.com/MorpheApp/morphe-cli/issues/47)) ([255646b](https://github.com/MorpheApp/morphe-cli/commit/255646b250237087ab7d7f9733daa6751b7e4016))
* Add `--options-file` json patch/option configuration ([#53](https://github.com/MorpheApp/morphe-cli/issues/53)) ([44943da](https://github.com/MorpheApp/morphe-cli/commit/44943da5f40f8ec37364d4f67b9d2e82d2b5e98f))
* Add `--striplibs` argument to strip unwanted architectures ([#46](https://github.com/MorpheApp/morphe-cli/issues/46)) ([7442d94](https://github.com/MorpheApp/morphe-cli/commit/7442d942d392b3e1e9ce959c30db8460bffee8d6))
* Support patching APKM bundles ([#40](https://github.com/MorpheApp/morphe-cli/issues/40)) ([bfe43d0](https://github.com/MorpheApp/morphe-cli/commit/bfe43d0b747d0e336a3f36f048e85907a140f1fc))



</details>

# ReVanced/revanced-patches

***Release Version: [v5.50.2](https://github.com/ReVanced/revanced-patches/releases/tag/v5.50.2)***  
***Release Date: February 15, 2026, 22:56:06 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

## [5.50.2](https://github.com/ReVanced/revanced-patches/compare/v5.50.1...v5.50.2) (2026-02-15)


### Bug Fixes

* Add missing patch option descriptions ([16e42a7](https://github.com/ReVanced/revanced-patches/commit/16e42a75ecbf51e06432f1f6c96758f8d9bdb771))

## [5.50.1](https://github.com/ReVanced/revanced-patches/compare/v5.50.0...v5.50.1) (2026-02-15)

### Bug Fixes

* Disable `Prevent screenshot detection` by default ([#6511](https://github.com/ReVanced/revanced-patches/issues/6511)) ([5b5c502](https://github.com/ReVanced/revanced-patches/commit/5b5c50254d533faa0e04d542f4859cbef610713e))
* **Instagram - Open links externally:** Fix patch by handling >4-bit register ([#6538](https://github.com/ReVanced/revanced-patches/issues/6538)) ([f681a6f](https://github.com/ReVanced/revanced-patches/commit/f681a6ffd45f05a61743e7d272cd68c4b743be42))
* **Instagram:** Make `Change link sharing domain` and `Sanitize sharing links` work with latest versions again ([#6518](https://github.com/ReVanced/revanced-patches/issues/6518)) ([85a9079](https://github.com/ReVanced/revanced-patches/commit/85a9079c25760d0329e518e379eeefe3beeea143))
* **Letterboxd - Hide ads:** Fix patch by returning the correct return type ([#6527](https://github.com/ReVanced/revanced-patches/issues/6527)) ([80c34b9](https://github.com/ReVanced/revanced-patches/commit/80c34b9d74a42018a0cd52b4a584ee71206bf963))
* Process strings from Crowdin to strip the app/patch prefixes again ([e566efc](https://github.com/ReVanced/revanced-patches/commit/e566efc51fca45c6284406245a360685a8e90d74))
* **Strava:** Fix `Add media download` patch ([#6526](https://github.com/ReVanced/revanced-patches/issues/6526)) ([dc9e68b](https://github.com/ReVanced/revanced-patches/commit/dc9e68ba574dd9f35cd742cb63193c5d875addde))


### Features

* **FotMob:** Add `Hide ads` patch ([#6566](https://github.com/ReVanced/revanced-patches/issues/6566)) ([4b0b737](https://github.com/ReVanced/revanced-patches/commit/4b0b7374f21d13599ef2f1e2f5880e7589b0874e))
* **GmsCore support:** Reduce amount of necessary changes and add update check ([#6582](https://github.com/ReVanced/revanced-patches/issues/6582)) ([650e6a2](https://github.com/ReVanced/revanced-patches/commit/650e6a271075b57368432cd9d4294fd1ce26cceb))
* **Instagram:** Add `Disable analytics` patch ([#6531](https://github.com/ReVanced/revanced-patches/issues/6531)) ([ad92864](https://github.com/ReVanced/revanced-patches/commit/ad92864483a21d7eae7952c8f8429cde3d44e848))
* **Kleinanzeigen:** Add `Hide ads` patch ([#6533](https://github.com/ReVanced/revanced-patches/issues/6533)) ([bd6e544](https://github.com/ReVanced/revanced-patches/commit/bd6e544007d539ac2eb890d9bdcb6850435f96cb))
* **Kleinanzeigen:** Add `Hide PUR` patch  ([#6558](https://github.com/ReVanced/revanced-patches/issues/6558)) ([4958ecf](https://github.com/ReVanced/revanced-patches/commit/4958ecf10c880e9e7f15dd2e58ebaefbf49e417a))
* **Microsoft Lens:** Remove migration to OneDrive ([#6551](https://github.com/ReVanced/revanced-patches/issues/6551)) ([e389632](https://github.com/ReVanced/revanced-patches/commit/e389632afd52403aba26b6981d098b93cea45e00))
* **Nothing X:** Add `Show K1 token(s)` patch ([#6490](https://github.com/ReVanced/revanced-patches/issues/6490)) ([421cb28](https://github.com/ReVanced/revanced-patches/commit/421cb2899ef5c0f100fb8007bae8b89137d0e41c))
* **Strava:** Add `Hide distractions` patch ([#6479](https://github.com/ReVanced/revanced-patches/issues/6479)) ([66b0852](https://github.com/ReVanced/revanced-patches/commit/66b0852f8fa57c82b09997337a304374883d8ba5))
* **YouTube Music:** Add `Hide layout components` patch ([#6365](https://github.com/ReVanced/revanced-patches/issues/6365)) ([71ce823](https://github.com/ReVanced/revanced-patches/commit/71ce8230a959dcaf2d8cd5dad1a4f21b88819aa0))
* **YouTube Music:** Add `Unlock Android Auto Media Browser` patch ([#6477](https://github.com/ReVanced/revanced-patches/issues/6477)) ([5edd9dc](https://github.com/ReVanced/revanced-patches/commit/5edd9dccae3b1ab4edf19771a771812e3c9ccf80))

</details>

# MorpheApp/MicroG-RE

***Release Version: [6.1.1](https://github.com/MorpheApp/MicroG-RE/releases/tag/6.1.1)***  
***Release Date: February 14, 2026, 15:04:45 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

### Bug Fixes

- Resolve login errors (627f49218560157222c1c9b5eeb2844374f955ba)

**Full Changelog**: https://github.com/MorpheApp/MicroG-RE/compare/6.1.0...v6.1.1</details>

# IMXEren/mix-patches

***Release Version: [v1.0.0](https://github.com/IMXEren/mix-patches/releases/tag/v1.0.0)***  
***Release Date: January 18, 2026, 23:57:07 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

# 1.0.0 (2026-01-18)


### Features

* **trakt:** add Unlock pro patch ([64af918](https://github.com/IMXEren/mix-patches/commit/64af918d36c364fe7f71c77d8170d1ded67afc97))



</details>

# inotia00/revanced-patches

***Release Version: [v5.14.1](https://github.com/inotia00/revanced-patches/releases/tag/v5.14.1)***  
***Release Date: December 31, 2025, 03:18:29 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

YouTube
==
- chore(YouTube): Improve fingerprint compatibility
- feat(YouTube - Hide comments components): Add `Hide information button` setting
- feat(YouTube - Hide description components): Add `Hide Featured links section` and `Hide Featured videos section` [#167](https://github.com/inotia00/revanced-patches/pull/167)
- feat(YouTube - Hide feed components): Add `Hide Join button` and `Hide Subscribe button` in channel page [#170](https://github.com/inotia00/revanced-patches/pull/170)
- feat(YouTube - Navigation bar components): Add `Replace navigation button` setting
- feat(YouTube - Shorts components): Add `Hide Auto-dubbed label`, `Hide live preview` and `Hide preview comment` [#169](https://github.com/inotia00/revanced-patches/pull/169)
- feat(YouTube - Spoof app version): Add target version `20.13.41 - Restore non collapsed video action bar`
- feat(YouTube - Spoof streaming data): Change the default value of `Show reload video button` to OFF
- feat(YouTube - Toolbar components): Add `Hide Search button` setting
- fix(YouTube - AuthUtils): Sometimes the Auth token is not updated
- fix(YouTube - Hide ads): YouTube Doodles are unclickable when `Hide general ads` is turned on [ReVanced_Extended#3298](https://github.com/inotia00/ReVanced_Extended/issues/3298)
- fix(YouTube - Hide ads): `Hide YouTube Premium promotion` setting does not hide some elements [#3298 (comment)](https://github.com/inotia00/ReVanced_Extended/issues/3298#issuecomment-3633262097)
- fix(YouTube - Hide ads): `Hide general ads` does not hide some banners (Needs testing)
- fix(YouTube - Hide feed components): `Hide category bar in related videos` breaks the fullscreen player UI (A/B tests) [ReVanced/revanced-patches#6298](https://github.com/ReVanced/revanced-patches/issues/6298)
- fix(YouTube - Hide layout components): Fix side effect of `Disable translucent status bar`
- fix(YouTube - Navigation bar components): Sometimes context is null
- fix(YouTube - Navigation bar components): `Swap Create and Notifications buttons` setting hides Shorts ads
- fix(YouTube - Overlay buttons): Chapters fade when set wider overlay buttons [#168](https://github.com/inotia00/revanced-patches/pull/168)
- fix(YouTube - Player components): App may crash on YouTube 20+
- fix(YouTube - Set Transcript Cookies): Embedded player does not start playing with `No Auth`
- fix(YouTube - Shorts components): Sometimes context is null
- fix(YouTube - Spoof streaming data): Age-restricted videos do not play in the `Android No SDK` client
- fix(YouTube - Spoof streaming data): Update side effects


YouTube Music
==
- feat(YouTube Music): Add `Spoof app version for lyrics` patch
- feat(YouTube Music): Remove `Spoof app version` patch
- feat(YouTube Music - Flyout menu components): Add `Hide Taste match menu` setting
- feat(YouTube Music - Flyout menu components): Combine `Hide Save episode for later menu` and `Hide Save to library menu` into `Hide Save episode for later and Save to library menus`
- feat(YouTube Music - Hide action bar components): Add `Replace like button` setting
- feat(YouTube Music - Player components): Add `Hide information button` setting
- feat(YouTube Music - Player components): Add patch option `Swipe to dismiss miniplayer` [ReVanced_Extended#3327](https://github.com/inotia00/ReVanced_Extended/issues/3327)
- feat(YouTube Music - Spoof streaming data): Add `Android Music No SDK` client
- feat(YouTube Music - Spoof streaming data): Add `Sign in to Android No SDK` setting
- feat(YouTube Music - Spoof streaming data): Change default client to `Android Music No SDK`
- fix(YouTube Music): Fix crashes on Android 5-6 [#175](https://github.com/inotia00/revanced-patches/pull/175)
- fix(YouTube Music - Hide ads): Home feed does not load when `Hide fullscreen ads` setting is enabled
- fix(YouTube Music - Hide ads): `Hide promotion alert banner` setting does not hide some banners
- fix(YouTube Music - Navigation bar components): `Hide Library button` does not work in YouTube Music 8.24+
- fix(YouTube Music - Player components): Fix side effect of `Enable smooth transition animation`


Reddit
==
- fix(Reddit): No notifications on patched app [ReVanced_Extended#3303](https://github.com/inotia00/ReVanced_Extended/issues/3303)


Shared
==
- chore(WebViewHostActivity): Always include `Referer` in the header
- docs: Add link badges to README-template.md [#166](https://github.com/inotia00/revanced-patches/pull/166)
- docs: Include logo in README.md [#171](https://github.com/inotia00/revanced-patches/pull/166)
- feat(Spoof streaming data): Change default client to `Android No SDK`
- feat(Spoof streaming data): Remove `iPad OS` client which no longer works
- feat(Spoof streaming data): Remove all code related to PoToken
- feat(Spoof streaming data): Rename `About Android VR Auth` to `Sign in to Android VR` and remove the `Android VR Auth` client (Integrated into `Android VR`)
- feat(Universal): Add `Change installer package name` patch
- fix(Disable forced auto audio tracks): Code was added repeatedly
- fix(Spoof streaming data): Change the recommended JavaScript client to `TV Simply`
- fix(Spoof streaming data): J2V8 native library (4KB page size) causes performance degradation on Android 16 devices (Requires [Cli 5.0.2](https://github.com/inotia00/revanced-cli/releases/tag/v5.0.2) or [Manager 1.25.7](https://github.com/inotia00/revanced-manager/releases/tag/v1.25.7))
- fix(Spoof streaming data): V8 runtime shuts down every time deobfuscation is finished
- fix(Spoof streaming data): `Android VR` or `Android No SDK` access tokens sometimes do not refresh


Announcement
==
- **Final release before EOL. This sentence will be updated once [README.md is finished](https://github.com/inotia00/revanced-patches/pull/174).**
- Thanks to the [Aurora OSS Team](https://auroraoss.com/) for providing a lot of references for implementing YouTube sign in logic.
- Troubleshooting playback issues on YouTube and YouTube Music: [Community-Guides](https://github.com/ReVanced-Extended-Community/Community-Guides/blob/main/news/playback-issues-announcement.md) [Issue Center](https://github.com/inotia00/ReVanced_Extended/issues/3181).
- Currently Reddit 2025.40.0+ can only be patched via CLI or rvx-builder: [Announcement](https://github.com/inotia00/ReVanced_Extended/issues/3288) [Documentation](https://github.com/inotia00/revanced-documentation/blob/main/docs/latest-reddit-patch-info.md).
- Compatible ReVanced Manager: [RVX Manager v1.25.7 (fork)](https://github.com/inotia00/revanced-manager/releases/tag/v1.25.7).


Contribute to translation
==
- [YouTube](https://crowdin.com/project/revancedextended)
- [YT Music](https://crowdin.com/project/revancedmusicextended)
- **These Crowdin projects will be closed or deactivated after January 2026.**</details>

# inotia00/revanced-cli

***Release Version: [v5.0.2](https://github.com/inotia00/revanced-cli/releases/tag/v5.0.2)***  
***Release Date: December 29, 2025, 08:40:00 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

- fix: Align native libraries of patched apps to 16kb instead of 4kb by bumping dependencies

> [!Note]
> Based on ReVanced Cli [5.0.1](https://github.com/ReVanced/revanced-cli/tree/v5.0.1).
> Added some commands required by rvx-builder:
> - Added option command `options` (`options.json` file generator)
> - Added option command `patches` (`patches.json` file generator)
> - Added option command `--legacy-options` (Set patch option via `options.json` file)
> - Added option command `--rip-libs` (Remove native libs from apk)
> - Added option command `--unsigned` (Disable signing of the final apk, regardless of whether it is mounted or not)
> - Added support anti-split (Merged some [REAndroid/ARSCLib](https://github.com/REAndroid/ARSCLib) sources to implement anti-split)
</details>

# REAndroid/APKEditor

***Release Version: [V1.4.7](https://github.com/REAndroid/APKEditor/releases/tag/V1.4.7)***  
***Release Date: December 28, 2025, 11:00:45 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

## What's Changed
* Set smali comment level to `basic` (For faster smali deompiling):https://github.com/REAndroid/APKEditor/commit/a5390a3401153ab9ac38b4487a279316eee7400d
* Fix: Protector - dictionaries options by @Kirlif in https://github.com/REAndroid/APKEditor/pull/218


**Full Changelog**: https://github.com/REAndroid/APKEditor/compare/V1.4.6...V1.4.7</details>

# ReVanced/revanced-cli

***Release Version: [v5.0.1](https://github.com/ReVanced/revanced-cli/releases/tag/v5.0.1)***  
***Release Date: April 14, 2025, 08:53:52 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

## [5.0.1](https://github.com/ReVanced/revanced-cli/compare/v5.0.0...v5.0.1) (2025-04-14)


### Bug Fixes

* Make mounting work again by bumping dependencies ([#359](https://github.com/ReVanced/revanced-cli/issues/359)) ([68a4872](https://github.com/ReVanced/revanced-cli/commit/68a48724ebf01a0c8f8adc0fec63037bff672dc9))



</details>

