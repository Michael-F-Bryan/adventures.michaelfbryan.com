# Michael's Adventures

(**[Published](http://adventures.michaelfbryan.com/)**)

A simple blog for documenting my thoughts and experiments.

## Getting Started

This blog uses the [Hugo][hugo] static site generator. You'll need to
[install it][install-hugo] before anything else.

During development you'll want to use the dev server to see changes the
moment they're made.

```console
hugo server --buildDrafts --buildExpired --buildFuture
```

This should start a HTTP server on http://localhost:1313/ that serves the site,
recompiling on every change.

## Custom Short-Codes and Templates

You can customise whether a page should receive the *"I've written a long
article but you don't need to read it all in one hit, here's a table of
contents"* message.

The logic goes something like this:

```python
def should_show_toc():
    if "toc" in frontMatter:
        return frontMatter["toc"]
    else:
        return page.readingTime > Site.Params.toc_reading_time_threshold
```

### Deployment

The real site is published to GitHub Pages on every commit to the `master`
branch.

This should all be handled by GitHub Actions automatically.

[install-hugo]: https://gohugo.io/getting-started/installing/
[hugo]: https://gohugo.io/
