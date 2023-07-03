import re
import json
import requests

# Get info
def get_pkg(env_file, file):
    # Get env file contents
    response = requests.get(env_file)
    env_content = response.text
    
    # Get App Packages and Codes
    response = requests.get(file)
    python_code = response.text
    pattern = r'"([^"]+)":\s*\(?"([^"]+)",'
    matches = re.findall(pattern, python_code)
    get_pkg.packages = []
    get_pkg.codes = []
    for package_name, code in matches:
        get_pkg.packages.append(package_name.strip())
        get_pkg.codes.append(code.strip())
    return env_content

# Parse json_data from env_content
# Parsed with extra keys (EXTENDED) for every app
def parse_json_data_with_extras(env_content):
    env_dict = {}
    lines = env_content.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or line.isspace():
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        env_dict[key] = value

    # Generate the JSON structure
    existing_downloaded_apks_list = env_dict.get("EXISTING_DOWNLOADED_APKS", "").split(",")
    patch_apps_list = env_dict.get("PATCH_APPS", "").split(",")

    json_data = {
        "env": [
            {
                "keystore_file_name": env_dict.get("KEYSTORE_FILE_NAME", ""),
                "archs_to_build": env_dict.get("ARCHS_TO_BUILD", "").split(","),
                "build_extended": env_dict.get("BUILD_EXTENDED", "False"),
                "existing_downloaded_apks": [{"app_name": code, "app_package": package} for package, code in zip(get_pkg.packages, get_pkg.codes) if code in existing_downloaded_apks_list],
                "patch_apps": [
                    {
                        "app_package": package,
                        package: [
                            {
                                "app_name": code,
                                "version": env_dict.get(f"{code.upper()}_VERSION", "latest_supported"),
                                "exclude_patch_app": env_dict.get(f"EXCLUDE_PATCH_{code.upper()}", "").split(","),
                                "exclude_patch_app_extended": env_dict.get(f"EXCLUDE_PATCH_{code.upper()}_EXTENDED", "").split(",") if code in ['youtube', 'youtube_music'] else [],
                                "alternative_app_patch": env_dict.get(f"ALTERNATIVE_{code.upper()}_PATCHES", "").split(",") if code in ['youtube', 'youtube_music'] else [],
                            }
                        ]
                    }
                    for package, code in zip(get_pkg.packages, get_pkg.codes) if code in patch_apps_list
                ]
            }
        ]
    }
    return json_data

# Parse json_data from env_content
# Parsed without extra keys (EXTENDED) for every app
def parse_json_data(env_content):
    env_dict = {}
    lines = env_content.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or line.isspace():
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        env_dict[key] = value

    # Generate the JSON structure
    existing_downloaded_apks_list = env_dict.get("EXISTING_DOWNLOADED_APKS", "").split(",")
    patch_apps_list = env_dict.get("PATCH_APPS", "").split(",")

    json_data = {
        "env": [
            {
                "keystore_file_name": env_dict.get("KEYSTORE_FILE_NAME", ""),
                "archs_to_build": env_dict.get("ARCHS_TO_BUILD", "").split(","),
                "build_extended": env_dict.get("BUILD_EXTENDED", "False"),
                "existing_downloaded_apks": [{"app_name": code, "app_package": package} for package, code in zip(get_pkg.packages, get_pkg.codes) if code in existing_downloaded_apks_list],
                "patch_apps": []
            }
        ]
    }

    for package, code in zip(get_pkg.packages, get_pkg.codes):
        if code in patch_apps_list:
            app_data = {
                "app_package": package,
                package: [
                    {
                        "app_name": code,
                        "version": env_dict.get(f"{code.upper()}_VERSION", "latest_supported"),
                        "exclude_patch_app": env_dict.get(f"EXCLUDE_PATCH_{code.upper()}", "").split(","),
                    }
                ]
            }
            if code in ['youtube', 'youtube_music']:
                exclude_patch_app_extended = env_dict.get(f"EXCLUDE_PATCH_{code.upper()}_EXTENDED", "").split(",")
                alternative_app_patches = env_dict.get(f"ALTERNATIVE_{code.upper()}_PATCHES", "").split(",")
                if exclude_patch_app_extended:
                    app_data[package][0]["exclude_patch_app_extended"] = exclude_patch_app_extended
                if alternative_app_patches:
                    app_data[package][0]["alternative_app_patches"] = alternative_app_patches
            
            json_data["env"][0]["patch_apps"].append(app_data)
    return json_data

# Replace empty lists with []
def replace_empty_lists(data):
    if isinstance(data, dict):
        return {k: replace_empty_lists(v) if v != [""] else [] for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_empty_lists(v) if v != [""] else [] for v in data]
    else:
        return data

# Write generated json_data into file
def write_json_file(json_string, output_file):
    with open(output_file, "w") as file:
        file.write(json_string)

py_file_url = "https://raw.githubusercontent.com/IMXEren/rvx-builds/main/src/patches.py"
env_file_url = "https://raw.githubusercontent.com/IMXEren/rvx-builds/main/.env"
env_content = get_pkg(env_file_url, py_file_url)
json_data = parse_json_data(env_content)
json_data = replace_empty_lists(json_data)
# Convert the JSON to a formatted string
json_string = json.dumps(json_data, indent=4)
output_file = "env.json"
write_json_file(json_string, output_file)
print(json_string)
