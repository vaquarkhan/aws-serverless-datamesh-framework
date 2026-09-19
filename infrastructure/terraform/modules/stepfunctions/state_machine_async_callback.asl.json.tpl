{
  "Comment": "Serverless Data Mesh: async Event + waitForTaskToken (LMI segments up to 90 min)",
  "StartAt": "InitializeRetryCounter",
  "States": {
    "InitializeRetryCounter": {
      "Type": "Pass",
      "Parameters": {
        "workload.$": "$",
        "resume_attempt": 0
      },
      "ResultPath": "$",
      "Next": "InvokeDomainWriter"
    },
    "InvokeDomainWriter": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke.waitForTaskToken",
      "TimeoutSeconds": ${lambda_invoke_timeout_seconds},
      "HeartbeatSeconds": ${heartbeat_seconds},
      "Parameters": {
        "FunctionName": "${lambda_qualified_arn}",
        "InvocationType": "Event",
        "Payload": {
          "task_token.$": "$$.Task.Token",
          "workload.$": "$.workload",
          "resume_attempt.$": "$.resume_attempt"
        }
      },
      "ResultPath": "$.result",
      "Retry": [
        {
          "ErrorEquals": [
            "Lambda.ServiceException",
            "Lambda.AWSLambdaException",
            "Lambda.SdkClientException"
          ],
          "IntervalSeconds": 5,
          "MaxAttempts": 3,
          "BackoffRate": 2.0
        }
      ],
      "Next": "RouteOutcome"
    },
    "RouteOutcome": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.result.outcome",
          "StringEquals": "committed",
          "Next": "Success"
        },
        {
          "Variable": "$.result.outcome",
          "StringEquals": "resumed",
          "Next": "Success"
        },
        {
          "Variable": "$.result.outcome",
          "StringEquals": "rolled_back",
          "Next": "IncrementResumeAttempt"
        },
        {
          "Variable": "$.result.outcome",
          "StringEquals": "verification_failed",
          "Next": "VerificationFailed"
        }
      ],
      "Default": "UnknownFailure"
    },
    "IncrementResumeAttempt": {
      "Type": "Pass",
      "Parameters": {
        "workload.$": "$.workload",
        "resume_attempt.$": "States.MathAdd($.resume_attempt, 1)",
        "result.$": "$.result"
      },
      "Next": "CheckResumeLimit"
    },
    "CheckResumeLimit": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.resume_attempt",
          "NumericGreaterThanEquals": ${max_resume_attempts},
          "Next": "ResumeLimitExceeded"
        }
      ],
      "Default": "WaitBeforeResume"
    },
    "WaitBeforeResume": {
      "Type": "Wait",
      "Seconds": ${resume_wait_seconds},
      "Next": "InvokeDomainWriter"
    },
    "Success": {
      "Type": "Succeed"
    },
    "VerificationFailed": {
      "Type": "Fail",
      "Error": "VerificationFailed",
      "Cause": "VRP validate-then-commit blocked metadata commit. Inspect proof artifacts in S3."
    },
    "ResumeLimitExceeded": {
      "Type": "Fail",
      "Error": "ResumeLimitExceeded",
      "Cause": "IceGuard rollback resume loop exceeded max attempts. Check Lambda timeout pressure."
    },
    "UnknownFailure": {
      "Type": "Fail",
      "Error": "UnknownOutcome",
      "Cause": "Domain writer returned an unrecognized outcome."
    }
  }
}
