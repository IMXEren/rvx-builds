import os
import re
import json
import requests

import utils.writer as wr
from utils.repo import GitHubRepo
from utils.urls import GitHubURLs

gh = GitHubRepo()
repo = gh.get_repo()
branch = gh.get_branch()
urls = GitHubURLs(repo, branch)
rv_json_url = urls.get_rv_json()
rvx_json_url = urls.get_rvx_json()
py_file_url = urls.get_patches_py()
env_file_url = urls.get_env()

# Get info
def get_pkg():
    # Get env file contents
    response = requests.get(env_file_url)
    env_content = response.text
    
    # Get App Packages and Codes
    response = requests.get(py_file_url)
    python_code = response.text
    pattern = r'"([^"]+)":\s*"([^"]+)",'
    matches = re.findall(pattern, python_code)
    get_pkg.packages = []
    get_pkg.codes = []
    for package_name, code in matches:
        get_pkg.packages.append(package_name.strip())
        get_pkg.codes.append(code.strip())
    return env_content

def set_patch_type():
    def get_packages_from_patches(patches):
        packages = set()
        for item in patches:
            for package in item["compatiblePackages"]:
                packages.add(package["name"])
        return packages
    
    def allign_codes(list):
        codes = []
        for package in list:
            i = get_pkg.packages.index(package)
            code = get_pkg.codes[i]
            codes.append(code)
        return codes
    
    for url in rv_json_url, rvx_json_url:
        r = requests.get(url)
        patches = r.json()
        packages = get_packages_from_patches(patches)
        if url == rv_json_url:
            global rv_packages, rv_codes
            rv_packages = list(set(get_pkg.packages) & set(packages))
            rv_codes = allign_codes(rv_packages)
        else:
            global rvx_packages, rvx_codes
            rvx_packages = list(set(get_pkg.packages) & set(packages))
            rvx_codes = allign_codes(rvx_packages)

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
                "dry_run": env_dict.get("DRY_RUN", "False"),
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
                        "include_patch_app": env_dict.get(f"INCLUDE_PATCH_{code.upper()}", "").split(","),
                        "exclude_patch_app": env_dict.get(f"EXCLUDE_PATCH_{code.upper()}", "").split(","),
                    }
                ]
            }
            if code in rvx_codes:
                exclude_patch_app_extended = env_dict.get(f"EXCLUDE_PATCH_{code.upper()}_EXTENDED", "").split(",")
                if exclude_patch_app_extended:
                    app_data[package][0]["exclude_patch_app_extended"] = exclude_patch_app_extended
            if code in ['youtube', 'youtube_music']:
                alternative_app_patches = env_dict.get(f"ALTERNATIVE_{code.upper()}_PATCHES", "").split(",")
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

env_content = get_pkg()
set_patch_type()
json_data = parse_json_data(env_content)
json_data = replace_empty_lists(json_data)
json_string = json.dumps(json_data, indent=4)
output_file = "apps/json/env.json"
wr.write_json(output_file, json_data)
print(json_string, flush=True)