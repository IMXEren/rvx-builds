# crimera/piko

***Release Version: [v1.34.1](https://github.com/crimera/piko/releases/tag/v1.34.1)***  
***Release Date: August 06, 2024, 11:18:33 UTC***  
***Changelog:***

## [1.34.1](https://github.com/crimera/piko/compare/v1.34.0...v1.34.1) (2024-08-06)

### Bug Fixes

* **Twitter:** Fix aapt breakage due to tag mismatch ([730a51c](https://github.com/crimera/piko/commit/730a51c20f464bbe2b680004721161dd5f34dadf))


# inotia00/revanced-patches

***Release Version: [v4.12.1](https://github.com/inotia00/revanced-patches/releases/tag/v4.12.1)***  
***Release Date: August 07, 2024, 17:13:11 UTC***  
***Changelog:***

YouTube
==
- feat(YouTube): add `Hook download actions` patch https://github.com/inotia00/revanced-patches/pull/70
- feat(YouTube/Client spoof): update hardcoded client version
- feat(YouTube/Shorts components): move `Change Shorts repeat state` setting to `Experimental Flags` (close https://github.com/inotia00/ReVanced_Extended/issues/2231, https://github.com/inotia00/ReVanced_Extended/issues/2295)
- fix(YouTube/Hide comments components): `Hide Comments section in home feed` setting not working in new component name
- fix(YouTube/Hide feed components): sometimes `Hide carousel shelf` setting doesn't work
- fix(YouTube/Hide layout components): no longer hiding `Settings` https://github.com/inotia00/ReVanced_Extended/issues/1424
- fix(YouTube/Hook download actions): `Override playlist download button` setting does not work in `Download playlist` menu of flyout panel
- fix(YouTube/Overlay buttons): `Always repeat` button doesn't work when the video is minimized https://github.com/inotia00/ReVanced_Extended/issues/2293
- fix(YouTube/Return YouTube Dislike): dislikes not appearing due to new component name
- fix(YouTube/SponsorBlock): improve create segment manual seek accuracy https://github.com/ReVanced/revanced-patches/pull/3491
- fix(YouTube/Spoof client): change default value
- fix(YouTube/Spoof client): fix background playback issue with livestream on iOS clients https://github.com/inotia00/ReVanced_Extended/issues/2290
- fix(YouTube/Spoof client): partial fix for watch history issue of brand accounts on iOS clients https://github.com/inotia00/ReVanced_Extended/issues/2297
- chore(YouTube): clarity of in-app strings https://github.com/inotia00/revanced-patches/pull/69
- feat(YouTube/Translations for YouTube): update translation


YouTube Music
==
- feat(YouTube Music): add support versions `7.12.52` ~ `7.13.52`
- feat(YouTube Music): add `Change share sheet` patch https://github.com/inotia00/ReVanced_Extended/issues/1983
- feat(YouTube Music/Player components): add settings `Disable miniplayer gesture`, `Disable player gesture` https://github.com/inotia00/ReVanced_Extended/issues/2097
- fix(YouTube Music/Hide account components): no longer hiding `Settings` https://github.com/inotia00/ReVanced_Extended/issues/1424
- feat(YouTube Music/Translations for YouTube Music): update translation


Announcement
==
- Reddit 2024.18.0+ can only be patched via [CLI](https://github.com/inotia00/revanced-documentation/blob/main/docs/latest-reddit-patch-info.md) or rvx-builder.
- Compatible ReVanced Manager: [RVX Manager v1.21.1 (fork)](https://github.com/inotia00/revanced-manager/releases/tag/v1.21.1).


Contribute to translation
==
- [YouTube](https://crowdin.com/project/revancedextended)
- [YT Music](https://crowdin.com/project/revancedmusicextended)

# ReVanced/revanced-patches

***Release Version: [v4.12.0](https://github.com/ReVanced/revanced-patches/releases/tag/v4.12.0)***  
***Release Date: August 06, 2024, 00:08:59 UTC***  
***Changelog:***

# [4.12.0](https://github.com/ReVanced/revanced-patches/compare/v4.11.0...v4.12.0) (2024-08-06)


### Bug Fixes

* **Instagram - Hide ads:**  Restore compatibility with latest version by fixing fingerprint ([#3455](https://github.com/ReVanced/revanced-patches/issues/3455)) ([4505fa4](https://github.com/ReVanced/revanced-patches/commit/4505fa4138bb55c8957790239c01b8dda63d6cdd))
* **Messenger - Disable switching emoji to sticker:** Constrain to last working version `439.0.0.29.119` ([6207c31](https://github.com/ReVanced/revanced-patches/commit/6207c314c657a1188d1081b0a196a61e49cad83b))
* **YouTube - Hide keyword content:** Do not hide flyout menu ([687c9f7](https://github.com/ReVanced/revanced-patches/commit/687c9f7eb03cca5f7b3486f07f2e3453ebc77faf))
* **YouTube - SponsorBlock:** Correctly show minute timestamp when creating a new segment ([d74c366](https://github.com/ReVanced/revanced-patches/commit/d74c366dbf5f25c20fbfc5a0157c3c15dda82a16))
* **YouTube - SponsorBlock:** Improve create segment manual seek accuracy ([#3491](https://github.com/ReVanced/revanced-patches/issues/3491)) ([1544981](https://github.com/ReVanced/revanced-patches/commit/15449819ff74b636fb2fa6aacd770142c51d2e5d))
* **YouTube - Spoof client:** Restore missing high qualities by spoofing the iOS client user agent ([#3468](https://github.com/ReVanced/revanced-patches/issues/3468)) ([0e6ae5f](https://github.com/ReVanced/revanced-patches/commit/0e6ae5fee752a76604cf9b95f9a76c0cbe5f7dae))
* **YouTube - Spoof client:** Restore livestream audio only playback with iOS spoofing ([#3504](https://github.com/ReVanced/revanced-patches/issues/3504)) ([90d3288](https://github.com/ReVanced/revanced-patches/commit/90d32880906787d82c4b9a7a1099b46dff3a0870))


### Features

* Add `Hide mock location` patch ([#3417](https://github.com/ReVanced/revanced-patches/issues/3417)) ([5f81b40](https://github.com/ReVanced/revanced-patches/commit/5f81b40e7d5567fb5689d08ccc9caeaa267c3143))
* Add `Spoof build info` patch ([e7829b4](https://github.com/ReVanced/revanced-patches/commit/e7829b41e782c9feda23b9d6acf48bae277d24d9))
* **Boost for Reddit:** Add `Disable ads` patch ([#3474](https://github.com/ReVanced/revanced-patches/issues/3474)) ([b292c20](https://github.com/ReVanced/revanced-patches/commit/b292c200bf4ea5b4f71d96690ac011e7843552f0))
* **CandyLink:** Remove non-functional `Unlock pro` patch ([7ae9f8f](https://github.com/ReVanced/revanced-patches/commit/7ae9f8fa0a349b91853e9554f18e564ca6ff887c))
* **Expense Manager:** Remove non-functional `Unlock pro` patch ([ebbcac7](https://github.com/ReVanced/revanced-patches/commit/ebbcac74fd8598daebb4be0bd7c430c41333e2d4))
* **Google News:** Add `Enable CustomTabs` and `GmsCore support` patch ([#3111](https://github.com/ReVanced/revanced-patches/issues/3111)) ([ad59096](https://github.com/ReVanced/revanced-patches/commit/ad590962275f888b335252ad5bed0f34e959d3c7))
* **Google Photos:** Add `GmsCore support` patch ([#3414](https://github.com/ReVanced/revanced-patches/issues/3414)) ([24528e0](https://github.com/ReVanced/revanced-patches/commit/24528e0a6eec17ce0a3c52f8862585933615ad28))
* **Instagram:** Remove unnecessary `Hide timeline ads` patch ([5e1d001](https://github.com/ReVanced/revanced-patches/commit/5e1d001056df68e1e2b39f1365215c91bcc9e46b))
* **SoundCloud:** Add `Enable offline sync` patch ([#3407](https://github.com/ReVanced/revanced-patches/issues/3407)) ([4de86c6](https://github.com/ReVanced/revanced-patches/commit/4de86c6407376bcd3cc0513a2f0707410b8d7ccd))
* **SwissID:** Add `Remove Google Play Integrity Integrity check` patch ([#3478](https://github.com/ReVanced/revanced-patches/issues/3478)) ([60492ae](https://github.com/ReVanced/revanced-patches/commit/60492aea7863e07d8bf1af9380ae9295ca161f3c))
* **YouTube - Description components:** Add `Hide 'Key concepts' section` option ([#3495](https://github.com/ReVanced/revanced-patches/issues/3495)) ([d75b645](https://github.com/ReVanced/revanced-patches/commit/d75b64595a7ac26faca4c0ae21923b22f6783975))
* **YouTube:** Add `Bypass image region restrictions` patch ([#3442](https://github.com/ReVanced/revanced-patches/issues/3442)) ([765fab2](https://github.com/ReVanced/revanced-patches/commit/765fab2af2769349446cc0f2109343ef3bd8c621))





