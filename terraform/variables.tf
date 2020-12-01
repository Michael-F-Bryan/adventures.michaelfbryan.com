variable "hostname" { type = string }
variable "gcp_project_id" { type = string }
variable "gcp_region" { type = string }
variable "gcp_zone" { type = string }
variable "do_token" { type = string }

variable "gcp_credentials" {
  type    = string
  default = null
}

output "static_ip" {
  value = google_compute_global_address.cdn_public_address.address
}
