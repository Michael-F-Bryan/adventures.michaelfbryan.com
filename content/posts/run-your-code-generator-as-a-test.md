---
title: Run Your Code Generator as a Test
date: '2026-08-23T18:00:00+08:00'
draft: true
description: Generated code can give a project a much nicer interface, but it also introduces another maintenance step. This article shows the test pattern I use to keep generated files aligned with their source, catch manual edits, and leave every change available for review.
tags:
- Go
- Testing
- Code Generation
- OpenAPI
---

At some point in a project's life, somebody runs a code generator. Maybe they point a client generator at an OpenAPI document, or feed a `.proto` file to `protoc`, or write a small script that turns a config file into a lookup table. The output is genuinely useful, so it gets committed, and the project's interfaces improve overnight. Then, being diligent, the author adds a line to the README: *"After changing the schema, re-run `make generate` and commit the result."*

That sentence is where the trouble starts. The project now contains two representations of the same information, an authoritative one and a derived one, and the only thing keeping them consistent is a human remembering to run a command.

I've used a pattern for years that removes the remembering: run the generator from the test suite, compare its output against what's checked in, repair any difference, and fail the test so the change still gets reviewed. It's a small amount of code, it works with any deterministic generator, and once it's in place the derived code simply can't drift without CI telling you about it. This article walks through the two helpers that make it work, a complete worked example that generates a Go client from a running web application, and the costs you accept by adopting it.

## The Command Somebody Has to Remember

A one-off generation is fine on the day it happens. The generated code matches its source because both were touched in the same sitting, and everybody involved still remembers how the pieces fit together. The problem is that projects evolve, and the moment either side can change, the derivation can rot in two different directions.

The first direction is the obvious one: the authoritative input changes and nobody re-runs the generator. The API grows an endpoint, the schema gains a column, the config file gets a new entry, and the generated code keeps describing the old world. Nothing fails at the time. The mismatch surfaces weeks later as a runtime error, or as a confused developer wondering why the field they can see in the schema doesn't exist on the generated type.

The second direction is sneakier. Somebody needs a small change, notices it would be quickest to make it in the generated file, and patches it directly. The patch works, it gets committed, and it quietly becomes load-bearing. Months later somebody else re-runs the generator for an unrelated reason and the patch evaporates, usually without anyone noticing until whatever depended on it breaks.

Both failures have the same root cause. Re-running the generator is a task that is almost always redundant; 99% of the time the output wouldn't change, so there's no feedback loop teaching anyone to do it. Humans are bad at remembering rarely-needed chores, and a README can document the command but can't make anyone run it. If keeping two representations consistent matters, the check needs to be executable, and the natural place for an executable check is the test suite. CI already runs it, and every developer already knows what a red test means.

## Run the Generator From a Test

The idea isn't mine. Matklad's [Self Modifying Code][self-modifying-code] describes a test that reads its own source file, derives some generated text from another region of the code, splices it between a pair of markers, writes the file back if anything changed, and then fails so the developer commits the update. The generator stays a simple string-manipulating function, consumers see ordinary source code with normal navigation and debugging, and freshness is enforced every time the tests run.

Matklad's version rewrites a region inside one file. Most of the generators I work with produce whole files, or whole directory trees, so I've generalised the same move into two helpers: one that reconciles a single file, and one that reconciles a directory the generator owns outright. The examples here are Go, but there's nothing Go-specific about the idea; I've used the same helpers in Python and Rust projects.

### `EnsureFileContents()`

Here's the single-file helper in full.

```go
// EnsureFileContents makes sure the file at path contains exactly contents.
//
// If the file already matches, EnsureFileContents returns without touching
// anything. Otherwise it creates any missing parent directories, writes
// contents to path, and fails the test so the resulting change has to be
// inspected, committed, and the test rerun before it can pass again.
func EnsureFileContents(t *testing.T, path string, contents []byte) {
	t.Helper()

	if existing, err := os.ReadFile(path); err == nil && bytes.Equal(existing, contents) {
		return
	} else if err != nil && !os.IsNotExist(err) {
		t.Fatalf("unable to read %s: %v", path, err)
	}

	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("unable to create directory for %s: %v", path, err)
	}
	if err := os.WriteFile(path, contents, 0o644); err != nil {
		t.Fatalf("unable to write %s: %v", path, err)
	}

	t.Errorf("%s was out of date and has been updated in place; inspect the diff, commit it, and rerun this test", path)
}
```

