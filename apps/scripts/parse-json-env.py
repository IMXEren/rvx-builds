import os
import json
import requests

def parse_env_json_to_env(json_data, output_file, key_order, key_order_placeholder):
    # Load the JSON data
    data = json.loads(json_data)

    # Extract the required values from the JSON
    env_dict = {}
    env_dict["KEYSTORE_FILE_NAME"] = data["env"][0].get("keystore_file_name", "")
    env_dict["ARCHS_TO_BUILD"] = ",".join(data["env"][0].get("archs_to_build", []))
    env_dict["BUILD_EXTENDED"] = data["env"][0].get("build_extended", "False")

    existing_downloaded_apks = [apk["app_name"] for apk in data["env"][0].get("existing_downloaded_apks", [])]
    env_dict["EXISTING_DOWNLOADED_APKS"] = ",".join(existing_downloaded_apks)

    patch_apps = []
    for app_data in data["env"][0].get("patch_apps", []):
        app_package = app_data["app_package"]
        app_name = list(app_data[app_package][0].values())[0]
        app_version = app_data[app_package][0].get("version", "")
        
        # Extract the required values
        app_version = app_data[app_package][0].get("version", "")
        exclude_patch = ",".join(app_data[app_package][0].get("exclude_patch_app", []))
        exclude_patch_extended = ",".join(app_data[app_package][0].get("exclude_patch_app_extended", []))
        alternative_patches = ",".join(app_data[app_package][0].get("alternative_app_patches", []))

        # Add the keys and values to the environment dictionary
        env_dict[f"{app_name.upper()}_VERSION"] = app_version
        env_dict[f"EXCLUDE_PATCH_{app_name.upper()}"] = exclude_patch
        env_dict[f"EXCLUDE_PATCH_{app_name.upper()}_EXTENDED"] = exclude_patch_extended
        env_dict[f"ALTERNATIVE_{app_name.upper()}_PATCHES"] = alternative_patches

        # Replace the placeholder APP_NAME with the actual app names in the key_order
        for key in key_order_placeholder:
            key = key.replace("APP_NAME", app_name.upper())
            key_order.append(key)

        # Add the app_name to the patch_apps list
        patch_apps.append(app_name)
    env_dict["PATCH_APPS"] = ",".join(patch_apps)

    # Write the env_content
    env_content = ""
    for key in key_order:
        value = env_dict.get(key)
        if key.endswith("_VERSION") and value == "latest_supported":
            env_content += f"# {key}={value}\n"
        elif value:
            env_content += f"{key}={value}\n"

    os.makedirs(os.path.dirname(output_file), exist_ok=True) # Create the directories if they don't exist
    # Write the env_content to a file
    with open(output_file, "w") as file:
        file.write(env_content)
    print(env_content, flush=True)

# Get the JSON data
# json_file = open('apps/env.json', 'r')
# json_data = json_file.read()
# json_file.close()

json_file = "https://raw.githubusercontent.com/IMXEren/rvx-builds/main/apps/env.json"
json_data = requests.get(json_file).text
output_file = "apps/.env"

# Define the desired sorting key order
key_order = [
    "KEYSTORE_FILE_NAME",
    "ARCHS_TO_BUILD",
    "BUILD_EXTENDED",
    "PATCH_APPS",
    "EXISTING_DOWNLOADED_APKS",
]
key_order_placeholder = [
    "APP_NAME_VERSION",
    "EXCLUDE_PATCH_APP_NAME",
    "EXCLUDE_PATCH_APP_NAME_EXTENDED",
    "ALTERNATIVE_APP_NAME_PATCHES",
]

parse_env_json_to_env(json_data, output_file, key_order, key_order_placeholder)
