import os
import re
import json
import pytz
import datetime
import requests

from utils.scraper import scraper
from utils.repo import GitHubRepo
from utils.urls import GitHubURLs

gh = GitHubRepo()
repo = gh.get_repo()
branch = gh.get_branch()
urls = GitHubURLs(repo, branch)
patches_py_url = urls.get_patches_py()
rv_json_url = urls.get_rv_json()
rvx_json_url = urls.get_rvx_json()

json_file = "apps/json/apps.json"
md_file = "apps/docs/apps.md"

def get_available_patch_apps(url):
    response = requests.get(url)
    python_code = response.text
    # Extract package_name and app_code from the Python code
    pattern = r'"([^"]+)":\s*"([^"]+)",'
    matches = re.findall(pattern, python_code)
    package_name = []
    app_code = []
    for package, code in matches:
        package_name.append(package.strip())
        app_code.append(code.strip())
    return package_name, app_code

def get_app_code(package):
    if isinstance(package, list):
        code = []
        for pkg in package:
            i = available_packages.index(pkg)
            code.append(app_code[i])
    elif isinstance(package, str):
        i = available_packages.index(package)
        code = app_code[i]
    return code

def get_patches_json(i):
    i = 0 if i == "rv" else (1 if i == "rvx" else i)
    urls = [
        rv_json_url,
        rvx_json_url,
    ]
    url = urls[i]
    r = requests.get(url)
    patches = r.json()
    return patches

def get_packages_from_patches(patches):
    packages = set()
    for item in patches:
        for package in item["compatiblePackages"]:
            packages.add(package["name"])
    return packages

def get_last_version(json_data, package_name):
    last_versions = []
    for obj in json_data:
        compatible_packages = obj.get("compatiblePackages", [])
        for package in compatible_packages:
            if package.get("name") == package_name:
                versions = package.get("versions", [])
                if versions:
                    last_versions.append(versions[-1])
                else:
                    last_versions.append("Any")
    return last_versions

def version_key(version):
    # Converts the version string to a tuple of integers
    return tuple(map(int, re.findall(r'\d+', version)))

rv_patches = get_patches_json("rv")
rvx_patches = get_patches_json("rvx")
all_patches = rv_patches + rvx_patches
all_packages = get_packages_from_patches(all_patches)
all_rv_packages = get_packages_from_patches(rv_patches)
all_rvx_packages = get_packages_from_patches(rvx_patches)

available_packages, app_code = get_available_patch_apps(patches_py_url)
rv_packages = list(set(all_rv_packages) & set(available_packages))
rvx_packages = list(set(all_rvx_packages) & set(available_packages))
supported_packages = list(set(all_packages) & set(available_packages))
rv_appcodes = get_app_code(rv_packages)
rvx_appcodes = get_app_code(rvx_packages)
supported_appcodes = get_app_code(supported_packages)
print("Package Names:", supported_packages, flush=True)
print("App Codes:", supported_appcodes, flush=True)

# Step 3: Match package names and scraping
def make_json_data(packages, patches=[]):
    json_data = []
    patch_apps = 0
    for package_name in packages:
        patch_apps += 1
        latest_versions = get_last_version(patches, package_name)
        target_version = max(latest_versions, key=version_key)
        print(package_name, flush=True)
        app_codename = get_app_code(package_name)
        app_name, app_icon, app_url = scraper(package_name, app_codename)
        print(app_name, flush=True)
        json_data.append({
                "app_package": package_name,
                "app_code": app_codename,
                "app_name": app_name,
                "app_url": app_url,
                "app_icon": app_icon,
                "target_version": target_version,
            })
    return patch_apps, json_data

rv_patch_apps, rv_json_data = make_json_data(rv_packages, rv_patches)
# rvx_patch_apps, rvx_json_data = make_json_data(rvx_packages, rvx_patches)
            
# Step 4: Handle unmatched package names
unadded_packages = list(all_packages - set(available_packages))
removed_packages = list(set(available_packages) - all_packages)
for package_name in unadded_packages:
    print("Missing package:", package_name, flush=True)

