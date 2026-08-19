---
title: The Accidental Application Runtime
date: '2026-08-19T21:00:00+08:00'
tags:
- Go
- Architecture
- Concurrency
- Software Design
---

Imagine you look after the software for a small 3D-print farm: a rack of printers, a Go service running on a box in the corner, and a central backend somewhere that decides what needs printing. The service started life as a dashboard. Somebody wanted to see what each printer was doing without walking over to it, so you wrote a little HTTP server, and because the handlers needed live printer state, the server's setup code connected to the printers and started a goroutine to poll them. Completely reasonable.

Then the central backend came along. Jobs now arrive from upstream, so the service grew a goroutine that pulls them down into a SQLite-backed job store. Something has to match queued jobs to idle printers, so it grew a scheduler. Something has to actually send G-code to a printer and watch it happen, so it grew a runner. Each of these landed in the same setup path, because that's where the printer connections and the store already lived, and each was a small, sensible change that took an afternoon.

A while later the backend team asked for periodic status reports, and by then nobody even paused before adding another goroutine to the pile. The setup code now looks something like this:

```go
func NewServer(cfg Config) (*Server, error) {
	printers, err := ConnectPrinters(cfg.Printers)
	if err != nil {
		return nil, err
	}

	store, err := OpenJobStore(cfg.DatabasePath)
	if err != nil {
		return nil, err
	}

	s := &Server{
		printers: printers,
		store:    store,
		backend:  NewBackendClient(cfg.BackendURL, cfg.APIKey),
		state:    newStateCache(),
	}

	go s.watchPrinters()  // the dashboard needs live state
	go s.pullJobs()       // jobs arrive from the backend
	go s.schedule()       // idle printer + queued job → assignment
	go s.runAssignments() // someone has to actually print things
	go s.reportUpstream() // the backend wants status reports

	return s, nil
}
```

There's nothing especially bad about this code. Each line was the natural next step at the time. The application works; it prints things. The problem isn't the length of the setup code, but that it now owns all of the application's long-running work.

## Then Someone Asks for Graceful Shutdown

The problem showed up when somebody asked for graceful shutdown. Deploying a new version of the service means killing the process, and killing the process mid-print ruins whatever was on the beds and leaves half-claimed jobs in limbo. The request is simple enough: when the service receives `SIGTERM`, it should stop accepting new work, let the runner get each printer to a safe stopping point, record which assignments were interrupted so the next process can pick them up, and then exit.

You sit down to thread cancellation through the code, and the questions start piling up. Which goroutines are even running? The only way to answer is to read the setup code and everything it calls. What order should they stop in? The scheduler feeds the runner through a channel — if the scheduler exits first, who closes it, and is the runner allowed to finish draining it? The puller and the reporter both talk to the backend; do they share a shutdown deadline? Every background failure so far has just been logged and forgotten, and now some of them are supposed to trigger an orderly teardown instead. And all of these answers have to be expressed *inside an HTTP server object*, because that's the thing that owns everything.

None of these questions is hard on its own. What makes this the moment you stop and ask whether there's a better way is that the code gives you nowhere to answer them. The lifetimes you're being asked to coordinate aren't represented anywhere — they're implicit in five `go` statements and the order of some struct fields.

## An Accidental Runtime

Every application with more than one long-lived activity has a runtime in the small, whether or not anyone designed it: something decides what those activities are, what they're allowed to touch, how they hear about each other, and when they stop. We normally reserve the word "runtime" for the machinery underneath the language, but your application has one of its own. In the print-farm service, that setup code lives in `NewServer`. Nobody chose that. The HTTP server was simply the first object that needed the shared state, so it became the place where long-running things get born, and every later addition reinforced the pattern. That's what I mean by an *accidental* application runtime.

The reason this is worth naming — and the reason "the setup code is too big" misses the point — is what it does to the architecture. The service genuinely has one: five concurrent components with fairly clear responsibilities and well-defined data flowing between them. You could sketch it on a whiteboard in a minute, once you'd worked it out. But no artefact in the codebase expresses it. The design exists only as the side effects of wiring code: a field here, a `go` statement there, a channel threaded through two private methods. The application has outgrown the structure it started with — "a web server with some helpers" stopped being a true description a long time ago — and nothing in the code acknowledges that a larger design has emerged. The architecture is real, but hidden.

