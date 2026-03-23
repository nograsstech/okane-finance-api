#!/usr/bin/env bash
# Configure git to use the project's hooks directory
set -e

git config core.hooksPath .githooks
echo "Git hooks configured. Pre-push hook will run tests before each push."
