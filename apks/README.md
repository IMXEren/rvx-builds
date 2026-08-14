### APKs, Keystores and Options files go here.

#### Please follow [this guide](https://docs.google.com/document/u/0/d/1wHvqQwCYdJrQg4BKlGIVDLksPN0KpOnJWniT6PbZSrI/mobilebasic) to obtain your own client-id for patching the various Reddit clients. I recommend getting one from a burner account if you're going to store it in a location public access.

#### Note that the data set in `options.yml` is a mixed form from different patch sources like ReVanced, ReVanced Extended etc. For individual `options.yml` of the patch sources, this can slightly [help](/README.md#patching) in that process.

### Secret Values in Options

For setting sensitive values/secrets in your options, you should prefer adding them as a key-value pair to GitHub secrets (prefixed by `SECRET_`) and then referencing the key as the value. When setting them to GitHub secrets, run the workflow _Sync Secrets to Reusable Workflow_ ([sync-secrets.yml](../.github/workflows/sync-secrets.yml)).

For example: In case of reddit client-id required by 3rd party clients.

```ini
# GitHub Secrets
SECRET_REDDIT_CLIENT_ID=some-secret

## OR

# .env
REDDIT_CLIENT_ID=some-secret
```

```yml
## options.yml
## Value-key prefixed by '$__' and suffixed by '__'
Spoof client:
  "OAuth client ID": "$__REDDIT_CLIENT_ID__"
```

### Device Specification

Based on the spec [`device-spec.json`](./device-spec.json) provided, it only includes necessary archs and screen density (dpi) from the split apk archives before merging and then passing to the cli, resulting in relatively low-sized apks. Though, this would make the apk sometimes specific for your device (may not work for others). To enable, use `REPACK_SPLIT_APKS=True`.

To find the specification, use device info apps like App Manager (_Settings -> About the device -> CPU, Screen_), etc.

### APKEEP Google Play Device Profile

A custom APKEEP device properties file, such as one exported from Aurora Store's spoof manager, can also be placed in this directory. Reference it from `.env` with its repository-relative path:

```ini
APKEEP_DEVICE_FILE=apks/device.properties
```

Use an app-prefixed variable to select a different profile for one app:

```ini
YOUTUBE_APKEEP_DEVICE_FILE=apks/youtube-device.properties
```

Built-in profiles can instead be selected with `APKEEP_DEVICE_NAME` or its app-prefixed equivalent. See the [APKEEP device configuration documentation](../auto/docs/customize-patches.md#apkeep-device-configuration) and [upstream APKEEP guide](https://github.com/EFForg/apkeep/blob/master/USAGE-google-play.md#device-configuration) for available settings and profile details.
