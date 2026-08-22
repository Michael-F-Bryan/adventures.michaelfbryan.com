#!/usr/bin/env bash
#
# Builds this site on Vercel.
#
# Adapted from Hugo's official Vercel guide, so it stays easy to re-diff:
# https://gohugo.io/host-and-deploy/host-on-vercel/
#
# To upgrade Hugo, change HUGO_VERSION below, then set the same version in
# .github/workflows/main.yml so CI builds exactly what production builds.
# That is the only step. Vercel has no Hugo version configured in its
# dashboard, on purpose -- an invisible setting there once drifted to 0.145
# and silently disabled our Mermaid diagrams.

# Exit on error, undefined variables, or pipe failures
set -euo pipefail

# Define tool versions
HUGO_VERSION=0.165.0

# Set the build time zone
TZ=Australia/Perth

# Set the build cache directory (Vercel persists .vercel/cache between builds)
HUGO_CACHEDIR="${PWD}/.vercel/cache/hugo"

# Perform cleanup
cleanup() {
  if [[ -n "${build_temp_dir:-}" && -d "${build_temp_dir}" ]]; then
    rm -rf "${build_temp_dir}"
  fi
}

# Register the cleanup trap
trap cleanup EXIT SIGINT SIGTERM

main() {
  # Export the build time zone
  export TZ

  # Export the build cache directory
  export HUGO_CACHEDIR

  # Create a temporary directory for downloads
  build_temp_dir=$(mktemp -d)

  # Install Hugo. The theme compiles SCSS through toCSS without selecting a
  # transpiler, which uses the embedded LibSass, so the "extended" build is
  # required -- the plain build fails on the theme's stylesheets.
  echo "Installing Hugo ${HUGO_VERSION} (extended)..."
  curl -sfL --output-dir "${build_temp_dir}" -O \
    "https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_linux-amd64.tar.gz"
  mkdir -p "${HOME}/.local/hugo"
  tar -C "${HOME}/.local/hugo" -xf "${build_temp_dir}/hugo_extended_${HUGO_VERSION}_linux-amd64.tar.gz"
  export PATH="${HOME}/.local/hugo:${PATH}"

  # Log tool versions, so the build log always records what actually ran
  echo "Logging tool versions..."
  hugo version

  # Configure Git
  echo "Configuring Git..."
  git config --global core.quotepath false

  # Fetch full Git history. config.toml sets enableGitInfo, and the theme
  # footer links each page to the commit that last changed it. Vercel clones
  # shallow, which makes every older post point at the wrong commit.
  if [[ $(git rev-parse --is-shallow-repository) == true ]]; then
    echo "Fetching full Git history..."
    git fetch --unshallow
  fi

  # Initialize Git submodules (themes/hugo-coder)
  if [[ -f .gitmodules ]]; then
    echo "Initializing Git submodules..."
    git submodule update --init --recursive
  fi

  # Build the project. No -D: the repo has draft posts that must stay unpublished.
  echo "Building the project..."
  hugo build --gc --minify
}

main "$@"
