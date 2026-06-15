variable "name_prefix" {
  type = string
}

variable "state_machine_arn" {
  type = string
}

variable "schedule_expression" {
  type    = string
  default = "cron(0 2 * * ? *)"
}

variable "schedule_enabled" {
  type    = bool
  default = false
}

variable "default_workload_payload" {
  type    = string
  default = <<-JSON
    {
      "workload_id": "scheduled-backfill",
      "total_records": 1000,
      "domain_id": "orders-domain"
    }
  JSON
}

variable "tags" {
  type    = map(string)
  default = {}
}
