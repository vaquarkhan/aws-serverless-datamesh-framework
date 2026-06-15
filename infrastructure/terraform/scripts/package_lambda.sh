#!/usr/bin/env bash
# Build Lambda deployment package for Terraform.
# Usage: ./infrastructure/terraform/scripts/package_lambda.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
BUILD_DIR="${ROOT}/infrastructure/terraform/build"
PACKAGE="${BUILD_DIR}/domain-writer.zip"
STAGING="${BUILD_DIR}/staging"
EXTRAS="${SDM_EXTRAS:-}"
PIPELINE_SRC="${SDM_PIPELINE_SRC:-}"

echo "==> Building Lambda package (extras=${EXTRAS:-core}, pipeline=${PIPELINE_SRC:-platform})"
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

cp "${ROOT}/VERSION" "${STAGING}/VERSION"
if [ -d "${STAGING}/serverless_data_mesh" ]; then
  cp "${ROOT}/VERSION" "${STAGING}/serverless_data_mesh/VERSION"
fi

if [ -n "${PIPELINE_SRC}" ]; then
  echo "==> Overlaying compiled pipeline from ${PIPELINE_SRC}"
  for f in handler.py readers.py pipeline_config.py; do
    if [ -f "${PIPELINE_SRC}/${f}" ]; then
      cp "${PIPELINE_SRC}/${f}" "${STAGING}/${f}"
    fi
  done
else
  cp -r "${ROOT}/examples" "${STAGING}/examples"
fi

cd "${STAGING}"
# Remove test/metadata noise to shrink package
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.dist-info" -prune -o -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true

zip -r "${PACKAGE}" . -x "*.pyc" "*/tests/*" "*/__pycache__/*" >/dev/null

echo "==> Package ready: ${PACKAGE}"
echo "    Handler: ${SDM_LAMBDA_HANDLER:-$([ -n "${PIPELINE_SRC}" ] && echo handler.lambda_handler || echo examples.domain_writer.handler.lambda_handler)}"
echo "    Size: $(du -h "${PACKAGE}" | cut -f1)"
