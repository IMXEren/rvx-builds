#!/usr/bin/sed -f

# Replace "py_file_url = ..." with a new URL
s@py_file_url = "https://raw\.githubusercontent\.com/.*@py_file_url = "https://raw.githubusercontent.com/{$1}/main/src/patches.py"@

# Replace "config_py_file_url = ..." with a new URL
s@config_py_file_url = "https://raw\.githubusercontent\.com/.*@config_py_file_url = "https://raw.githubusercontent.com/{$1}/main/src/config.py"@

# Add more sed commands if needed
