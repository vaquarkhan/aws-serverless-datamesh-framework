#!/usr/bin/env bash
# Build Lambda deployment package for Terraform.
# Usage: ./infrastructure/terraform/scripts/package_lambda.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
BUILD_DIR="${ROOT}/infrastructure/terraform/build"
PACKAGE="${BUILD_DIR}/domain-writer.zip"
STAGING="${BUILD_DIR}/staging"
EXTRAS="${SDM_EXTRAS:-}"

echo "==> Building Lambda package (extras=${EXTRAS:-core})"
rm -rf "${STAGING}" "${PACKAGE}"
mkdir -p "${STAGING}"

python -m pip install --upgrade pip >/dev/null

INSTALL_SPEC="${ROOT}"
if [ -n "${EXTRAS}" ]; then
  INSTALL_SPEC="${ROOT}[${EXTRAS}]"
fi

python -m pip install "${INSTALL_SPEC}" \
  --target "${STAGING}" \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  --upgrade 2>/dev/null || \
python -m pip install "${INSTALL_SPEC}" --target "${STAGING}" --upgrade

cp -r "${ROOT}/examples" "${STAGING}/examples"

cd "${STAGING}"
# Remove test/metadata noise to shrink package
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.dist-info" -prune -o -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true

zip -r "${PACKAGE}" . -x "*.pyc" "*/tests/*" "*/__pycache__/*" >/dev/null

echo "==> Package ready: ${PACKAGE}"
echo "    Size: $(du -h "${PACKAGE}" | cut -f1)"
