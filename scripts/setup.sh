#!/usr/bin/env bash
set -euo pipefail

pnpm install
pnpm run setup:env
pnpm run setup:db