Graceful shutdown happened to be the request that exposed this for me. For you it might be a component you can't test without standing up the whole process, or a new feature with no obvious home, or a new team member asking "what talks to what?" and watching you open six files to answer. The symptom varies; the underlying condition — an operating architecture that's visible only indirectly — is the same.

It's also not really about HTTP. The same accretion happens to a CLI command's run function, the setup code around a message-queue consumer, a GUI main window, or a `main()` that grew organically. Wherever starting the application revolves around one convenient object, that object gradually becomes the runtime. HTTP servers are just unusually good hosts for the pattern, because they're long-lived, they're created early, and every feature eventually wants to show something to a user.

None of this is hypothetical. The design grew out of a real Go edge service that talks to hardware, whose details aren't mine to share. The print-farm service was written from scratch for this article to recreate the same pressures. If it feels oddly specific in places, that's why.

## A Detour Through PX4

Once I'd named the problem — the architecture exists, but nothing expresses it — I wanted prior art for expressing it, and the codebase that taught me the most wasn't a web framework. It was [PX4][px4], the open-source drone autopilot. I've spent a fair amount of time in its source and documentation, and it's an application that makes our print farm look leisurely: sensor drivers producing data at hundreds of hertz, estimators fusing it, controllers consuming the estimates, telemetry, logging — dozens of concurrent activities that absolutely must coordinate, running on a flight controller.

