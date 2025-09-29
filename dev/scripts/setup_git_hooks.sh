#!/bin/sh
# Setup script for Git hooks
# This script configures Git to use our hooks

# Set the hooks path to our .husky directory
git config core.hooksPath .husky

echo "Git hooks have been set up successfully!"
echo "Commit message validation is now active."