A test that uses it derives the expected output however it likes (running a template, shelling out to a CLI, reflecting over some types) and then makes one call:

```go
func TestLookupTableIsUpToDate(t *testing.T) {
	generated := generateLookupTable()
	EnsureFileContents(t, "lookup_table.go", generated)
}
```

The behaviour on drift looks strange the first time you see it: the helper *fixes* the file and then fails anyway. Why not just fix it and pass, or fail without touching anything?

Because each half of that behaviour serves a different audience. Writing the file means a developer who runs the test locally is left with the correct output sitting in their working tree, as a concrete diff they can read in their usual tools, rather than a wall of "expected X, got Y" output and a chore still ahead of them. Failing the test means CI can never go green on a commit whose generated code didn't match its source, because CI's rewritten file is thrown away with the build machine. The failure message tells the developer exactly what happened and what to do next: inspect the diff, commit it, rerun. On the second run the file already matches and the test passes. Every regeneration therefore passes through a human and through code review, exactly like a handwritten change would.

### `AssertFileTreeMatches()`

Generators like [`ogen`][ogen] or `sqlc` emit a directory full of files, and a single-file comparison isn't enough: files can change, appear, or stop being generated at all. The tree-level helper reconciles a whole directory against the freshly generated output.

```go
// AssertFileTreeMatches reconciles targetDir so it contains exactly the
// files found under expectedDir.
//
// Changed or missing files are written into targetDir. Files that exist
// under targetDir but have no counterpart under expectedDir are deleted.
// targetDir is therefore treated as wholly owned by the generator: a
// handwritten file left in that directory will be removed the next time
// this runs.
//
// As with EnsureFileContents, any repair still fails the test so the
// resulting diff gets reviewed before it is trusted.
func AssertFileTreeMatches(t *testing.T, expectedDir, targetDir string) {
	t.Helper()

	expected := readTree(t, expectedDir)
	actual := readTree(t, targetDir)

	for relPath, contents := range expected {
		targetPath := filepath.Join(targetDir, relPath)
		previous, existed := actual[relPath]
		if existed && bytes.Equal(previous, contents) {
			continue
		}

		if err := os.MkdirAll(filepath.Dir(targetPath), 0o755); err != nil {
			t.Fatalf("unable to create directory for %s: %v", targetPath, err)
		}
		if err := os.WriteFile(targetPath, contents, 0o644); err != nil {
			t.Fatalf("unable to write %s: %v", targetPath, err)
		}

		if existed {
			t.Errorf("%s had drifted from the generated output and has been overwritten; inspect the diff, commit it, and rerun this test", targetPath)
		} else {
			t.Errorf("%s was missing from %s and has been created; inspect the diff, commit it, and rerun this test", targetPath, targetDir)
		}
	}

	for relPath := range actual {
		if _, stillExpected := expected[relPath]; stillExpected {
			continue
		}

		targetPath := filepath.Join(targetDir, relPath)
		if err := os.Remove(targetPath); err != nil {
			t.Fatalf("unable to remove stale generated file %s: %v", targetPath, err)
		}
		t.Errorf("%s is no longer part of the generated output and has been deleted; inspect the diff, commit it, and rerun this test", targetPath)
	}

	pruneEmptyDirs(targetDir)
}
```

{{% expand "The file-walking helpers" %}}

```go
// readTree walks dir and returns its file contents keyed by path relative to
// dir. A missing dir is treated as an empty tree so the first run of
// AssertFileTreeMatches against a not-yet-created target directory works.
func readTree(t *testing.T, dir string) map[string][]byte {
	t.Helper()

	files := make(map[string][]byte)
	err := filepath.WalkDir(dir, func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() {
			return nil
		}
		rel, err := filepath.Rel(dir, path)
		if err != nil {
			return err
		}
		contents, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		files[rel] = contents
		return nil
	})
	if err != nil && !os.IsNotExist(err) {
		t.Fatalf("unable to walk %s: %v", dir, err)
	}
	return files
}

// pruneEmptyDirs removes directories left empty by deleted files, so a
// generator that stops emitting a subdirectory does not leave it behind.
func pruneEmptyDirs(dir string) {
	var dirs []string
	_ = filepath.WalkDir(dir, func(path string, entry fs.DirEntry, err error) error {
		if err != nil || !entry.IsDir() || path == dir {
			return nil
		}
		dirs = append(dirs, path)
		return nil
	})
	// Remove deepest directories first so nested empty parents collapse too.
	for i := len(dirs) - 1; i >= 0; i-- {
		_ = os.Remove(dirs[i]) // no-op unless the directory is now empty
	}
}
```

