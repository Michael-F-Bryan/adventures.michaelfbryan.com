# Michael's Adventures

(**[Published](http://adventures.michaelfbryan.com/) | [Staging](https://staging.adventures.michaelfbryan.com/)**)

A simple blog for documenting my thoughts and adventures.

## Getting Started

This blog uses the [Hugo][hugo] static site generator. You'll need
to [install it][install-hugo] before anything else.

During development you'll want to use the dev server to see changes the moment
they're made.

```console
hugo server --buildDrafts --buildExpired --buildFuture
```

This should start a HTTP server on http://localhost:1313/ that serves the site,
recompiling on every change.

### Staging

Whenever you push a new commit to GitHub, GitHub Actions are wired up so the
commit will be compiled and uploaded to the staging site (linked above). This
lets you view the blog as a normal user would (e.g. so you can send a link to
your editor).

This deliberately overwrites everything that was previously on the staging
site.

The staging environment is backed by *Google Cloud*, with the website itself
stored in a *Google Storage* bucket and served up by a HTTPS proxy.

The staging environment is provisioned using Terraform and the `Terraform`
service account.

To re-provision the environment you will need to save service account
credentials to `terraform/terraform-service-account-key.json` and make sure the
account has the following roles:

- Compute Network Admin
- Compute Security Admin
- Storage Admin

From there you can set the `GOOGLE_APPLICATION_CREDENTIALS` environment
variable.

```bash
export GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/terraform/terraform-service-account-key.json
```

You can view the Terraform plan with `make plan`, and execute that plan
(provisioning cloud resources) using `make apply`.

This step may take a couple seconds.

### Deployment

The real site is published to GitHub Pages on every commit to the `master`
branch.

This should all be handled by GitHub Actions automatically.

[install-hugo]: https://gohugo.io/getting-started/installing/
[hugo]: https://gohugo.io/
