# inotia00/revanced-patches

***Release Version: [v4.9.2](https://github.com/inotia00/revanced-patches/releases/tag/v4.9.2)***  
***Release Date: June 23, 2024, 11:51:22 UTC***  
***Changelog:***

YouTube
==
- feat(YouTube): add support version `19.23.40`, drop support version `19.20.35`, `19.21.40`
- feat(YouTube/Description components): separate the `Hide Key concepts section` setting from the `Hide Chapters section` setting https://github.com/inotia00/ReVanced_Extended/issues/2102
- feat(YouTube/Miniplayer): add `Enable drag and drop` setting (YouTube 19.23.40+)
- feat(YouTube/Navigation bar components): add `Enable translucent navigation bar` settings (YouTube 19.23.40+, Android 12+) https://github.com/inotia00/ReVanced_Extended/issues/2177
- feat(YouTube/Seekbar components): add `Enable Cairo seekbar` settings (YouTube 19.23.40+) https://github.com/inotia00/ReVanced_Extended/issues/2178
- feat(YouTube/Settings): Remove quotations from proper nouns https://github.com/inotia00/revanced-patches/pull/56
- fix(YouTube): `Hide animated button background` patch doesnt work https://github.com/inotia00/ReVanced_Extended/issues/2179
- fix(YouTube/GmsCore support): spoof package name https://github.com/inotia00/revanced-patches/pull/57
- fix(YouTube/Hide action buttons) : empty space is left after hiding all action buttons under videos https://github.com/inotia00/ReVanced_Extended/issues/2180
- fix(YouTube/Hide ads): app crashes in the old client https://github.com/inotia00/ReVanced_Extended/issues/2146
- fix(YouTube/Hide feed components): `Hide carousel shelf` setting does not work (A/B tests) https://github.com/inotia00/ReVanced_Extended/issues/2172
- fix(YouTube/Hide feed components): `Hide comments by keywords` setting hides unintended layout
- fix(YouTube/Hide feed components): `Hide expandable chip under videos` setting does not work (A/B tests) https://github.com/inotia00/ReVanced_Extended/issues/2173
- fix(YouTube/Hide feed components): `Keyword filter`, `Hide low views video`, `Hide recommended videos by views` setting does not work (A/B tests)
- fix(YouTube/Hide feed components): community posts are not hidden https://github.com/inotia00/ReVanced_Extended/issues/2074
- fix(YouTube/Miniplayer): `Hide expand and close buttons` setting is not disabled in `Modern 1` on YouTube 19.20.35+
- fix(YouTube/Overlay buttons): in devices that do not use `xxhdpi`, some buttons are not replaced correctly
- fix(YouTube/Player components): `Hide Open mix playlist button` and `Hide Open playlist button` aren't working https://github.com/inotia00/ReVanced_Extended/issues/2174
- fix(YouTube/Spoof client): change default value to ON
- fix(YouTube/Spoof client): seekbar thumbnail not shown in `Android Testsuite` client
- fix(YouTube/Spoof client): update side-effects https://github.com/inotia00/ReVanced_Extended/issues/2166
- fix(YouTube/Toolbar components): add support for Cairo icon
- feat(YouTube/Translations): update translation


YouTube Music
==
- feat(YouTube Music): add support versions `7.05.54` ~ `7.06.53`
- feat(YouTube Music): add `Enable Cairo splash animation` patch (YouTube Music 7.06.53+)
- fix(YouTube Music): app crashes at old client https://github.com/inotia00/ReVanced_Extended/issues/2168
- fix(YouTube Music/Custom header for YouTube Music): patch not applied to some users (due to A/B testing)
- feat(YouTube Music/Translations): update translation


Reddit
==
- feat(Reddit): add `Change version code` patch
- feat(Reddit): add `Hide recommended communities shelf` patch https://github.com/inotia00/ReVanced_Extended/issues/2114
- fix(Reddit/Settings): patch option `RVX settings menu name` does not apply to header in ReVanced Extended settings


Announcement
==
- There is a change in `options.json`. If you see warnings related to patch options, remove the `options.json` file or `Patch options`.
- `Restore old seekbar thumbnails` setting has been deprecated in `YouTube v19.17.41+`.
- If you want to use the `Restore old seekbar thumbnails` setting, just patch `YouTube v18.29.38 ~ v19.16.39`.
- Reddit 2024.18.0+ can only be patched via [CLI](https://github.com/inotia00/revanced-documentation/blob/main/docs/latest-reddit-patch-info.md).
- Compatible ReVanced Manager: [RVX Manager v1.20.4 (fork)](https://github.com/inotia00/revanced-manager/releases/tag/v1.20.4), [RVX Manager v1.18.1 (fork)](https://github.com/inotia00/revanced-manager/releases/tag/v1.18.1)


Contribute to translation
==
- [YouTube](https://crowdin.com/project/revancedextended)
- [YT Music](https://crowdin.com/project/revancedmusicextended)

# ReVanced/revanced-patches

***Release Version: [v4.10.0](https://github.com/ReVanced/revanced-patches/releases/tag/v4.10.0)***  
***Release Date: June 23, 2024, 12:14:46 UTC***  
***Changelog:***

# [4.10.0](https://github.com/ReVanced/revanced-patches/compare/v4.9.0...v4.10.0) (2024-06-23)


### Bug Fixes

* **YouTube - Client spoof:** Correctly play more livestreams using Android VR ([#3316](https://github.com/ReVanced/revanced-patches/issues/3316)) ([c05264a](https://github.com/ReVanced/revanced-patches/commit/c05264af3944cbfe8d9aa34fb0e0fddb05a1d42f))
* **YouTube - Hide description components:** Replace `Hide game section` and `Hide music section` with `Hide attributes section` ([#3327](https://github.com/ReVanced/revanced-patches/issues/3327)) ([0198a43](https://github.com/ReVanced/revanced-patches/commit/0198a436f97b127a2a5dd283644254f9a0ae3e43))
* **YouTube Music:** Rename `Minimized playback` to `Remove background playback restrictions` ([#3315](https://github.com/ReVanced/revanced-patches/issues/3315)) ([3c31e55](https://github.com/ReVanced/revanced-patches/commit/3c31e55b13d9495e857f068f8cd2b4320112d763))
* **YouTube:** Rename `Minimized playback` to `Remove background playback restrictions` ([#3314](https://github.com/ReVanced/revanced-patches/issues/3314)) ([37d415b](https://github.com/ReVanced/revanced-patches/commit/37d415b53af4771d9c97a8b1c153be32bf3ac2e0))


### Features

* Add `Change version code` patch ([#3338](https://github.com/ReVanced/revanced-patches/issues/3338)) ([685ef39](https://github.com/ReVanced/revanced-patches/commit/685ef39119daf1033a83262982519531c481c40f))
* **Boost For Reddit:** Add `Fix /s/ links` patch ([#3154](https://github.com/ReVanced/revanced-patches/issues/3154)) ([5fa9fd2](https://github.com/ReVanced/revanced-patches/commit/5fa9fd2dfef43838d7311a967a3e805256a5d116))
* **Boost for Reddit:** Add `Fix audio missing in video downloads` patch ([#3287](https://github.com/ReVanced/revanced-patches/issues/3287)) ([a9258d4](https://github.com/ReVanced/revanced-patches/commit/a9258d48d3ddf8552ab56219677a3b31ee553666))
* **YouTube - Comments:** Add `Hide 'Create a Short' button` option ([#3333](https://github.com/ReVanced/revanced-patches/issues/3333)) ([be9e244](https://github.com/ReVanced/revanced-patches/commit/be9e24420fda80903e44e2e2278ea4904ecac4e1))
* **YouTube - Comments:** Add `Hide Thanks button` and `Hide 'Comments by members' header` options ([#3317](https://github.com/ReVanced/revanced-patches/issues/3317)) ([9c4c4f0](https://github.com/ReVanced/revanced-patches/commit/9c4c4f05a762d745404101bbc3925ab4eba2deb8))
* **YouTube - Miniplayer:** Rename `Tablet mini player` and allow selecting the style of the in-app miniplayer ([#3302](https://github.com/ReVanced/revanced-patches/issues/3302)) ([5511736](https://github.com/ReVanced/revanced-patches/commit/5511736b0c5dd409db6a68db0f85e389bb95be47))





