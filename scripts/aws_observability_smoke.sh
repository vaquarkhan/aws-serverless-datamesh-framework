#!/usr/bin/env bash
# Post-deploy observability smoke checks (run before terraform destroy).
set -euo pipefail

PREFIX="${SDM_NAME_PREFIX:-sdm-prod}"
REGION="${AWS_REGION:-us-east-2}"
FUNCTION="${SDM_LAMBDA_FUNCTION:-${PREFIX}-domain-writer}"
LOG_GROUP="/aws/lambda/${FUNCTION}"
DLQ_NAME="${PREFIX}-domain-writer-dlq"

echo "==> CloudWatch log group: ${LOG_GROUP}"
aws logs describe-log-groups --log-group-name-prefix "${LOG_GROUP}" --region "${REGION}" \
  --query 'logGroups[0].logGroupName' --output text

echo "==> Recent pvdm_outcome lines (wait 30s after invoke if empty)"
aws logs filter-log-events \
  --log-group-name "${LOG_GROUP}" \
  --filter-pattern '{ $.event = "pvdm_outcome" }' \
  --limit 5 \
  --region "${REGION}" \
  --query 'events[*].message' --output text || true

echo "==> VRP custom metrics namespace"
aws cloudwatch list-metrics \
  --namespace "ServerlessDataMesh/Trust" \
  --region "${REGION}" \
  --query 'Metrics[0].MetricName' --output text || true

echo "==> DLQ depth"
aws sqs get-queue-attributes \
  --queue-url "$(aws sqs get-queue-url --queue-name "${DLQ_NAME}" --region "${REGION}" --query QueueUrl --output text)" \
  --attribute-names ApproximateNumberOfMessages \
  --region "${REGION}"

echo "==> Dashboard"
aws cloudwatch list-dashboards --region "${REGION}" \
  --query "DashboardEntries[?contains(DashboardName, '${PREFIX}')].DashboardName" --output text

echo "Done. Keep stack alive 5+ minutes to confirm metrics in console."
