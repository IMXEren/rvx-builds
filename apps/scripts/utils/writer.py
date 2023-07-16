import os
import re
import json
import pytz
import datetime
from unidecode import unidecode

def check_path(file_path):
    # Create the directories if they don't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

def write_md(file, content):
    check_path(file)
    with open(file, "w", encoding="utf-8") as f:
        f.write(content)

def write_json(file, data):
    check_path(file)
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def make_md(json_data, title, body, type):

    # Sort the output data by app_name in ascending order
    json_data.sort(key=lambda x: (x["app_name"] != "YouTube", x["app_name"] != "YouTube Music", x["app_name"].lower()))

    # Create md content
    content = f"### {title}\n"
    content += f"{body}\n"
    if type == "rv" or type == "rvx":
        supported = True
    else:
        supported = False
    
    if supported:
        table = "| S.No. | Icon | Name | Code | Package |\n"
        table +="|:-----:|------|------|------|---------|\n"
    elif not supported:
        table = "| S.No. | Icon | Name | Package |\n"
        table +="|:-----:|------|------|---------|\n"
    serial_no = 0
    for entry in json_data:
        app_package = entry["app_package"]
        app_name = entry["app_name"]
        app_icon = entry["app_icon"]
        app_url = entry["app_url"]
        if supported:
            app_code = entry["app_code"]
        serial_no += 1
        # Escape pipe characters in the data
        app_package = app_package.replace("|", "\\|")
        if supported:
            app_code = app_code.replace("|", "\\|")
        app_name = app_name.replace("|", "\\|")
        app_icon = app_icon.replace("|", "\\|")
        app_icon_alt = unidecode(app_name.lower().replace(" ", "\\_"))[:10] + "\\_icon"
        app_icon_alt = app_icon_alt.replace("\\\\", "\\")
        app_url = app_url.replace("|", "\\|")
        # Add a row to the table
        if supported:
            table += f"| {serial_no}. | ![{app_icon_alt}]({app_icon}) | [**{app_name}**]({app_url}) | `{app_code}` | `{app_package}` |\n"
        elif not supported:
            table += f"| {serial_no}. | ![{app_icon_alt}]({app_icon}) | [**{app_name}**]({app_url}) | `{app_package}` |\n"
    
    # Combine the content and table
    content += table
    return content

timezone = pytz.timezone("UTC")
current_time = datetime.datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S %Z")

def heading_and_toc(md_content):
    content = f'''# Apps

***Generated at `{current_time}`***\n\n'''
    content += f'{generate_toc(md_content)}\n'
    return content

def generate_toc(md_content):
    headings = re.findall(r'^(\#{1,6})\s+(.*)$', md_content, flags=re.MULTILINE)
    toc = "## Table of Contents\n"
    for level, title in headings:
        level_count = len(level)
        indent = "  " * (level_count - 1)
        link = title.lower().replace(" ", "-")
        toc += f"{indent}- [{title.strip()}](#{link})\n"
    return toc

def write_supported(apps, data):
    content = '''## Supported Apps

Here are the listed apps that are eligible to be patched using this repository's resources.

**Note: Not all apps that can be patched are present in this list. Try raising an issue or a PR for me to add that app**.\n\n'''

    titles = ['ReVanced','ReVanced Extended']
    bodies = [
        f'Here is a list of {apps[0]} apps that can be patched using [**ReVanced**](https://www.github.com/revanced/revanced-patches) provided officially by the **ReVanced Team**.\n\n',
        f'''Here is a list of {apps[1]} apps that can be patched using [**ReVanced Extended (RVX)**](https://www.github.com/inotia00/revanced-patches) provided by **inotia00**. 

**Note: It supports fewer apps but provides more patches compared to ReVanced.**\n\n'''
    ]
    types = ['rv','rvx']

    for json, title, body, type in zip(data, titles, bodies, types):
        content += f'{make_md(json, title, body, type)}\n\n'
    return content

def write_unsupported(apps, data):
    content = '''## Unsupported Apps

Here are the listed apps that are ineligible to be patched using this repository's resources. The possible reasons are:
1. ***Slipped through my attention. In this case, raise an issue or a discussion.***
2. ***The app is pay to download, or there is not a reliable legitimate source (modded APKs as an example). In this case, you'll have to add that app yourself with required resources.***
3. ***Lastly, removed from the patches. In this case, no solution.***\n\n'''

    titles = ['Unadded', 'Removed']
    bodies = [
        f'Here is a list of {apps[0]} apps that are not yet added to be able to patch them.\n\n',
        f'Here is a list of {apps[1]} apps that were previously supported but have been removed from the provided patches.\n\n'
    ]
    types = ['unsupported','unsupported']
    for json, title, body, type in zip(data, titles, bodies, types):
        content += f'{make_md(json, title, body, type)}\n\n'
    return content

def filter_empty_data(list):
    list = [i for i in list if i]
    return list