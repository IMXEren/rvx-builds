# MorpheApp/morphe-patches

***Release Version: [v2.4.0-dev.7](https://github.com/MorpheApp/morphe-patches/releases/tag/v2.4.0-dev.7)***  
***Release Date: November 21, 2026, 16:17:40 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

## [2.4.0-dev.7](https://github.com/MorpheApp/morphe-patches/compare/v2.4.0-dev.6...v2.4.0-dev.7) (2026-11-21)

### ✨ New Features

* **Reddit - Hide post buttons:** "Hide Award button" also hides the Award button of comments ([c02951a](https://github.com/MorpheApp/morphe-patches/commit/c02951aa39fabb9348136fdf2bb2278322bee42d))
* **YouTube  Music:** Add `Apple Music animated artwork` patch ([#5082](https://github.com/MorpheApp/morphe-patches/issues/5082)) ([a48adbe](https://github.com/MorpheApp/morphe-patches/commit/a48adbee3a9c6a23a62a0e489da2e227487d245a))
* **YouTube - Hide layout components:** Add "Hide Badges", "Hide 'Liked videos'" and "Hide 'Watch later'" settings for the You tab ([a671788](https://github.com/MorpheApp/morphe-patches/commit/a67178893b2ac0206ea431074b14c0a021e3b40c))
* **YouTube - Hide layout components:** Add "Hide Topics" setting ([#5097](https://github.com/MorpheApp/morphe-patches/issues/5097)) ([e0fb5e3](https://github.com/MorpheApp/morphe-patches/commit/e0fb5e3e5357472aa3d2551227984c0d30542b23))
* **YouTube Music:** Add `Sonos Cast` patch ([#4891](https://github.com/MorpheApp/morphe-patches/issues/4891)) ([b760507](https://github.com/MorpheApp/morphe-patches/commit/b7605075b80556fa242ec8a109e2375a526db9b6))
* **YouTube:** Add `Glass menus` patch ([#5107](https://github.com/MorpheApp/morphe-patches/issues/5107)) ([ed52a0d](https://github.com/MorpheApp/morphe-patches/commit/ed52a0ddae97c80e5c824d14cd2f45c457f126d0))
* **YouTube:** Add `Hold gesture` patch ([#5099](https://github.com/MorpheApp/morphe-patches/issues/5099)) ([0e899ed](https://github.com/MorpheApp/morphe-patches/commit/0e899ed4940bb8ec8e51960a77b847e7180f5a32))

### 🐛 Bug Fixes

* **YouTube - Add to queue:** Handle Play next in queue on playlist pages for native queue ([#5088](https://github.com/MorpheApp/morphe-patches/issues/5088)) ([033d4b5](https://github.com/MorpheApp/morphe-patches/commit/033d4b56de1aa5663299a2e982850a12c938d36b))
* **YouTube - DeArrow:** Thumbnails that failed to load are not loaded again when the connection comes back while the app is in the background ([b9a8094](https://github.com/MorpheApp/morphe-patches/commit/b9a8094fb0405684030af7cef9d0a91cb14eaeb5))
* **YouTube - Hide layout components:** Hide new type of community posts ([7ce7538](https://github.com/MorpheApp/morphe-patches/commit/7ce7538b83e36fb2c8a2ce774d949ca5ae9d14a9))
* **YouTube - Hide layout components:** Keyword filter does not hide videos with fancy text titles ([5f5609b](https://github.com/MorpheApp/morphe-patches/commit/5f5609b8730f3b25380abdcb17beb1686196f59c))
* **YouTube - Litho filter:** Elements that the element hooks hide, such as the YouTube Premium promotions, leave empty cells in the tablet feed ([#5012](https://github.com/MorpheApp/morphe-patches/issues/5012)) ([358afd0](https://github.com/MorpheApp/morphe-patches/commit/358afd0ac6c8fb9a506362ce6edfaa7aecc43d98))
* **YouTube - Navigation bar:** Navigation bar does not auto-hide while scrolling on accounts whose app controllers never hide it ([#4432](https://github.com/MorpheApp/morphe-patches/issues/4432)) ([e1a0248](https://github.com/MorpheApp/morphe-patches/commit/e1a024896c4427b737aa96e339b5cebe542ec7ac))
* **YouTube - Navigation bar:** Navigation bar does not auto-hide while scrolling on accounts whose feed pages do not enable it ([#4432](https://github.com/MorpheApp/morphe-patches/issues/4432)) ([dfb784e](https://github.com/MorpheApp/morphe-patches/commit/dfb784e4d96134cf4665e8a5d08676da0b699fe5))
* **YouTube - Player controls:** Old player buttons show over the overlay buttons on 21.47 ([040df43](https://github.com/MorpheApp/morphe-patches/commit/040df439743657500b649211f3823ac9a9260af9))
* **YouTube - Restore old video action bar:** "Classic One-Row" shows two rows and comments do not load GIFs on 20.26 ([#5068](https://github.com/MorpheApp/morphe-patches/issues/5068)) ([5007b0a](https://github.com/MorpheApp/morphe-patches/commit/5007b0a24200b3c529c9a2b33fd682500e81e1d2))
* **YouTube - Restore original titles:** Title of the previous video is shown when the next video of a playlist plays before its video ID is known ([a1a2dc8](https://github.com/MorpheApp/morphe-patches/commit/a1a2dc8213a2748398614131058f0f72330cd287))
* **YouTube - Restore original titles:** Titles stay loading or are not restored after the app is opened again from the background ([3863119](https://github.com/MorpheApp/morphe-patches/commit/3863119f6db1c8e1a25aee103864007fe3f5dc29))
* **YouTube - Return YouTube Dislike:** Feed thumbnail like count of a grid of Shorts is shown below the thumbnail, and twice on the left Short, when a Short at the right has a channel name in capital letters ([#5070](https://github.com/MorpheApp/morphe-patches/issues/5070)) ([6896cbe](https://github.com/MorpheApp/morphe-patches/commit/6896cbe49a38db68a4b8475825beba0c03361aa6))
* **YouTube Music - Change start page:** Subscriptions start page is sometimes blank on `9.26+` ([0c5353a](https://github.com/MorpheApp/morphe-patches/commit/0c5353a00274930faa794e2ba9b4ac98f1b57eb8))
* **YouTube Music - Glass miniplayer:** Miniplayer missing album artwork ([#5117](https://github.com/MorpheApp/morphe-patches/issues/5117)) ([6af6775](https://github.com/MorpheApp/morphe-patches/commit/6af6775c75b0ff785e5f8030bb90aa1d06fc9684))
* **YouTube Music - Navigation bar:** "Hide 'Ask Music' button" does not hide the button in the player, miniplayer and fullscreen ([#5120](https://github.com/MorpheApp/morphe-patches/issues/5120)) ([9ae8dd6](https://github.com/MorpheApp/morphe-patches/commit/9ae8dd69a55f5dcf40c79ac377987a24fac80ddd))
* **YouTube Music - Remember video quality:** Default quality is used about 10 seconds after a track starts ([#5109](https://github.com/MorpheApp/morphe-patches/issues/5109)) ([7531b56](https://github.com/MorpheApp/morphe-patches/commit/7531b56ae8e4fc76789b05010a396c5af2f2d252))
* **YouTube Music - Remember video quality:** Videos with only low quality VP9 play at 360p with no quality menu ([#5108](https://github.com/MorpheApp/morphe-patches/issues/5108)) ([ac829a2](https://github.com/MorpheApp/morphe-patches/commit/ac829a2fe76a6389c3ff422a917d900a6b2c4b2c))
* **YouTube:** Feed stutters while scrolling, as the element hooks run twice for each loaded element ([#5096](https://github.com/MorpheApp/morphe-patches/issues/5096)) ([6db505e](https://github.com/MorpheApp/morphe-patches/commit/6db505e22f9d9ff4ac9c622500f027a4d1e193d0))
* **YouTube:** Feed stutters while scrolling, as the titles and thumbnails loaded meanwhile lay out and mount again all the shown elements ([2283c7a](https://github.com/MorpheApp/morphe-patches/commit/2283c7afe16859fb263e5eea68be5f2d69a5d3e3))
* **YouTube:** Feed thumbnail badges take a text below the thumbnail for the duration badge, and are missing on the rows of a list, on screens with a high display density ([5617a08](https://github.com/MorpheApp/morphe-patches/commit/5617a08b0b438586c197162710525e03d503dfad))
* **YouTube:** Location setting changes back to the country of the device after leaving YouTube settings ([#5071](https://github.com/MorpheApp/morphe-patches/issues/5071)) ([#5080](https://github.com/MorpheApp/morphe-patches/issues/5080)) ([efff3b3](https://github.com/MorpheApp/morphe-patches/commit/efff3b32c109d92fbba9aa10740cdd9cfa139661))
* **YouTube:** Update tab selected fingerprint to match more app versions ([4c7f601](https://github.com/MorpheApp/morphe-patches/commit/4c7f601789f8c1270dcead06bb61d389538d8dd1))
* **YouTube:** Video ID is not updated when the next video of a playlist plays in the background ([c35d12c](https://github.com/MorpheApp/morphe-patches/commit/c35d12c4e732011ca9fc217a1bfedbb675f8dbfb))
</details>

# MorpheApp/morphe-desktop

***Release Version: [v2.3.0](https://github.com/MorpheApp/morphe-desktop/releases/tag/v2.3.0)***  
***Release Date: November 21, 2026, 10:19:34 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

# [2.3.0](https://github.com/MorpheApp/morphe-desktop/compare/v2.2.0...v2.3.0) (2026-11-21)


### Bug Fixes

* Show real app name without a patch bundle ([#436](https://github.com/MorpheApp/morphe-desktop/issues/436)) ([dc09eb9](https://github.com/MorpheApp/morphe-desktop/commit/dc09eb9e0f71dfa156ada236d00d1a4d60ad29c9))
* Show the Play Store icon for uninstalled apps ([#444](https://github.com/MorpheApp/morphe-desktop/issues/444)) ([84e80d2](https://github.com/MorpheApp/morphe-desktop/commit/84e80d242aa64db20cacd6852b5d75273209e0da))
* Update morphe-patcher dependency ([8c6faa2](https://github.com/MorpheApp/morphe-desktop/commit/8c6faa2db358778277c60024134c4d2f351a245d))
* Update Patcher dependency ([3e7fd0e](https://github.com/MorpheApp/morphe-desktop/commit/3e7fd0e46a0226338273afc528765b0e70a77f1d))


### Features

* Rework About into Settings subpage ([#441](https://github.com/MorpheApp/morphe-desktop/issues/441)) ([8450c6f](https://github.com/MorpheApp/morphe-desktop/commit/8450c6f76b62ad8b0483289098518a36825f1fd9))
* Rework patch sources and versions screen + Dialog Consolidation ([#433](https://github.com/MorpheApp/morphe-desktop/issues/433)) ([70be7ca](https://github.com/MorpheApp/morphe-desktop/commit/70be7ca458df9999c2b60b5982697e716604fba4))
* Rework status banners and add source update banner ([#440](https://github.com/MorpheApp/morphe-desktop/issues/440)) ([e4d111a](https://github.com/MorpheApp/morphe-desktop/commit/e4d111a89514bdcbd5e42aff32a9f2c25b777b30))
* Show app form factors in GUI and CLI ([#435](https://github.com/MorpheApp/morphe-desktop/issues/435)) ([3a41067](https://github.com/MorpheApp/morphe-desktop/commit/3a41067a67f9d30946075302cfdde5db2eb69be9))
* Show contributors and supporters in settings about screen ([#442](https://github.com/MorpheApp/morphe-desktop/issues/442)) ([7b42de6](https://github.com/MorpheApp/morphe-desktop/commit/7b42de63c5054450bc2dd771a2ed31eb3b489fbf))
</details>

# MorpheApp/MicroG-RE

***Release Version: [7.3.1](https://github.com/MorpheApp/MicroG-RE/releases/tag/7.3.1)***  
***Release Date: November 14, 2026, 08:53:06 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

## What's Changed
* docs: Add APK signing certificate fingerprint to README by @brummilab in https://github.com/MorpheApp/MicroG-RE/pull/338
* fix(maps): Insert tile overlays below annotations and handle zIndex by @Akash-Sriram in https://github.com/MorpheApp/MicroG-RE/pull/345
* fix(games): Remove live system-overlay account popup (TYPE_APPLICATION_OVERLAY) by @codeiva11 in https://github.com/MorpheApp/MicroG-RE/pull/333
* feat(phenotype): Support live Google Phenotype server sync and client IPC for modded Google apps by @Akash-Sriram in https://github.com/MorpheApp/MicroG-RE/pull/350

## New Contributors
* @brummilab made their first contribution in https://github.com/MorpheApp/MicroG-RE/pull/338
* @Akash-Sriram made their first contribution in https://github.com/MorpheApp/MicroG-RE/pull/345

**Full Changelog**: https://github.com/MorpheApp/MicroG-RE/compare/7.3.0...7.3.1</details>

# REAndroid/APKEditor

***Release Version: [V1.4.9](https://github.com/REAndroid/APKEditor/releases/tag/V1.4.9)***  
***Release Date: May 19, 2026, 11:25:01 UTC***  
<details>
<summary><b><i>Changelog:</i></b></summary>

## What's Changed
* Fix: Merging issue #228 
* Fix: Smali wide register handling #229 


**Full Changelog**: https://github.com/REAndroid/APKEditor/compare/V1.4.8...V1.4.9</details>

