provider "digitalocean" {
  token = var.do_token
}

data "digitalocean_domain" "default" {
  name = "michaelfbryan.com"
}

resource "digitalocean_record" "staging" {
  domain = data.digitalocean_domain.default.name
  type   = "A"
  name   = "staging.adventures"
  value  = google_compute_global_address.cdn_public_address.address
}
