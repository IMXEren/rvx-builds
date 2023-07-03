#!/usr/bin/sed -f

echo "File $1"
echo .
echo "Repo $2"

# Replace "py_file_url = ..." with a new URL
s@py_file_url = "https://raw\.githubusercontent\.com/.*@py_file_url = "https://raw.githubusercontent.com/${{ github.repository }}/main/src/patches.py"@

# Replace "config_py_file_url = ..." with a new URL
s@config_py_file_url = "https://raw\.githubusercontent\.com/.*@config_py_file_url = "https://raw.githubusercontent.com/${{ github.repository }}/main/src/config.py"@

# Add more sed commands if needed