Three ideas from [PX4's architecture][px4-arch] transfer almost directly.

**Modules, in one process.** PX4 is built as self-contained modules that communicate through asynchronous message passing, but it is not a distributed system: the modules share an address space and run as tasks or on shared work queues. That combination — strong internal boundaries *without* separate services — was exactly the shape I was missing. You don't have to choose between "one big object owns everything" and "split it into microservices".

**Typed topics, not everything a message.** Modules exchange messages over [uORB][uorb], a publish/subscribe bus where each topic carries one well-known message type. Just as usefully, PX4 doesn't force everything through the bus: broadly-used facilities like parameters sit outside the message graph and are accessed directly. Streams of events and stable shared services are different things, and the architecture keeps them different.

**Topology you can generate.** Because modules declare their subscriptions and publications in code, PX4 can extract a [graph of modules and topics][uorb-graph] straight from the source. The architecture diagram isn't a wiki page that rots; it's derived from the same declarations that run the system.

I want to give proper credit here because the shape of everything that follows is borrowed from PX4. But it is only the shape. uORB's delivery behaviour, for instance, is tuned for control loops: a topic's default queue holds a single message, and a slow reader simply misses intermediate values — newer publications overwrite unread ones. That's the right call when only the freshest gyro sample matters, and the wrong call when the message is "a job finished". The design below makes the opposite default and treats latest-value delivery as its own explicit concept, and it makes no attempt to reproduce uORB's implementation, its multi-instance topics, or its start/stop-individual-modules lifecycle. Shape, not guarantees.

## Modules as Ordinary Functions

So: what's the smallest way to say "this application is a set of concurrent modules that exchange typed messages and share a few resources" in Go, without inventing a schema language, a registration DSL, or a framework the reader has to learn?

My answer, after some false starts, is that you already say it every time you write a function signature:

```go
func MonitorPrinters(
	ctx context.Context,
	printers *PrinterClients,
	states chan<- PrinterState,
) error
```

Read that signature the way you'd read a sentence. This is a long-running activity that participates in a shared lifecycle (`ctx`), it needs access to the printer connections (`*PrinterClients`), it produces a stream of `PrinterState` values (`chan<- PrinterState`), and it can fail (`error`). Everything the runtime — or a colleague — needs to know about how this module plugs into the application is right there, in vocabulary Go programmers already know.

That observation became a small library, which I've called `backplane`. A module is any `func(ctx context.Context, ...dependencies) error`, and each parameter after the context declares one dependency:

| Parameter type         | Meaning                                             |
| ---------------------- | --------------------------------------------------- |
| `chan<- T`             | publish to the topic carrying `T`                   |
| `<-chan T`             | subscribe to the topic carrying `T`                 |
| `*backplane.Latest[T]` | observe the most recent `T` (we'll get to this one) |
| anything else          | a resource supplied by the caller                   |

A topic is identified by the exact Go type flowing through it — no topic strings to typo, no schema compiler. Any number of modules can publish or subscribe to the same type, and every subscriber receives every value.

The API on top is deliberately tiny:

```go
app, err := backplane.New(MonitorPrinters, ScheduleJobs, RunJobs /* , ... */)
// inspect it:
fmt.Print(app.Graph().Mermaid())
// or run it:
err = app.Run(ctx, printers, store)
```

`New` *records* the module signatures; it never calls a module. Keeping declaration separate from execution means the same signatures can produce an architecture diagram without opening a database connection, while `Run` can validate the entire wiring before a single module starts. Registering a function is simultaneously writing executable code and writing down where that code sits in the design.

Two contracts are worth pausing on, because they're where the accidental version went wrong.

First, **messages versus resources**. `PrinterState` is a flow of values; the job store is a capability. The accidental runtime blurred these — the state cache, the store, and the subscriptions all lived as fields on one struct, and everything touched everything. Here, a stream is a channel parameter and a resource is any other parameter, and the two are wired completely differently.

Second, **messages versus calls**. Nothing forces request/response work through the bus. When an HTTP handler needs to pause a job *and tell the user whether that worked*, a direct method call on the store is the honest contract, and the module simply declares the store as a resource. Topics are for events flowing between concurrent components, not a religion about how functions may talk to each other.

The uniform `ctx`-and-`error` shape also makes lifecycle and failure part of the contract. Every module must accept a context, which means every module author is confronted with cancellation as part of the ordinary contract rather than as a retrofit — the thing the print-farm service couldn't do. And every module must return an `error`, which gives failures somewhere legitimate to go besides a log line inside a forgotten goroutine.

Here's the rough shape we're heading towards, using a slice of the print farm — modules in boxes, typed topics on the arrows, resources dashed:

{{< mermaid >}}
graph LR
    pc[(printer clients)] -.-> mon[MonitorPrinters]
    store[(job store)] -.-> sched[ScheduleJobs]
    mon -- PrinterState --> sched
    sched -- AssignmentReady --> run[RunJobs]
    pc -.-> run
    run -- JobFinished --> sched
{{< /mermaid >}}

Notice the loop: completions feed back into scheduling. This is a system of peers, not a pipeline that terminates at a web handler.

{{% notice note %}} Everything in this article comes from a real, tested library: [`backplane`][repo], published under Apache-2.0. The sections below show the parts of the implementation where the interesting decisions live — enough, I hope, that you could finish it yourself — and the repository carries the complete implementation, along with the tests that pin down every contract described here.

If you spot a bug, in the code or the prose, let me know on the blog's [issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/backplane
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## Reading Signatures

The core of the whole idea is a function that looks at a parameter type and decides what kind of dependency it declares. With `reflect` this is almost embarrassingly short:

```go
func inspectParameter(parameterType reflect.Type) (parameter, error) {
	if parameterType == contextType {
		return parameter{}, errors.New("context.Context may only appear as the first parameter")
	}
	if messageType, ok := latestMessageType(parameterType); ok {
		return parameter{kind: latestParameter, typeOf: parameterType, topicType: messageType}, nil
	}
	if parameterType.Kind() == reflect.Chan {
		p := parameter{typeOf: parameterType, topicType: parameterType.Elem()}
		switch parameterType.ChanDir() {
		case reflect.SendDir:
			p.kind = publisherParameter
		case reflect.RecvDir:
			p.kind = subscriberParameter
		default:
			return parameter{}, errors.New("channels must be directional: chan<- T publishes, <-chan T subscribes")
		}
		return p, nil
	}
	return parameter{kind: resourceParameter, typeOf: parameterType}, nil
}
```

(Ignore the `latestParameter` branch for now; it gets introduced properly in a few sections.)

One decision in there deserves a comment: bidirectional channels are rejected outright. A plain `chan T` parameter compiles fine and would even work, but it doesn't *say* which way data flows — and since the entire point is that the signature is the wiring documentation, an ambiguous declaration is a bug, not a convenience.

Around this sits `inspectModule`, which enforces the module shape — must be a non-nil, non-variadic function, `context.Context` first and only there, exactly one `error` result — and `New`, which runs inspection over every module and then cross-checks the topics: a module that subscribes to a topic no module publishes is rejected on the spot. That check has the same flavour as an unsatisfied import: you've declared a dependency on something that doesn't exist, so refusing to start the application at all is kinder than letting a subscriber block forever at 2am. All of this happens before any module code runs, which is what makes the side-effect-free `Graph()` possible.

## Running the Modules

`Run(ctx, resources...)` has two jobs: bind the caller's resources to the declared parameters, and supervise the modules.

Resource binding stays simple. The caller passes already-created values — no providers, no factories — and each resource parameter binds to exactly one of them: by exact type match first, otherwise by *unique* assignability, so a concrete `*SQLiteJobStore` can satisfy a `JobStore` interface parameter without ceremony. Nil values, duplicate types, ambiguous matches, missing resources, and resources nothing asked for are all rejected before any module starts. That last one — rejecting *unused* resources — occasionally annoys me for about ten seconds, and then I remember that an unused resource is almost always a wiring mistake I'd rather hear about now.

I did consider going further and letting the library create resources too, and decided firmly against it. In practice the composition root wants to be ordinary Go at the top of `main`: open the store, `defer store.Close()`, pass it in. The moment the runtime owns resource creation, it needs ordering, error policies, health checks, and cleanup — and it has become a dependency-injection framework, which is a much bigger thing than I ever wanted. It would also wreck the laziness: needing a live database connection to render an architecture diagram is silly. Backplane binds values; owning them is your job.

Supervision is `errgroup` semantics, because those are the semantics I always end up wanting anyway:

```go
// (binding elided: by this point every declared parameter has been
// resolved into inv.args — resources, channels, and the shared context)
group, groupContext := errgroup.WithContext(ctx)

for _, t := range topics {
	group.Go(func() error {
		t.pump(groupContext)
		return nil
	})
}
for _, inv := range invocations {
	group.Go(func() error {
		defer func() {
			if inv.done != nil {
				close(inv.done)
			}
			for _, t := range inv.published {
				t.publisherDone()
			}
		}()
		result := inv.module.fn.Call(inv.args)[0].Interface()
		if result == nil {
			return nil
		}
		return fmt.Errorf("module %s: %w", inv.module.name, result.(error))
	})
}
return group.Wait()
```

A module returning `nil` finishes quietly and its siblings carry on — a finite publisher is a perfectly normal module, not a special kind. The first module to return an error cancels every sibling's context. Cancelling the context you passed to `Run` shuts the whole application down. And `Run` doesn't return until every module has, so "the process exited" means "every component actually stopped", not "main fell off the end". The deferred bookkeeping — `inv.done` and `publisherDone()` — is each module telling its topics that it's finished; the next section is about why they care.

One deliberate omission: there is no way to add a module while the application is running. The set is fixed at `New`. A module that needs short-lived workers spawns its own goroutines, joins them before returning, and folds their failures into its own error — that's an implementation detail of the module, not a new node in the architecture. Every use case I came up with for dynamic registration was served better by a static module that sits mostly idle, and keeping the set fixed is precisely what makes the graph trustworthy.

## Moving Values Around

Topics are where the concurrency actually lives, and this is the code I'd least want a reader to hand-wave past. Each publisher parameter gets its own unbuffered channel into the topic; a per-topic pump goroutine receives values and fans them out:

```go
func (t *topic) pump(ctx context.Context) {
	defer t.finish()

	topicDone := reflect.SelectCase{Dir: reflect.SelectRecv, Chan: reflect.ValueOf(t.done)}
	contextDone := reflect.SelectCase{Dir: reflect.SelectRecv, Chan: reflect.ValueOf(ctx.Done())}
	inputs := slices.Clone(t.inputs)
	cancelled := false

	for {
		cases := make([]reflect.SelectCase, 0, len(inputs)+2)
		cases = append(cases, topicDone, contextDone)
		if cancelled {
			cases[1].Chan = reflect.Value{} // a zero Chan is never ready
		}
		for _, input := range inputs {
			cases = append(cases, reflect.SelectCase{Dir: reflect.SelectRecv, Chan: input})
		}

		chosen, value, ok := reflect.Select(cases)
		switch {
		case chosen == 0: // every publisher has returned
			return
		case chosen == 1:
			cancelled = true
		case !ok: // a module closed its publisher channel: stop receiving from it
			inputs = slices.Delete(inputs, chosen-2, chosen-1)
		case cancelled: // cancellation interrupts delivery: drain and drop
		default:
			if t.latest != nil {
				t.latest.publish(value, time.Now())
			}
			cancelled = !t.deliver(value, contextDone)
		}
	}
}

// deliver hands value to every live subscriber, blocking until each accepts
// it. It reports false if the context was cancelled mid-delivery.
func (t *topic) deliver(value reflect.Value, contextDone reflect.SelectCase) bool {
	for index := range t.subscribers {
		sub := &t.subscribers[index]
		if sub.dead {
			continue
		}
		chosen, _, _ := reflect.Select([]reflect.SelectCase{
			{Dir: reflect.SelectSend, Chan: sub.channel, Send: value},
			{Dir: reflect.SelectRecv, Chan: sub.moduleDone},
			contextDone,
		})
		switch chosen {
		case 1: // the subscribing module returned: drop its subscription
			sub.dead = true
		case 2:
			return false
		}
	}
	return true
}
```

The delivery contract that falls out of this is easy to state and important to internalise: **delivery is in-process, memory-only, and backpressured**. A publish blocks until every subscriber has accepted the value, so a module must treat every send as potentially blocking. There is no durability, no replay, no retry, no acknowledgement. If losing a message would matter after a crash, the message was never the right place for that information — more on this when we rebuild the print farm.

Most of the subtlety is in shutdown and completion:

- **A topic completes when every module publishing to it has returned** — at
  which point the subscriber channels are closed, so
  `for value := range subscription` is the natural consumption loop and
  terminates by itself. Completion tracks module lifetimes, not channels.
- **A finished subscriber stops participating.** If a module returns while
  its siblings are still publishing, its abandoned subscription is dropped
  (that's the `moduleDone` case above) rather than backpressuring the topic
  from beyond the grave.
- **Cancellation drains.** After the context is cancelled, the pump keeps
  receiving but drops the values, so a publisher blocked in a bare send can
  unwind and get on with its own shutdown. Yes, that means cancellation can
  lose in-flight values; that's part of the contract, and it's why durable
  facts don't live on the bus.
- **Closing a channel you were handed is a fault backplane tolerates.** The
  channels belong to the runtime, and a module has no business closing one —
  but if it does, only that module's own later sends panic; the topic keeps
  working for everyone else, and completion still waits for the module to
  actually return.

None of this is exotic — it's a fan-out loop and some `select` cases — but having it written *once*, with tests, is exactly what the accidental runtime never had. Every one of those bullet points used to be an ad-hoc decision smeared across five goroutines.

## Rebuilding the Print Farm

Now we get to put the service back together, and this is where the design gets stress-tested, because the print farm needs more than a pipeline.

Deciding the module boundaries is mostly deciding who owns what. The central backend owns job creation, queue membership, and priority — arguing with it locally would mean building conflict resolution I don't want to teach or maintain. The local HTTP interface owns the immediate physical controls: pause, cancel, take a printer out of service. SQLite, behind an opaque `JobStore` interface, owns everything that must survive a restart: queued jobs, claimed assignments, terminal outcomes. And the bus owns exactly one thing — live, in-process coordination.

That split produces six modules:

```go
// Watches the printers, publishing a snapshot whenever one changes.
func MonitorPrinters(ctx context.Context, printers *PrinterClients,
	states chan<- PrinterState) error

// Pulls jobs from the central backend into the store, announces changes,
// and periodically reports current farm state upstream.
func SyncBackend(ctx context.Context, backend *BackendClient, jobs JobStore,
	interval ReportInterval, farm *backplane.Latest[FarmState],
	progress *backplane.Latest[JobProgress], queueChanged chan<- QueueChanged) error

// The dashboard and local controls: reads current state, streams updates
// over SSE, and applies operator actions through the store.
func ServeHTTP(ctx context.Context, config HTTPConfig, jobs JobStore,
	farm *backplane.Latest[FarmState], progress *backplane.Latest[JobProgress],
	queueChanged chan<- QueueChanged) error

// Matches persisted queued work against live printer availability and
// durably claims assignments.
func ScheduleJobs(ctx context.Context, jobs JobStore, states <-chan PrinterState,
	changed <-chan QueueChanged, finished <-chan JobFinished,
	assignments chan<- AssignmentReady) error

// Executes assignments on printers, persisting outcomes and publishing
// live progress.
func RunJobs(ctx context.Context, printers *PrinterClients, jobs JobStore,
	assignments <-chan AssignmentReady, progress chan<- JobProgress,
	finished chan<- JobFinished) error

// Folds printer state, progress, and outcomes into one current view of
// the farm.
func BuildFarmState(ctx context.Context, printers <-chan PrinterState,
	progress <-chan JobProgress, finished <-chan JobFinished,
	farm chan<- FarmState) error
```

Notice what happened to HTTP. `ServeHTTP` is a real module with real dependencies — it can pause a job through the store and answer for the result — but it's one peer among six. It no longer gives birth to anything. Notice, too, `BuildFarmState`: a module that consumes three topics and publishes a derived one, with no I/O at all. The accidental runtime had this logic as a cache bolted onto the server; here it's a first-class component you can read, replace, or test on its own.

The subtlest contract in the system is between the store and the bus, and it's worth spelling out because in-process buses make it very easy to lie to yourself about durability. `QueueChanged` and `AssignmentReady` are *notifications about* durable state, never the state itself. Any durable mutation follows commit-then-notify: `ScheduleJobs` claims a job in SQLite *first*, and only then announces `AssignmentReady` to wake the runner. If the process dies between the two, the claim is still in the store, and both the scheduler and runner begin by reconciling against the store rather than waiting to be told — a notification that fired in a previous process is gone forever, and the design has to be indifferent to that. The bus is a wake-up call, not a ledger.

With that in mind, the scheduler is small enough to read in one pass:

```go
func ScheduleJobs(
	ctx context.Context,
	jobs JobStore,
	states <-chan PrinterState,
	changed <-chan QueueChanged,
	finished <-chan JobFinished,
	assignments chan<- AssignmentReady,
) error {
	printers := map[PrinterID]PrinterState{}

	// Recover work that was queued before this process existed.
	if err := assignWork(ctx, jobs, printers, assignments); err != nil {
		return err
	}

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case state := <-states:
			printers[state.Printer] = state
		case <-changed:
			// Something in the queue moved; the details live in the store.
		case <-finished:
			// A printer just came free.
		}

		if err := assignWork(ctx, jobs, printers, assignments); err != nil {
			return err
		}
	}
}
```

`assignWork` finds idle printers, asks the store for the highest-priority job each is capable of printing, durably claims the pair, and announces it. The scheduling rule itself could grow much smarter without anything else in the system changing, because everything it knows arrives through those parameters.

## Streams Versus State

Rebuilding the print farm exposes one more contract. Look at who consumes `FarmState` and `JobProgress`: the HTTP module, for GET endpoints and an SSE stream to however many browser tabs happen to be open; and the backend sync module, which snapshots the farm every thirty seconds for its report.

A declared subscriber is the wrong contract for both. Backpressured delivery means every subscriber can slow the publisher down — which is exactly what you want between the runner and the scheduler, and exactly what you *don't* want between the runner and someone's phone on hotel Wi-Fi. A dashboard doesn't need every intermediate progress value anyway; it needs the current one, promptly, and the freedom to miss the ones in between. A periodic reporter is even more extreme: it wants to ask "what's the state right now?" twice a minute and ignore everything else.

"Every value, with backpressure" and "the current value, without backpressure" are different contracts, and blurring them is how streaming endpoints grow bespoke buffers, drop policies, and replay caches one incident at a time. So the split gets its own type — the `*backplane.Latest[T]` you've seen in the signatures above. Declaring one gives the module a live view of a topic instead of a subscription: `Load` returns the most recent value and when it arrived, and `Watch` serves the streaming case:

```go
// Watch returns a channel that converges on the most recent value: the
// current value (if any) is delivered immediately, and each newer value
// overwrites any undelivered one, so a slow watcher misses intermediate
// values rather than backpressuring the topic.
func (l *Latest[T]) Watch(ctx context.Context) <-chan T {
	watcher := make(chan T, 1)

	l.mu.Lock()
	if l.hasValue {
		watcher <- l.value
	}
	// ... register the watcher; a goroutine removes it when ctx is
	// cancelled, and the topic closes every watcher when it completes ...
	l.mu.Unlock()
	return watcher
}
```

The mechanism that keeps watchers from ever blocking a publisher is a one-value mailbox per watcher:

```go
for watcher := range l.watchers {
	select {
	case watcher <- typedValue:
	default:
		// The watcher has an undelivered value: replace it. Nothing else
		// sends on watcher, so after the drain the send cannot block.
		select {
		case <-watcher:
		default:
		}
		watcher <- typedValue
	}
}
```

With `Latest`, the SSE handler collapses into something you'd be happy to review: watch the projections, send each update as it arrives, and let the channel closing end the loop. New clients get the current state immediately — `Watch` delivers it up front — with no replay cache to invalidate. The runtime already knew the current state; it just needed a contract for handing it over.

## Testing the Pieces

The module boundaries also make testing straightforward. Because modules are ordinary functions, testing the scheduler needs no bus, no HTTP server, and no printers — just channels and a fake store:

```go
func TestSchedulerAssignsQueuedJobToIdlePrinter(t *testing.T) {
	jobs := newFakeJobStore(Job{ID: "benchy", Filament: PLA})
	states := make(chan PrinterState)
	changed := make(chan QueueChanged)
	finished := make(chan JobFinished)
	assignments := make(chan AssignmentReady)

	ctx, cancel := context.WithCancel(t.Context())
	errs := make(chan error, 1)
	go func() {
		errs <- ScheduleJobs(ctx, jobs, states, changed, finished, assignments)
	}()

	states <- PrinterState{Printer: "mk4-01", Idle: true, Loaded: PLA}

	got := <-assignments
	if got.Job != "benchy" || got.Printer != "mk4-01" {
		t.Fatalf("assigned %+v", got)
	}
	if !jobs.isClaimed("benchy", "mk4-01") {
		t.Fatal("assignment was announced before it was durably claimed")
	}

	cancel()
	if err := <-errs; !errors.Is(err, context.Canceled) {
		t.Fatalf("ScheduleJobs() error = %v", err)
	}
}
```

The test stays at the module boundary: a printer went idle, so an assignment should appear, and the store must be updated before the event is published. Concurrent behaviour — usually miserable to test — is exercised directly through the same typed channels the runtime would provide, and the commit-then-notify ordering is one assertion instead of a prayer.

When you do want to test the wiring rather than one module, you assemble a small backplane out of test modules — a publisher that injects events, the module under test, a subscriber that records output — and `Run` it. The library's own test suite works this way, and it's also where every contract from the delivery section is pinned down: sibling survival after a `nil` return, first-error cancellation, blocked publishers unwinding on shutdown, abandoned subscriptions, the lot. Those tests exist once, in the library — instead of implicitly, nowhere, in every application.

## The Graph at the End

Putting the finished service together looks like this — resources created and owned at the top of `main`, just as before, and every `go` statement from the old setup code now a name in a list:

```go
ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
defer stop()

app, err := backplane.New(
	MonitorPrinters,
	SyncBackend,
	ServeHTTP,
	ScheduleJobs,
	RunJobs,
	BuildFarmState,
)
if err != nil {
	log.Fatal(err)
}

printers, err := ConnectPrinters(cfg.Printers)
// ...
store, err := OpenJobStore(cfg.DatabasePath)
// ...
defer store.Close()

err = app.Run(ctx, printers, store,
	NewBackendClient(cfg.BackendURL, cfg.APIKey),
	cfg.HTTP, ReportInterval(30*time.Second))
```

The graceful-shutdown request that started all of this is now the boring part: `SIGTERM` cancels one context, every module sees it, the runner parks its printers and records what was interrupted, and `Run` returns when — and only when — everyone has actually finished. The question "who stops, in what order, owned by whom" has one structural answer instead of five improvised ones.

And because `New` never executed anything, the same declarations render the architecture. `fmt.Print(app.Graph().Mermaid())` emits this, verbatim:

{{< mermaid >}}
graph LR
  n0["MonitorPrinters"]
  n1["SyncBackend"]
  n2["ServeHTTP"]
  n3["ScheduleJobs"]
  n4["RunJobs"]
  n5["BuildFarmState"]
  n6[("*main.BackendClient")]
  n7[("*main.PrinterClients")]
  n8[("main.HTTPConfig")]
  n9[("main.JobStore")]
  n10[("main.ReportInterval")]
  n11{{"main.AssignmentReady"}}
  n12{{"main.FarmState"}}
  n13{{"main.JobFinished"}}
  n14{{"main.JobProgress"}}
  n15{{"main.PrinterState"}}
  n16{{"main.QueueChanged"}}
  n7 --> n0
  n0 --> n15
  n6 --> n1
  n9 --> n1
  n10 --> n1
  n12 -->|latest| n1
  n14 -->|latest| n1
  n1 --> n16
  n8 --> n2
  n9 --> n2
  n12 -->|latest| n2
  n14 -->|latest| n2
  n2 --> n16
  n9 --> n3
  n15 --> n3
  n16 --> n3
  n13 --> n3
  n3 --> n11
  n7 --> n4
  n9 --> n4
  n11 --> n4
  n4 --> n14
  n4 --> n13
  n15 --> n5
  n14 --> n5
  n13 --> n5
  n5 --> n12
{{< /mermaid >}}

This is the whiteboard sketch from back when we were diagnosing the problem — except nobody drew it, maintains it, or gets to be wrong about it. It's derived from the same signatures that `Run` executes, so it can't drift, and regenerating it after a refactor takes one command.

Read it for a moment, because it's candid in ways hand-drawn architecture diagrams rarely are. The feedback loop is visible: `JobFinished` flows back into `ScheduleJobs`. `ServeHTTP` sits on the edge as one consumer among several — the dashed lines show it still directly holds `JobStore`, because synchronous operator commands are honest method calls, and the graph doesn't pretend otherwise. Four modules touch the store; that's real coupling, deliberately retained, and now it's *visible* coupling. What the graph shows is declared topology — which modules exist and what they're wired to — not whether anything is currently healthy or publishing; it's a floor plan, not a heartbeat monitor. For explaining the system to someone new, or arguing about where a proposed feature should live, a floor plan is the thing that was missing.

## What Backplane Isn't

The whole library is well under a thousand lines, and I'd like it to stay that way, so it's worth being explicit about the boundaries — most of which you've already seen as design decisions:

- **Not a message broker.** Everything is in one process and one memory
  space. No persistence, no replay, no acknowledgements, no QoS, no
  cross-process transport. If a fact must survive a crash, put it in the
  store and use the topic to wake people up.
- **Not a DI container.** The caller creates resources, cleans them up,
  and passes in values. Backplane binds; it never builds.
- **Not a process manager.** The module set is fixed before startup, modules
  can't be individually restarted, and dynamic workers are a module's
  private business.
- **Not a rule that everything is a message.** Request/response work keeps
  being function calls on resources, because that's the truthful contract
  for it.
- **Not for every application.** A stateless HTTP API in front of a database
  has one job and doesn't need an application runtime; giving it one is
  ceremony. This design earns its keep when there are several long-running
  concurrent activities whose relationships have become hard to see.

If you squint, what's left is the slice of the microservices pitch I actually find myself missing in a monolith — clear ownership, visible contracts, components you can test alone — while the deployment, scaling, and fault-isolation benefits obviously don't come along for the ride.

## Recognising It Next Time

The library was the easy part; a capable Go programmer could rebuild it from this article without much trouble, and you're welcome to. The part I'd actually like you to take away is the diagnosis.

The pattern to watch for is setup code — perhaps a run function or a consumer loop — that starts several goroutines simply because it already has access to their dependencies. The application may have outgrown its original structure even though the real architecture is still only visible in its wiring. Before reaching for a service boundary or a framework, try asking the smaller question first: *what are the long-running parts of this application, what flows between them, and where is any of that written down?*

If the answer is "nowhere", that doesn't mean the code is bad. It means a design has emerged without being written down. A bus like this one is one way to make it explicit, but the mechanism is secondary. The important part is writing down the architecture the application already has.

[px4]: https://px4.io/
[px4-arch]: https://docs.px4.io/main/en/concept/architecture
[uorb]: https://docs.px4.io/main/en/middleware/uorb
[uorb-graph]: https://docs.px4.io/main/en/middleware/uorb_graph