{{% /expand %}}

The deletion pass is what makes this helper genuinely different from calling `EnsureFileContents()` in a loop, and it's also where the sharpest edge lives. Because stale files get removed, the target directory has to be *wholly owned* by the generator. A handwritten file dropped into that directory will survive exactly until the next test run. That's a boundary worth establishing deliberately: generated output goes in its own directory, handwritten code lives elsewhere, and the directory's ownership is obvious from its name or a README inside it.

With both helpers in hand, the overall contract is worth spelling out once. The authoritative input (the schema, the migrations, the grammar) remains the only place where intentional changes happen. The test regenerates the derived code exactly and compares it byte-for-byte, which catches both drift directions from earlier: stale output when the source changed, and manual edits to the output itself. And because the output is checked in rather than produced at build time, everyone downstream still gets the good parts of committed code: jump-to-definition, autocomplete, docs rendered from the source, diffs that show up in review, and no requirement that every consumer has the generator toolchain installed.

## Generate a Client From a Running API

To show the whole pattern working end to end, I want a generator that somebody would actually use, against a source of truth that actually changes. Generating an API client from a real application's OpenAPI document fits both requirements, so the worked example uses [Mealie][mealie], a self-hosted recipe manager and meal planner with a FastAPI backend. Mealie ships as a single container, publishes versioned images, and serves a live OpenAPI 3.1 document from `/openapi.json`. It's standing in for whatever service your project consumes; the interesting part is the derivation, not the recipes.

The test we're building does the following, every time the suite runs:

1. start the pinned Mealie release in Docker and wait for it to come up;
2. fetch its OpenAPI document and normalise it into a stable form;
3. reconcile the vendored copy of the schema with `EnsureFileContents()`;
4. run a pinned version of `ogen` over the vendored schema, into a temporary directory; and
5. reconcile the checked-in client tree with `AssertFileTreeMatches()`.

Here's the test itself, which is short enough to read in one go:

```go
func TestMealieClientIsUpToDate(t *testing.T) {
	if testing.Short() {
		t.Skip("starts a Docker container; skipped in -short mode")
	}

	baseURL := startMealie(t)

	raw := fetchOpenAPI(t, baseURL)
	normalised, stats := normaliseOpenAPI(t, raw)
	t.Logf("normalisation: %s", stats)

	schemaPath := filepath.Join("schema", "openapi.json")
	codegen.EnsureFileContents(t, schemaPath, normalised)

	generatedDir := runOgen(t, schemaPath)
	codegen.AssertFileTreeMatches(t, generatedDir, "client")
}
```

One design decision is invisible in that listing but important: this test never imports the generated client. If a bad schema ever produces a client that doesn't compile, a test that imported it couldn't build either, and the one tool capable of regenerating a working client would be broken by the very problem it exists to fix. Keeping the codegen test free of dependencies on its own output preserves the repair path.

### Capture the API Description

The container setup is ordinary `os/exec` plumbing around Docker, so I'll show the parts that carry decisions and describe the rest. The image is pinned by both tag and digest, which makes the test's answer to "which version of the API are we generating against?" exact:

```go
// pinnedImage is the exact Mealie release under test, pinned by tag and
// digest so the worked example always exercises the same server.
const pinnedImage = "ghcr.io/mealie-recipes/mealie:v3.23.1@sha256:5fc5cebedddb3952c1ee78f20faf42ab7e49986813fd314745aa97978a4a13eb"

func startMealie(t *testing.T) (baseURL string) {
	t.Helper()

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	runCmd := exec.CommandContext(ctx, "docker", "run",
		"--detach",
		"--publish", "127.0.0.1::9000", // let docker pick a free host port
		"--rm",
		pinnedImage,
	)
	// ... capture the container ID, register a t.Cleanup() that force-removes
	// the container, ask `docker port` which ephemeral host port was bound,
	// and poll GET /api/app/about until Mealie answers (60s deadline).
}
```

