terraform {
  backend "gcs" {
    bucket = "terraform.adventures.michaelfbryan.com"
    prefix = "/state"
  }

  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "1.22.2"
    }

    google = {
      source = "hashicorp/google"
    }
  }
}
