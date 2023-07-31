import re
import requests
from loguru import logger

import utils.writer as wr
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

rv_json_file = "apps/revanced/apps.json"
rvx_json_file = "apps/revanced-extended/apps.json"
rvxm_json_file = "apps/revanced-extended/apps-merged.json"
md_file = "apps/docs/README.md"

@logger.catch
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

@logger.catch
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

@logger.catch
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

@logger.catch
def get_packages_from_patches(patches):
    packages = set()
    for item in patches:
        for package in item["compatiblePackages"]:
            packages.add(package["name"])
    return packages

@logger.catch
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

@logger.catch
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
logger.info("Package Names: {}", supported_packages)
logger.info("App Codes: {}", supported_appcodes)

# Step 3: Match package names and scraping
@logger.catch
def make_json_data(packages, patches=[]):
    json_data = []
    patch_apps = 0
    for package_name in packages:
        patch_apps += 1
        latest_versions = get_last_version(patches, package_name)
        target_version = max(latest_versions, key=version_key)
        logger.debug("{}. {}", patch_apps, package_name)
        app_codename = get_app_code(package_name)
        app_name, app_icon, app_url = scraper(package_name, app_codename)
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
rvx_patch_apps, rvx_json_data = make_json_data(rvx_packages, rvx_patches)

@logger.catch
def rvx_merge_json():
    json1_list = rvx_json_data
    json2_list = rv_json_data
    merged_dict = {obj['app_package']: obj for obj in json1_list}
    for obj2 in json2_list:
        if obj2['app_package'] not in merged_dict:
            merged_dict[obj2['app_package']] = obj2
    merged_list = list(merged_dict.values())
    wr.write_json(rvxm_json_file, merged_list)
            
# Step 4: Handle unmatched package names
unadded_packages = list(all_packages - set(available_packages))
removed_packages = list(set(available_packages) - all_packages)
# for package_name in unadded_packages:
#     print("Missing package:", package_name, flush=True)

unadded_scrape = []
unadded_apps = 0
removed_scrape = []
removed_apps = 0
for package_name in unadded_packages:
    logger.info("Scraping for unadded package - {}", package_name)
    app_name, app_icon, app_url = scraper(package_name, None)
    if app_name == "NA":
        logger.error("Unadded package: {}", package_name)
    else:
        unadded_apps += 1
        unadded_scrape.append({
                "app_package": package_name,
                "app_name": app_name,
                "app_url": app_url,
                "app_icon": app_icon,
            })
for package_name in removed_packages:
    logger.info("Scraping for removed package - {}", package_name)
    app_name, app_icon, app_url = scraper(package_name, None)
    if app_name == "NA":
        logger.error("Removed package: {}", package_name)
    else:
        removed_apps += 1
        removed_scrape.append({
                "app_package": package_name,
                "app_name": app_name,
                "app_url": app_url,
                "app_icon": app_icon,
            })
logger.info("\nUnadded Scrape: {}", unadded_scrape)
logger.info("\nRemoved Scrape: {}", removed_scrape)

supported_apps = [rv_patch_apps, rvx_patch_apps]
supported_data = [rv_json_data, rvx_json_data]
unsupported_apps = [unadded_apps, removed_apps]
unsupported_data = [unadded_scrape, removed_scrape]

supported_data = wr.filter_empty_data(supported_data)
unsupported_data = wr.filter_empty_data(unsupported_data)
content = wr.write_supported(supported_apps, supported_data)
content += wr.write_unsupported(unsupported_apps, unsupported_data)
header = wr.heading_and_toc(content)
content = (header + content).strip() + "\n"
wr.write_md(md_file, content)
wr.write_json(rv_json_file, rv_json_data)
wr.write_json(rvx_json_file, rvx_json_data)
rvx_merge_json()