Publishing onto a Docker-assigned ephemeral port means two copies of the test can run at once without fighting over a port number, and `t.Cleanup` removes the container even when the test fails. Readiness is a polling loop against `GET /api/app/about`, which conveniently also reports the running application's version, so the test log records which release actually answered.

Fetching `/openapi.json` is a plain HTTP GET. Vendoring the response verbatim doesn't work, though, and the reasons are worth separating carefully because they're two different problems that are easy to blur together.

The first problem is a generator capability gap. `ogen` v1.24.0 can't generate code for a handful of OpenAPI features that Mealie's document happens to use, most notably object-valued `default` values (23 of them). That's handled entirely in `ogen`'s own config file, without touching the JSON:

```yaml
# ogen.yml
generator:
  # ogen v1.24.0 rejects three shapes present in Mealie v3.23.1's OpenAPI
  # document: object-valued "default" values, a couple of complex "anyOf"
  # schemas, and one pair of sum-type variants that share a generated name.
  # Naming them here (rather than "all") means a future ogen upgrade that
  # implements one of these will start failing loudly instead of silently
  # widening what gets skipped.
  ignore_not_implemented:
    - "object defaults"
    - "complex anyOf"
    - "sum types with same names"
```

The second problem is determinism, and it lives in the document itself. Two of Mealie's schema properties embed a `default` that FastAPI computed at the moment the server process built its schema: the current wall-clock time, down to the microsecond. Fetch the document from two freshly started containers and you get two byte-different schemas even though nothing about the API changed. The normalisation step strips any string default shaped like an RFC 3339 timestamp, on the reasoning that a default which looks like a wall-clock instant didn't come from the schema author. It then re-encodes the whole document with Go's `encoding/json`, which sorts object keys and indents consistently, so two normalised fetches of an unchanged schema are byte-identical.

With the document stable, the `EnsureFileContents()` call in the test above vendors it as `schema/openapi.json`. The vendored schema earns its place in the repository independently of the client. It's an auditable observation of what that exact release actually serves, so when a version bump changes the API, the schema diff shows *what* changed at the contract level before you ever look at generated Go.

### Generate and Reconcile the Client

Generation runs into a fresh temporary directory rather than over the top of the checked-in client:

```go
func runOgen(t *testing.T, schemaPath string) (generatedDir string) {
	t.Helper()

	generatedDir = t.TempDir()

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	cmd := exec.CommandContext(ctx, "go", "run", "github.com/ogen-go/ogen/cmd/ogen",
		"-config", "ogen.yml",
		"-target", generatedDir,
		"-package", "mealie",
		"-clean",
		schemaPath,
	)

	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("ogen failed: %v\n%s", err, out)
	}
	return generatedDir
}
```

Two details here. Invoking `ogen` through `go run` against a `tool` directive in `go.mod` pins the generator's version the same way any other dependency is pinned, so every machine that runs this test runs the same `ogen`. And generating into `t.TempDir()` means generation either completes as a whole or fails without side effects; a generator crash can't leave the committed client half-overwritten. Only after `ogen` succeeds does the reconciliation touch the real tree:

```go
codegen.AssertFileTreeMatches(t, generatedDir, "client")
```

I'd like to say the example worked first try, but the second run of the test failed, and the failure is a better advertisement for the pattern than a clean run would have been. Mealie's document attaches `default` as a sibling of `$ref` in 52 places, and one referenced enum (`PlanEntryType`) is given *conflicting* defaults by different parents: `"breakfast"` in three places, `"dinner"` in one. `ogen` resolves that conflict in whatever order it happens to walk a map, so `oas_defaults_gen.go` genuinely flip-flopped between `PlanEntryType("dinner")` and `PlanEntryType("breakfast")` on consecutive runs. The test reported the file as drifted, overwrote it, and failed, which is exactly what it's supposed to do when generation isn't deterministic; it just found the nondeterminism in the toolchain rather than in a colleague's manual edit. The fix went into the normalisation step: drop every `default` that sits beside a `$ref`. Those siblings are legal in OpenAPI 3.1, but when four parents disagree about a referenced schema's default there is no single value that can be preserved deterministically, so for this generator those defaults carry no information worth vendoring. After that, back-to-back runs against fresh containers pass.

### Review a Version Bump

The point of all this machinery is the developer experience when something real changes, so let's walk through the intended loop. A new Mealie release comes out. You update `pinnedImage` to the new tag and digest, and run the test. It fails, reporting `schema/openapi.json` as out of date and updated in place and each client file whose generated contents changed as overwritten, with every message ending in the same instruction: inspect the diff, commit it, and rerun this test.

