#!/bin/bash

# Commit and push changes
commit_message="${1:-Add generated files}"
git config --global user.name "actions-user"
git config --global user.email "actions@github.com"
git add .
git commit -m "$commit_message"
git push
