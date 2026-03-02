### APKs, Keystores and Options files go here.

#### Please follow [this guide](https://docs.google.com/document/u/0/d/1wHvqQwCYdJrQg4BKlGIVDLksPN0KpOnJWniT6PbZSrI/mobilebasic) to obtain your own client-id for patching the various Reddit clients. I recommend getting one from a burner account if you're going to store it in a location public access.

#### Note that the data set in `options.json` is a mixed form from different patch sources like ReVanced, ReVanced Extended etc. For individual `options.json` of the patch sources, this can slightly [help](/README.md#patching) in that process.

### Device Specification

Based on the spec [`device-spec.json`](./device-spec.json) provided, it only includes necessary archs and screen density (dpi) from the split apk archives before merging and then passing to the cli, resulting in relatively low-sized apks. Though, this would make the apk sometimes specific for your device (may not work for others). To enable, use `REPACK_SPLIT_APKS=True`.

To find the specification, use device info apps like App Manager (*Settings -> About the device -> CPU, Screen*), etc.
