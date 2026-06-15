#!/usr/bin/env bash
# Verify DLQ receives failed async Lambda invocations (not handled error payloads).
# Prerequisite: Lambda with timeout=60 and event_invoke_config → DLQ wired.
set -euo pipefail

FUNCTION="${SDM_LAMBDA_ARN:?Set SDM_LAMBDA_ARN to qualified :live ARN}"
DLQ_URL="${SDM_DLQ_URL:?Set SDM_DLQ_URL}"

echo "==> Invoking Lambda with crash payload (unhandled exception → DLQ)"
aws lambda invoke \
  --function-name "${FUNCTION}" \
  --invocation-type Event \
  --payload '{"__crash": true, "workload_id": "dlq-test", "total_records": 1}' \
  /tmp/sdm-dlq-invoke.json || true

echo "Wait 90s for timeout + DLQ routing..."
sleep 90

COUNT=$(aws sqs get-queue-attributes \
  --queue-url "${DLQ_URL}" \
  --attribute-names ApproximateNumberOfMessages \
  --query 'Attributes.ApproximateNumberOfMessages' --output text)

echo "DLQ messages: ${COUNT}"
if [ "${COUNT}" = "0" ]; then
  echo "WARN: DLQ empty — ensure payload triggers unhandled crash/timeout, not caught VerificationRejectedError"
  exit 1
fi
