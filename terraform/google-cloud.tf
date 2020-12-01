provider "google" {
  version = "3.49.0"

  credentials = file("terraform-service-account-key.json")

  project = var.gcp_project_id
  region  = var.gcp_region
  zone    = var.gcp_zone
}

provider "google-beta" {
  version = "3.49.0"

  credentials = file("terraform-service-account-key.json")

  project = var.gcp_project_id
  region  = var.gcp_region
  zone    = var.gcp_zone
}

# The bucket used to store our rendered content
resource "google_storage_bucket" "staging" {
  name     = var.hostname
  location = var.gcp_region

  uniform_bucket_level_access = true
  force_destroy               = true

  website {
    main_page_suffix = "index.html"
    not_found_page   = "404.html"
  }
}

# Create a policy that gives all users read-only access
resource "google_storage_bucket_iam_binding" "readonly" {
  bucket = google_storage_bucket.staging.name
  role   = "roles/storage.objectViewer"
  members = [
    "allUsers",
  ]
}

# We want to set up a load balancer backed by the staging bucket

resource "google_compute_backend_bucket" "staging_backend" {
  name        = "staging-backend-bucket"
  bucket_name = google_storage_bucket.staging.name
  enable_cdn  = true
}

# We need a URL map for our proxy rules
resource "google_compute_url_map" "default" {
  name            = "url-map-${var.gcp_project_id}"
  default_service = google_compute_backend_bucket.staging_backend.self_link
}

# Add a global forwarding rule to the URL map
resource "google_compute_global_forwarding_rule" "https_endpoint" {
  name       = "cdn-global-forwarding-https-rule"
  target     = google_compute_target_https_proxy.https_proxy.self_link
  ip_address = google_compute_global_address.cdn_public_address.address
  port_range = "443"
}

# Issue ourselves a SSL certificate managed by Google
resource "google_compute_managed_ssl_certificate" "cdn_certificate" {
  provider = google-beta

  name = "cdn-managed-certificate"

  managed {
    domains = [var.hostname]
  }
}

# Create a HTTPS proxy
resource "google_compute_target_https_proxy" "https_proxy" {
  name             = "cdn-https-proxy"
  url_map          = google_compute_url_map.default.self_link
  ssl_certificates = [google_compute_managed_ssl_certificate.cdn_certificate.self_link]
}

# Our HTTPS proxy needs a public IP address
resource "google_compute_global_address" "cdn_public_address" {
  name         = "cdn-public-address"
  ip_version   = "IPV4"
  address_type = "EXTERNAL"
}
