#!/usr/bin/bash

github_repo="IMXEren/rvx-builds"
github_branch="main"
rename_script_1="apps/scripts/apps.py"
rename_script_2="apps/scripts/utils/repo.py"

# Replace "py_file_url = ..." with a new URL
sed -i "s@repo = .*@repo = \"$github_repo\"@" "$rename_script_2"
sed -i "s@branch = .*@branch = \"$github_branch\"@" "$rename_script_2"

# Replace "config_py_file_url = ..." with a new URL
# sed -i "s@config_py_file_url = \"https://raw\.githubusercontent\.com/.*@config_py_file_url = \"https://raw.githubusercontent.com/$github_repo/main/src/config.py\"@" "$rename_script_1"

# Add more sed commands if needed
