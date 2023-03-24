###### 23/MAR/2023:
### Builds are now automated!
Added scheduled action that checks for patch updates, and if an update is found, it will automatically trigger the workflow to build and release the updated applications.
<hr>

### Feel free to fork this fork.
Let the 'forkception' begin!

### How to use this fork:

*Before running the workflows for the first time, you need to go the Settings page of the repository and under Actions, then General, change the "Workflow permissions" to "read and write".*

1. Go to the Actions page at the top.
2. Select the "Build & Release" action.
3. Click the "Run Workflow" drop-down button and run it.

*It will take around 13 minutes to complete the workflow.*

4. Go to "Releases" at the bottom (on mobile) or at the right (on Desktop).
5. Download your patched applications.

#### Set up to build:
* ReVanced Extended **YouTube** (supported) in the...

...**arm64-v8a** and **armeabi-v7a** architectures.
* ReVanced Extended **YouTube Music** (latest) in the...

...**arm64-v8a** architecture.

***Releases include alternative versions of both with the all the different icon options.***

###### Check [.env](https://github.com/Spacellary/docker-py-revanced/blob/main/.env) for a list of excluded patches and [options.toml](https://github.com/Spacellary/docker-py-revanced/blob/main/apks/options.toml) for patch options.
###### Complete and original README can be found [here](https://github.com/Spacellary/docker-py-revanced/blob/main/README-ORIGINAL.md).
