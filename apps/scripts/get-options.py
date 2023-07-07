import os
import re
import json
import requests

# Get patches JSON
def get_options_json(url):
    response = requests.get(url)
    patches_json = response.text
    data = json.loads(patches_json)

    options_json = []
    unique_objects = set()  # To store unique objects

    for obj in data:
        options = obj["options"]
        if not options:  # Skip if "options" array is empty
            continue
        patch_name = obj["name"]
        options_list = []
        for option in options:
            key = option["key"]
            value = option.get("value", None)
            options_list.append({"key": key, "value": value})
        obj_tuple = (patch_name, json.dumps(options_list, sort_keys=True))
        if obj_tuple not in unique_objects:
            unique_objects.add(obj_tuple)
            options_json.append({"patchName": patch_name, "options": options_list})
    print(options_json)
    return options_json

# Convert to formatted JSON string
def format_options_json(opjson):
    opjson_str = json.dumps(opjson, indent=1, separators=(",", " : "), ensure_ascii=False)
    opjson_str = re.sub(r'\[\n(?:(?:\s+?)?)\{', r'[ {', opjson_str) # [ {
    opjson_str = re.sub(r' \}\n(?:(?:\s+?)?)\]', r'} ]', opjson_str) # } ]
    opjson_str = re.sub(r' \},\n\s+?\{', r'}, {', opjson_str) # }, {
    print(opjson_str)
    return opjson_str


urls = [
    "https://raw.githubusercontent.com/revanced/revanced-patches/main/patches.json",
    "https://raw.githubusercontent.com/inotia00/revanced-patches/revanced-extended/patches.json",
]

outs = [
    "apps/revanced/options.json",
    "apps/revanced-extended/options.json",
]

for url, output_file in zip(urls, outs):
    options_json = get_options_json(url)
    # options_json_str = json.dumps(options_json, indent=2)
    options_json_str = format_options_json(options_json)
    os.makedirs(os.path.dirname(output_file), exist_ok=True) # Create the directories if they don't exist
    with open(output_file, "w") as file:
        file.write(options_json_str)