# unadded_scrape = []
# unadded_apps = 0
# removed_scrape = []
# removed_apps = 0
# for package_name in unadded_packages:
#     app_name, app_icon, app_url = scraper(package_name, None)
#     if app_name == "NA":
#         print("Unadded package:", package_name)
#     else:
#         unadded_apps += 1
#         unadded_scrape.append({
#                 "app_package": package_name,
#                 "app_name": app_name,
#                 "app_url": app_url,
#                 "app_icon": app_icon,
#             })
# for package_name in removed_packages:
#     app_name, app_icon, app_url = scraper(package_name, None)
#     if app_name == "NA":
#         print("Removed package:", package_name)
#     else:
#         removed_apps += 1
#         removed_scrape.append({
#                 "app_package": package_name,
#                 "app_name": app_name,
#                 "app_url": app_url,
#                 "app_icon": app_icon,
#             })
# print("\nUnadded Scrape:", unadded_scrape)
# print("\nRemoved Scrape:", removed_scrape)
# def check_path(file_path):
#     # Create the directories if they don't exist
#     os.makedirs(os.path.dirname(file_path), exist_ok=True)

# def write_md(file, content):
#     check_path(file)
#     with open(file, "w", encoding="utf-8") as f:
#         f.write(content)

# def write_json(file, data):
#     check_path(file)
#     with open(file, "w", encoding="utf-8") as f:
#         json.dump(data, f, indent=4, ensure_ascii=False)

# def make_md(json_data, title, body, type):

#     # Sort the output data by app_name in ascending order
#     json_data.sort(key=lambda x: (x["app_name"] != "YouTube", x["app_name"] != "YouTube Music", x["app_name"].lower()))

#     # Create md content
#     content = f"### {title}\n"
#     content += f"{body}\n"
#     if type == "rv" or type == "rvx":
#         supported = True
#     else:
#         supported = False
    
#     if supported:
#         table = "| S.No. | Icon | Name | Code | Package |\n"
#         table +="|:-----:|------|------|------|---------|\n"
#     elif not supported:
#         table = "| S.No. | Icon | Name | Package |\n"
#         table +="|:-----:|------|------|---------|\n"
#     serial_no = 0
#     for entry in json_data:
#         app_package = entry["app_package"]
#         app_name = entry["app_name"]
#         app_icon = entry["app_icon"]
#         app_url = entry["app_url"]
#         if supported:
#             app_code = entry["app_code"]
#         serial_no += 1
#         # Escape pipe characters in the data
#         app_package = app_package.replace("|", "\\|")
#         if supported:
#             app_code = app_code.replace("|", "\\|")
#         app_name = app_name.replace("|", "\\|")
#         app_icon = app_icon.replace("|", "\\|")
#         app_url = app_url.replace("|", "\\|")
#         # Add a row to the table
#         if supported:
#             table += f"| {serial_no}. | ![]({app_icon}) | [**{app_name}**]({app_url}) | `{app_code}` | `{app_package}` |\n"
#         elif not supported:
#             table += f"| {serial_no}. | ![]({app_icon}) | [**{app_name}**]({app_url}) | `{app_package}` |\n"
    
#     # Combine the content and table
#     content += table
#     return content
# timezone = pytz.timezone("UTC")
# current_time = datetime.datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S %Z")
# # content += f"Generated at **`{current_time}`**\n\n"
# def heading_and_toc():
#     content = f'''# Apps

# ***Generated at `{current_time}`***\n

# ## Table of Contents
# 1. [Supported Apps](#supported-apps)
# 	- [ReVanced](#revanced)
# 	- [ReVanced Extended](#revanced-extended)
# 2. [Unsupported Apps](#unsupported-apps)
# 	- [Unadded](#unadded)
# 	- [Removed](#removed)\n\n'''
    
#     return content

# def write_supported(apps, data):
#     content = '''## Supported Apps

# Here are the listed apps that are eligible to be patched using this repository's resources.

# **Note: Not all apps that can be patched are present in this list. Try raising an issue or a PR for me to add that app**.\n\n'''

