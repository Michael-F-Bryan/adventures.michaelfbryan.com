# Michael's Adventures

(**[Rendered](http://adventures.michaelfbryan.com/)**)

A simple blog for documenting my thoughts and adventures.

## Getting Started

This blog uses the [Hugo][hugo] static site generator. You'll need
to [install it][install-hugo] before anything else.

During development you'll want to use the dev server to see changes the moment
they're made.

```console
hugo server --buildDrafts
```

Before deploying, make sure you've compiled the site using the `production`
environment.

```console
hugo --environment production
```

Then deploy it to the `adventures.michaelfbryan.com` S3 bucket using:

```console
hugo deploy --environment production
```

[install-hugo]: https://gohugo.io/getting-started/installing/
[hugo]: https://gohugo.io/