Your working tree now contains the updated schema and the regenerated client. `git diff` on the schema shows the new endpoints and changed models in OpenAPI terms; the client diff shows the same change as Go. You read both, commit them alongside the one-line version bump, rerun the test, and it passes. The entire cost of tracking a new upstream release is: change one constant, run one test, review one diff.

The same loop catches tampering. While testing this example I appended a comment to `oas_client_gen.go` and deleted `oas_validators_gen.go` outright; the next run overwrote the patched file, recreated the deleted one, and failed with a message pointing at each. A manual edit to generated code can still be *made*, but it can't quietly survive.

For scale: against Mealie v3.23.1 the vendored schema is a 31,276-line JSON document (178 paths, 246 component schemas) and the generated client is 20 files totalling a little over 216,000 lines. The full test takes about 10–13 seconds on my machine, nearly all of it waiting for the container to boot.

## Other Places I Have Used This Pattern

Nothing about the pattern is specific to OpenAPI or to Docker; any deterministic derivation from an authoritative source can sit behind the same pair of helpers. A few from my own projects, briefly.

**Database migrations to ORM models.** On a work project (a Python application I can't show here), the test suite creates a throwaway PostgreSQL database, applies every migration to it, then reflects selected schemas and generates typed SQLAlchemy models, with each generated module passed through an ensure-up-to-date helper. Migrations stay the single source of truth for the database's shape, while the rest of the application gets an ORM's autocomplete and type checking. It's worth acknowledging that this is the reverse of what many frameworks do: Django and friends treat the models as authoritative and generate migrations from them, which is a perfectly good trade when the framework owns the database. Reflection-based generation earns its keep when the migrations, not the models, are the thing you need to trust.

**Unityped syntax trees to typed AST wrappers.** In [WIT-LSP][wit-lsp], my language server for WIT (the interface-definition language used by the WebAssembly component model), the parser produces a loosely typed Tree-sitter syntax tree, and a generator derives strongly typed Rust wrappers (typed nodes, accessor methods, the lot) from Tree-sitter's node metadata. The [`ast_is_up_to_date` test][wit-lsp-ast] regenerates the wrappers, formats them, and reconciles the checked-in file. The idea of pairing a unityped concrete syntax tree with a generated, strongly typed AST layer comes from Matklad's [Introducing Ungrammar][ungrammar], which is worth reading if you work on language tooling.

**Source declarations to explicit registries.** WIT-LSP also scans its own Rust source for the variants of a `Diagnostic` enum and [generates][wit-lsp-diag] an `all_diagnostics()` function listing every one. Adding a diagnostic is just adding an enum variant; the registry can't be forgotten because a test regenerates it from the enum itself.

**Registries to reference documentation.** That same diagnostic registry carries each diagnostic's code, severity, and a Markdown description; a further derivation serialises the metadata to a checked-in JSON file, and the docs build renders it into an HTML error-code index. Source declarations feed a registry, the registry feeds structured metadata, and the metadata feeds published documentation, with a freshness test at each hop so no layer can silently fall behind the one before it.

## Costs and Failure Modes

The pattern isn't free, and the failures divide by timescale: some break the loop the moment you hit them, while others tax the project so gradually that nobody notices until the tax is large.

### Failures That Break the Loop Immediately

**Non-deterministic generation.** The whole scheme rests on byte-for-byte comparison, so any instability in the output turns the freshness test into a machine that rewrites files at random. The Mealie example hit this twice before it settled: once from timestamps baked into the schema, once from the generator resolving conflicting defaults in map-iteration order. Unstable iteration, embedded timestamps, absolute paths, and locale-dependent formatting are the usual suspects. The fix is always the same: find the source of instability and normalise it away in a deterministic step, or fix the generator.

**Unpinned tools.** If two developers have different versions of the generator installed, the checked-in output ping-pongs between them and every regeneration is suspect. Pin the generator the same way you pin every other dependency; the `tool` directive in `go.mod` does this for Go, lockfiles do it elsewhere. The container digest in the worked example is the same principle applied to the upstream service.

**Dependency cycles.** If the codegen test depends, even transitively, on the code it generates, then broken generated output can stop the test from compiling, and the repair path is wedged shut. This is why `TestMealieClientIsUpToDate` never imports the client it maintains. It's an easy rule to state and a surprisingly easy one to violate by accident, because the generated package is usually the most convenient one to reach for.

### Costs That Accumulate

The slower failures are behavioural, and they're the ones with the larger long-term impact.

A test that boots a container, or provisions a database, or touches the network, is a different animal to the rest of your unit tests. Ten seconds sounds cheap until it's one of a dozen such tests and the suite that used to run in two seconds now takes three minutes. Developers respond to slow suites in predictable ways: they run tests less often, or they carve the slow ones into a separate suite that runs less often, and either way the feedback loop the pattern depends on gets longer. The `testing.Short()` guard in the worked example is a small concession to this; the honest answer is that these tests belong in CI on every change and on developer machines when relevant, and keeping that arrangement healthy takes ongoing attention.

The other slow cost is the generated code itself. A 216,000-line client is not a neutral thing to keep in a repository. It bloats clones and history forever, and every regeneration produces diffs that no human will genuinely read line by line. Reviewers adapt by skimming, and a culture of skimming large diffs is exactly the environment where an important change slips through. The worked example softens this by vendoring the schema too, so review can focus on the small contract-level diff and treat the client diff as its mechanical consequence, but the repository cost remains. These are frog-in-the-pot problems: no single regeneration makes anything obviously worse, so the cost only becomes visible in hindsight.

A few operational rules follow from the same concerns. Generated trees need an unambiguous ownership boundary, because the reconciler deletes what it doesn't recognise. The other two rules are answers to the same question: where is a necessary change allowed to go? Never into the generated files themselves, which should announce themselves loudly (a `// Code generated ... DO NOT EDIT.` header at minimum) and are not a customisation seam; a change belongs in the authoritative source, in the generator, or in an explicit deterministic post-processing stage like the normalisation step above. And sometimes the answer is that the output shouldn't be checked in at all: if every consumer can regenerate it cheaply and reproducibly, build-time generation avoids the review load and repository growth entirely, at the price of the navigation, documentation, and reviewability that committed code provides.

## When I Reach for It

Rather than a checklist, here's the shape of the situation that makes me reach for this pattern.

The clearest trigger is noticing that a project has acquired a CLI incantation somebody must remember to run. Unless the project will never evolve, that instruction is a promise waiting to be broken, and moving the derivation into a test converts it from a memory problem into an ordinary red-test problem, the kind every developer already knows how to respond to.

The second half of the judgement is about the generation itself, because the test pattern only makes generated code *maintainable*, not worthwhile. Code generation brings real magic into a project: a build step people have to understand, large diffs, permanent history growth. It earns those costs when the derived interface is substantially better than what you'd write against otherwise. A typed client instead of hand-rolled HTTP calls, typed AST nodes instead of stringly-typed tree access, ORM models that match the real database, or the removal of genuinely large amounts of boilerplate. If the generated code is only a mild convenience, the honest move is to not generate it, and then there's nothing for the test to keep fresh.

None of this means you should go hunting for places to introduce code generation this week. It's a tool-belt pattern: cheap to remember, and you'll recognise the project that needs it when you're standing in it.

Next time you catch yourself writing "after changing X, remember to run Y" in a README, consider giving that sentence to the test suite instead. The helpers involved are about a hundred lines, and the idea has solid prior art in Matklad's self-modifying-code post. You still pay for the container boots and the oversized diffs, but the generated code stays exactly what its source says it should be, and nobody has to remember anything.

[self-modifying-code]: https://matklad.github.io/2022/03/26/self-modifying-code.html
[ungrammar]: https://rust-analyzer.github.io/blog/2020/10/24/introducing-ungrammar.html
[mealie]: https://github.com/mealie-recipes/mealie
[ogen]: https://github.com/ogen-go/ogen
[wit-lsp]: https://github.com/Michael-F-Bryan/wit-lsp
[wit-lsp-ast]: https://github.com/Michael-F-Bryan/wit-lsp/blob/c90addb21d37f2bd62a9474adca1dd8f6320d437/crates/xtask/src/codegen/ast.rs#L609-L620
[wit-lsp-diag]: https://github.com/Michael-F-Bryan/wit-lsp/blob/c90addb21d37f2bd62a9474adca1dd8f6320d437/crates/xtask/src/codegen/diagnostics.rs
