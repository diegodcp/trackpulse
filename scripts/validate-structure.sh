#!/usr/bin/env bash
set -euo pipefail

required_paths=(
  "README.md"
  ".gitignore"
  ".editorconfig"
  ".env.example"
  "Makefile"
  "apps/web/README.md"
  "apps/api/README.md"
  "apps/workers/README.md"
  "packages/test-fixtures"
  "infra/docker-compose.yml"
  ".github/PULL_REQUEST_TEMPLATE.md"
  ".github/ISSUE_TEMPLATE_task.md"
)

missing=0
for path in "${required_paths[@]}"; do
  if [[ ! -e "$path" ]]; then
    echo "Missing required path: $path"
    missing=1
  fi
done

if [[ "$missing" -ne 0 ]]; then
  echo "Structure validation failed."
  exit 1
fi

echo "Structure validation passed."
