import re
import json
import requests
from loguru import logger

import utils.writer as wr
from utils.repo import GitHubRepo
from utils.urls import GitHubURLs

# Get patches JSON
@logger.catch
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
    return options_json

# Convert to formatted JSON string
@logger.catch
def format_options_json(opjson):
    opjson_str = json.dumps(opjson, indent=1, separators=(",", " : "), ensure_ascii=False)
    opjson_str = re.sub(r'\[\n(?:(?:\s+?)?)\{', r'[ {', opjson_str) # [ {
    opjson_str = re.sub(r' \}\n(?:(?:\s+?)?)\]', r'} ]', opjson_str) # } ]
    opjson_str = re.sub(r' \},\n\s+?\{', r'}, {', opjson_str) # }, {
    return opjson_str

if __name__ == "__main__":
    gh = GitHubRepo()
    repo = gh.get_repo()
    branch = gh.get_branch()
    urls = GitHubURLs(repo, branch)
    rv_json_url = urls.get_rv_json()
    rvx_json_url = urls.get_rvx_json()

    urls = [
        rv_json_url,
        rvx_json_url,
    ]

    outs = [
        "apps/revanced/options.json",
        "apps/revanced-extended/options.json",
    ]

    for url, output_file in zip(urls, outs):
        options_json = get_options_json(url)
        logger.debug(options_json)
        # options_json_str = json.dumps(options_json, indent=2)
        options_json_str = format_options_json(options_json)
        logger.debug("""{}""", options_json_str)
        wr.check_path(output_file)
        with open(output_file, "w") as file:
            file.write(options_json_str)
        logger.info('Fetched options.json for revanced and revanced-extended')