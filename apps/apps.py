import requests
from bs4 import BeautifulSoup
import json
import re
import datetime
import pytz

json_file = "apps/apps.json"
md_file = "apps/apps.md"

# Step 1: Parse the online .py file to extract package names and app codes
py_file_url = "https://raw.githubusercontent.com/IMXEren/rvx-builds/main/src/patches.py"
response = requests.get(py_file_url)
python_code = response.text
# Extract package_name and app_code from the Python code
pattern = r'"([^"]+)":\s*\("([^"]+)",'
matches = re.findall(pattern, python_code)
package_name_from_py = []
app_code = []
for package_name, code in matches:
    package_name_from_py.append(package_name.strip())
    app_code.append(code.strip())
# Print the extracted package_name_from_py and app_code
print("Package Names:", package_name_from_py)
print("App Codes:", app_code)


# Step 2: Get all different compatiblePackages names from the revanced/revanced-patches.json file
json_file_url = "https://raw.githubusercontent.com/revanced/revanced-patches/main/patches.json"
response = requests.get(json_file_url)
json_patches = response.json()
compatible_packages_names = set()
for item in json_patches:
    for package in item["compatiblePackages"]:
        compatible_packages_names.add(package["name"])

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
                    last_versions.append("All")
    return last_versions

def version_key(version):
    # Converts the version string to a tuple of integers
    return tuple(map(int, re.findall(r'\d+', version)))

def apk_mirror_scrape(app_code):
    apk_mirror = "https://www.apkmirror.com"
    config_py_file_url = "https://raw.githubusercontent.com/IMXEren/rvx-builds/main/src/config.py"
    response = requests.get(config_py_file_url)
    pattern = r'"{}": f"(.*?)",'.format(app_code)
    match = re.search(pattern, response.text)
    if match:
        app_url = match.group(1)
        app_url = app_url.replace("{self.apk_mirror}", apk_mirror)
        print(app_url)
        driver = webdriver.Chrome()
        driver.get(app_url)
        app_name_element = driver.find_element(By.CSS_SELECTOR, "#masthead > header > div > div > div.f-grow > h1")
        app_icon_element = driver.find_element(By.CSS_SELECTOR, "#masthead > header > div > div > div.p-relative.icon-container > img")
        app_name = app_name_element.text if app_name_element else "NA"
        app_icon = app_icon_element.get_attribute("src") if app_icon_element else "NA"
        app_icon = app_icon.replace("&w=96&h=96", "&w=64&h=64")
        driver.quit()
        print("App Name:", app_name)
        print("Icon URL:", app_icon)
        return app_name, app_icon
    else:
        print("APKMirror URL not found for the specified app code")

# Step 3: Match package names and scraping
json_data = []
for package_name in compatible_packages_names:
    if package_name in package_name_from_py:
        latest_versions = get_last_version(json_patches, package_name)
        target_version = max(latest_versions, key=version_key)
        print(package_name)
        index = package_name_from_py.index(package_name)
        app_codename = app_code[index]
        url = f"https://play.google.com/store/apps/details?id={package_name}"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        app_name_element = soup.select_one("h1 > span")
        app_icon_element = soup.select_one("div.Il7kR > img")
        if app_icon_element is None:
            app_icon_element = soup.select_one("div.qxNhq > img")
        if app_icon_element:
            app_icon = app_icon_element["src"] if app_icon_element else ""
            app_icon = app_icon.replace("=w240-h480", "=w64-h64")
        if app_name_element:
            app_name = app_name_element.text
        if app_name_element or app_icon_element is None:
            app_name, app_icon = apk_mirror_scrape(app_codename)
        print(app_name)
        json_data.append({"app_package": package_name, "app_code": app_codename, "app_name": app_name, "app_url": url, "app_icon": app_icon, "target_version": target_version})

            
# Step 4: Drop unmatched package names
unmatched_packages = compatible_packages_names - set(package_name_from_py)
for package_name in unmatched_packages:
    print("Missing package:", package_name)

# Sort the output data by app_name in ascending order
json_data.sort(key=lambda x: (x["app_name"] != "YouTube", x["app_name"] != "YouTube Music", x["app_name"].lower()))
# Dump json data to JSON file
with open(json_file, "w", encoding="utf-8") as f:
    json.dump(json_data, f, indent=4, ensure_ascii=False)
print("Apps json data has been dumped to 'apps.json'!!")

# Load the data from the JSON file
with open(json_file, "r", encoding="utf-8") as f:
    data = json.load(f)
# Write apps.md
timezone = pytz.timezone("Asia/Kolkata")
current_time = datetime.datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S")
content = "# Apps\n\n"
content += "## Here is a list of apps that can be patched\n\n"
content += f"Generated at {current_time} IST\n\n"
table = "| Icon | Name | Code | Package |\n"
table += "|--------------|----------|----------|----------|\n"
for entry in data:
    app_package = entry["app_package"]
    app_code = entry["app_code"]
    app_name = entry["app_name"]
    app_icon = entry["app_icon"]
    app_url = entry["app_url"]
    # Escape pipe characters in the data
    app_package = app_package.replace("|", "\\|")
    app_code = app_code.replace("|", "\\|")
    app_name = app_name.replace("|", "\\|")
    app_icon = app_icon.replace("|", "\\|")
    app_url = app_url.replace("|", "\\|")
    # Add a row to the table
    table += f"| ![{app_url}]({app_icon}) | [**{app_name}**]({app_url}) | `{app_code}` | `{app_package}` |\n"
# Combine the content and table
content += table
# Add more sentences or content
content += "\n**Note: Not all apps that can be patched using ReVanced are present in this list. Try raising an issue for me to add that app or you may do it yourself. [Look here]()**.\n"
# Write the content to the Markdown file
with open(md_file, "w", encoding="utf-8") as f:
    f.write(content)
