#!/usr/bin/env bash
set -euo pipefail

required_files=(
  "docs/planning/batch-migration-wave.md"
  "docs/planning/issue-news-batch.md"
  "docs/planning/issue-fresh-food-batch.md"
  "docs/planning/issue-global-intel-batch.md"
  "jobs/news/contract.md"
  "jobs/fresh-food/contract.md"
  "jobs/global-intel/contract.md"
  "manifests/batch-jobs.shadow.example.yaml"
)

required_terms=(
  "Inputs"
  "Outputs"
  "Schedule"
  "Model"
  "SecretRef"
  "GUI/Login Dependency"
  "Shadow Validation"
  "Duplicate Prevention"
  "Cutover"
  "Rollback"
  "Completion Evidence"
)

for file in "${required_files[@]}"; do
  test -f "$file"
done

for file in docs/planning/issue-*-batch.md jobs/*/contract.md; do
  for term in "${required_terms[@]}"; do
    grep -q "$term" "$file"
  done
done

grep -q "enabled: false" manifests/batch-jobs.shadow.example.yaml
grep -q "publish: false" manifests/batch-jobs.shadow.example.yaml
grep -q "productionDestinations: false" manifests/batch-jobs.shadow.example.yaml

if grep -RInE '(token|password|secret|api[_-]?key)[=:][[:space:]]*[^[:space:]<>{}#]+' \
  docs/planning manifests maintenance-scripts; then
  echo "Potential inline secret assignment detected" >&2
  exit 1
fi

echo "batch contract validation passed"