#     titles = ['ReVanced','ReVanced Extended']
#     bodies = [
#         f'Here is a list of {apps[0]} apps that can be patched using [**ReVanced**](https://www.github.com/revanced/revanced-patches) provided officially by the **ReVanced Team**.\n\n',
#         f'''Here is a list of {apps[1]} apps that can be patched using [**ReVanced Extended (RVX)**](https://www.github.com/inotia00/revanced-patches) provided by **inotia00**. 

# **Note: It supports fewer apps but provides more patches compared to ReVanced.**\n\n'''
#     ]
#     types = ['rv','rvx']

#     for json, title, body, type in zip(data, titles, bodies, types):
#         content += f'{make_md(json, title, body, type)}\n\n'
#     return content

# def write_unsupported(apps, data):
#     content = '''## Unsupported Apps

# Here are the listed apps that are ineligible to be patched using this repository's resources. The possible reasons are:
# 1. ***Slipped through my attention. In this case, raise an issue or a discussion.***
# 2. ***The app is pay to download, or there is not a reliable legitimate source (modded APKs as an example). In this case, you'll have to add that app yourself with required resources.***
# 3. ***Lastly, removed from the patches. In this case, no solution.***\n\n'''

#     titles = ['Unadded', 'Removed']
#     bodies = [
#         f'Here is a list of {apps[0]} apps that are not yet added to be able to patch them.\n\n',
#         f'Here is a list of {apps[1]} apps that were previously supported but have been removed from the provided patches.\n\n'
#     ]
#     types = ['unsupported','unsupported']
#     for json, title, body, type in zip(data, titles, bodies, types):
#         content += f'{make_md(json, title, body, type)}\n\n'
#     return content


# supported_apps = [rv_patch_apps, rvx_patch_apps]
# supported_data = [rv_json_data, rvx_json_data]
# unsupported_apps = [unadded_apps, removed_apps]
# unsupported_data = [unadded_scrape, removed_scrape]
# content = heading_and_toc()
# content += write_supported(supported_apps, supported_data)
# content += write_unsupported(unsupported_apps, unsupported_data)
# write_md("./appsr.md", content)
# exit()

def write_md(patch_apps, json_data):
    # Sort the output data by app_name in ascending order
    json_data.sort(key=lambda x: (x["app_name"] != "YouTube", x["app_name"] != "YouTube Music", x["app_name"].lower()))
    os.makedirs(os.path.dirname(json_file), exist_ok=True) # Create the directories if they don't exist
    # Dump json data to JSON file
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=4, ensure_ascii=False)
    print("Apps json data has been dumped to 'apps.json'!!", flush=True)

    # Load the data from the JSON file
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Write apps.md
    content = "# Apps\n\n"
    content += f"## Here is a list of {patch_apps} apps that can be patched\n\n"
    timezone = pytz.timezone("UTC")
    current_time = datetime.datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S %Z")
    content += f"Generated at **`{current_time}`**\n\n"
    table = "| S.No. | Icon | Name | Code | ReVanced Extended (RVX) | Package |\n"
    table +="|:-----:|------|------|------|:-----------------------:|---------|\n"
    serial_no = 0
    for entry in data:
        app_package = entry["app_package"]
        app_code = entry["app_code"]
        app_name = entry["app_name"]
        app_icon = entry["app_icon"]
        app_url = entry["app_url"]
        serial_no += 1
        if app_package in rvx_packages:
            extended = ":white_check_mark:"
        else:
            extended = ":x:"
        # Escape pipe characters in the data
        app_package = app_package.replace("|", "\\|")
        app_code = app_code.replace("|", "\\|")
        app_name = app_name.replace("|", "\\|")
        app_icon = app_icon.replace("|", "\\|")
        app_url = app_url.replace("|", "\\|")
        # Add a row to the table
        table += f"| {serial_no}. | ![]({app_icon}) | [**{app_name}**]({app_url}) | `{app_code}` | {extended} | `{app_package}` |\n"
    # Combine the content and table
    content += table
    # Add more sentences or content
    content += "\n**Note: Not all apps that can be patched using ReVanced are present in this list. Try raising an issue for me to add that app or you may do it yourself. [Look here]()**.\n"
    os.makedirs(os.path.dirname(md_file), exist_ok=True) # Create the directories if they don't exist
    # Write the content to the Markdown file
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(content)

write_md(rv_patch_apps, rv_json_data)