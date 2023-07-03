#!/usr/bin/bash

github_repo=""
rename_script_1="apps/apps.py"
# rename_script_2

# Replace "py_file_url = ..." with a new URL
sed -i "s@py_file_url = \"https://raw.githubusercontent.com/.*@py_file_url = \"https://raw.githubusercontent.com/$github_repo/main/src/patches.py\"@" "$rename_script_1"

# Replace "config_py_file_url = ..." with a new URL
sed -i "s@config_py_file_url = \"https://raw\.githubusercontent\.com/.*@config_py_file_url = \"https://raw.githubusercontent.com/$github_repo/main/src/config.py\"@" "$rename_script_1"

# Add more sed commands if needed
