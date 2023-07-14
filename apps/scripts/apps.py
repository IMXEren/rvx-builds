import os
import re
import json
import pytz
import datetime
import requests
from bs4 import BeautifulSoup
from pyvirtualdisplay import Display
from selenium import webdriver
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from scraper import scraper

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
        'https://raw.githubusercontent.com/revanced/revanced-patches/main/patches.json',
        'https://raw.githubusercontent.com/inotia00/revanced-patches/revanced-extended/patches.json',
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

# def gplay_scrape(package_name):
#     app_url = f"https://play.google.com/store/apps/details?id={package_name}"
#     response = requests.get(app_url)
#     soup = BeautifulSoup(response.text, "html.parser")
#     app_name_element = soup.select_one("h1 > span")
#     app_icon_element = soup.select_one("div.Il7kR > img")
#     if app_icon_element is None:
#         app_icon_element = soup.select_one("div.qxNhq > img")
#     if app_icon_element:
#         app_icon = app_icon_element["src"] if app_icon_element else ""
#         app_icon = app_icon.replace("=w240-h480", "=w64-h64")
#     if app_name_element:
#         app_name = app_name_element.text
#     return app_name, app_icon, app_url

# def apk_mirror_selenium_scrape(app_code):
#     apk_mirror = "https://www.apkmirror.com"
#     config_py_file_url = "https://raw.githubusercontent.com/IMXEren/rvx-builds/main/src/config.py"
#     response = requests.get(config_py_file_url)
#     pattern = r'"{}": f"(.*?)",'.format(app_code)
#     match = re.search(pattern, response.text)
#     if match:
#         app_url = match.group(1)
#         app_url = app_url.replace("{self.apk_mirror}", apk_mirror)
#         print(app_url)
#         display = Display(visible=0, size=(800, 600))
#         display.start()
#         chrome_options = Options()
#         # driver = uc.Chrome(headless=True, options=chrome_options)
#         driver = webdriver.Chrome(options=chrome_options)
#         driver.get(app_url)
#         app_name_element = driver.find_element(By.CSS_SELECTOR, "#masthead > header > div > div > div.f-grow > h1")
#         app_icon_element = driver.find_element(By.CSS_SELECTOR, "#masthead > header > div > div > div.p-relative.icon-container > img")
#         app_name = app_name_element.text if app_name_element else "NA"
#         app_icon = app_icon_element.get_attribute("src") if app_icon_element else "NA"
#         app_icon = app_icon.replace("&w=96&h=96", "&w=64&h=64")
#         driver.quit()
#         display.stop()
#         print("App Name:", app_name, flush=True)
#         print("Icon URL:", app_icon, flush=True)
#         return app_name, app_icon, app_url
#     else:
#         print("APKMirror URL not found for the specified app code")

# def apk_mirror_requests_scrape(app_code):
#     apk_mirror = "https://www.apkmirror.com"
#     config_py_file_url = "https://raw.githubusercontent.com/IMXEren/rvx-builds/main/src/config.py"
#     response = requests.get(config_py_file_url)
#     pattern = r'"{}": f"(.*?)",'.format(app_code)
#     match = re.search(pattern, response.text)
#     if match:
#         app_url = match.group(1)
#         app_url = app_url.replace("{self.apk_mirror}", apk_mirror)
#         print(app_url)
#         s = requests
#         hdr = {
#             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
#             'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
#             'Accept-Encoding': 'none',
#             'Accept-Language': 'en-US,en;q=0.9',
#             'Connection': 'keep-alive',
#             }
#         r = s.get(app_url, headers=hdr)
#         soup = BeautifulSoup(r.text, "html.parser")
#         app_name_element = soup.select_one("#masthead > header > div > div > div.f-grow > h1")
#         app_icon_element = soup.select_one("#masthead > header > div > div > div.p-relative.icon-container > img")
#         if app_icon_element:
#             app_icon = app_icon_element["src"] if app_icon_element else ""
#             app_icon = f'{apk_mirror}{app_icon.replace("&w=96&h=96", "&w=64&h=64")}'
#         if app_name_element:
#             app_name = app_name_element.text
#         print("App Name:", app_name, flush=True)
#         print("Icon URL:", app_icon, flush=True)
#         return app_name, app_icon, app_url
#     else:
#         print("APKMirror URL not found for the specified app code")

# def get_json_data(key, value, url):
#     response = requests.get(url)
#     data = response.json()
#     matched_objects = [obj for obj in data if obj.get(key) == value]
#     return matched_objects

# def scraper(package_name, code_name):
#     # Parameter variables    
#     key = "app_package"
#     value = package_name
#     url = "https://raw.githubusercontent.com/IMXEren/rvx-builds/main/apps/json/extras.json"
    
#     # Ordered List of functions
#     scrapers = [get_json_data, gplay_scrape, apk_mirror_requests_scrape, apk_mirror_selenium_scrape]
    
#     # Ordered List of parameter variables
#     params = [
#         (key, value, url,),
#         (package_name,),
#         (code_name,),
#         (code_name,),
#     ]
    
#     # Calling functions with parameter variables
#     for scraper, param in zip(scrapers, params):
#         # print("Scraper:", scraper.__name__)
#         # print("Params:", param)
#         try:
#             if scraper == get_json_data:
#                 result = scraper(*param)
#                 app_name, app_icon, app_url = result[0]['app_name'], result[0]['app_icon'], result[0]['app_url']
#             else:
#                 app_name, app_icon, app_url = scraper(*param)
#             break
#         except Exception as e:
#             app_name, app_icon, app_url = "NA", "NA", "NA"
#             # print("ERROR:", str(e))
#             continue
#     return app_name, app_icon, app_url

rv_patches = get_patches_json("rv")
rvx_patches = get_patches_json("rvx")
all_patches = rv_patches + rvx_patches
all_packages = get_packages_from_patches(all_patches)
all_rv_packages = get_packages_from_patches(rv_patches)
all_rvx_packages = get_packages_from_patches(rvx_patches)

py_file_url = "https://raw.githubusercontent.com/IMXEren/rvx-builds/main/src/patches.py"
available_packages, app_code = get_available_patch_apps(py_file_url)
rv_packages = list(set(all_rv_packages) & set(available_packages))
rvx_packages = list(set(all_rvx_packages) & set(available_packages))
supported_packages = list(set(all_packages) & set(available_packages))
rv_appcodes = get_app_code(rv_packages)
rvx_appcodes = get_app_code(rvx_packages)
supported_appcodes = get_app_code(supported_packages)
print("Package Names:", supported_packages, flush=True)
print("App Codes:", supported_appcodes, flush=True)

# Step 3: Match package names and scraping
json_data = []
patch_apps = 0
for package_name in supported_packages:
    if package_name in rv_packages:
        app_extended = False
    if package_name in rvx_packages:
        app_extended = True
    patch_apps += 1
    latest_versions = get_last_version(all_patches, package_name)
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
            "app_extended": app_extended,
        })

            
# Step 4: Handle unmatched package names
unmatched_packages = all_packages - set(available_packages)
for package_name in unmatched_packages:
    print("Missing package:", package_name, flush=True)

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
