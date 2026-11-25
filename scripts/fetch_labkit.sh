#!/usr/bin/env bash
# Reproduce the read-only upstream reference snapshot (StepExample + LICENSE)
# from a pinned commit. Reference material only, not project firmware.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ref="$root/references"
repo='https://github.com/rmorenoga/LabAutomationKits.git'
commit='a22a6b981e1f0cfd5d0311b571e7998846d37a7d'
subdir='Electronics/Firmware/StepExample'
target="$ref/LabAutomationKits"
commit_file="$ref/LabAutomationKits.commit.txt"
if [[ -e "$target" || -e "$commit_file" ]]; then
  printf 'Refusing to overwrite existing reference material: %s or %s\n' "$target" "$commit_file" >&2
  exit 1
fi
mkdir -p "$ref"
work=$(mktemp -d "$ref/.labkit-fetch.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
# Authentication, if required, is handled by the user's existing Git configuration.
git init -q "$work/checkout"
git -C "$work/checkout" fetch -q --depth 1 "$repo" "$commit"
[[ "$(git -C "$work/checkout" rev-parse FETCH_HEAD)" == "$commit" ]] || { echo 'Fetched commit does not match the pinned commit; no reference installed.' >&2; exit 1; }
mkdir "$work/snapshot"
git -C "$work/checkout" archive FETCH_HEAD LICENSE "$subdir" | tar -xf - -C "$work/snapshot"
[[ -d "$work/snapshot/$subdir" ]] || { echo 'Expected StepExample directory is missing; no reference installed.' >&2; exit 1; }
# Retain upstream files and their license unchanged; no nested Git repository.
mv -- "$work/snapshot" "$target"
printf '%s\n' "$commit" > "$commit_file"
printf 'Installed reference snapshot: %s\nCommit: %s\n' "$target" "$commit"
printf 'Review %s before WP01. Do not flash or operate hardware automatically.\n' "$subdir"
