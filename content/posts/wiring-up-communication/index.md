---
title: "Wiring Up Communication"
date: "2019-10-10T22:58:00+08:00"
tags:
- adventures-in-motion-control
- vue
- javascript
---

As we mentioned [in the last AiMC post][next-step], the next task is to wire up
communications between the simulator's backend and frontend.

As a general rule, our frontend will have two communication regimes:

1. When something happens (e.g. a button is pressed or a job starts sending),
   the frontend will send a batch of messages to the backend and interpret the
   response
2. The frontend will continually poll the backend's state in the background
   (e.g. at 10Hz) 

As it is, the `Browser` in our WASM code already provides a method for
sending data to the frontend ([`Browser::send_data()`][send-data]) and
receiving data from the frontend ([`App::on_data_received()`][recv-data]) so
we shouldn't need to write any Rust code.

As far as the frontend is concerned, when a user clicks a button we should:

1. Construct a message to send to the backend
2. fire off an `async` function to queue that message
3. on the next `animate()` tick, the message will be encoded to bytes and we'll
   start sending those bytes to the backend (max of about 256 bytes/tick) using 
   `App::on_data_received()`
4. After processing the message, the backend will invoke `Browser::send_data()`
   to notify us of a response
5. When enough bytes have been received our frontend's `Decoder` will be able to
   decode them back into a `Packet`
6. The frontend will need to inspect the packet to figure out which message is
   being responded to
7. The original `async` call will either be `resolve()`-ed with the
   response, or `reject()`-ed with an error (e.g. `Nack`)

## Creating a Communication Bus

The central entity which will coordinate communication is the `CommsBus`. It
uses the `App::on_data_received()` and `Browser::send_data()`, as well as an
internal list of pending requests, to coordinate messaging between the frontend
and backend, and either `resolve()` or `reject()` pending messages.

The `CommsBus` starts off reasonably simple.

```ts
// frontend/src/CommsBus.ts

export default class CommsBus {
    private pending: Pending[] = [];
}

interface Pending {
    // TODO: implement this
 }
```

The main way it's used by the frontend is via a `send()` method. This needs
to use some `sendToBackend` callback (actually a reference to the
`App::on_data_received()` method) to send the encoded message and return a
promise. The promise's `resolve` and `reject` functions will also need to be
stashed away for later.

```ts
// frontend/src/CommsBus.ts

import { Decoder } from "anpp";

export default class CommsBus {
    public sendToBackend?: (data: Uint8Array) => void;
    private pending: Pending[] = [];

    public send(req: Request): Promise<Response> {
        if (this.sendToBackend) {
            this.sendToBackend(toPacket(req).encoded());

            return new Promise((resolve, reject) => {
                this.pending.push({ started: new Date(), resolve, reject });
            });
        } else {
            return Promise.reject(new Error("Not wired up to the backend"));
        }
    }
}

interface Pending {
    readonly started: Date;
    resolve(response: Response): void;
    reject(err: any): void;
}
```

You may notice that `send()` receives a `Request` object and returns (a promise
which will eventually resolve to) a `Response`. These are actually trivial
data classes which are used to represent the various message types we expect.

```ts
// frontend/src/messaging.ts

export type Request = GoHome;
export type Response = Ack | Nack;

export class Ack {
    public toString(): string { return "ACK"; }
}

export class Nack {
    public toString(): string { return "NACK"; }
}

export class GoHome {
    public readonly speed: number;

    /**
     * Create a new `GoHome` message.
     * @param speed The speed to go home at in mm/s. Must be a positive integer
     * below 256.
     */
    public constructor(speed: number) {
        speed = Math.round(speed);
        if (speed <= 0 || speed >= 256) {
            throw new Error(`The speed must be between 0 and 256 (exclusive), found ${speed}`);
        }

        this.speed = speed;
    }

    public toString(): string { return `Go Home @ ${this.speed}mm/s`; }
}
```

We also need a `toPacket()` function to convert between a message type and a
`Packet` from the [`anpp` package on NPM][anpp-ts].

Given the only `Request` the frontend can send (at this stage) is a `GoHome`,
implementing `toPacket()` is almost trivial...

```ts
// frontend/src/CommsBus.ts

import { Decoder, Packet } from "anpp";

function toPacket(request: Request): Packet {
    if (request instanceof GoHome) {
        return new Packet(1, new Uint8Array([request.speed]));
    } else {
        throw new Error("Unable to convert this to a Packet");
    }
}
```

Next, whenever the backend wants to send us data the `Browser::send_data()` hook
(provided by the top-level Vue component) will need to tell the `CommsBus`. From
there, the bytes can be added to a `Decoder` (again from the `anpp` package) and
we can check for any parsed messages.

```ts
// frontend/src/CommsBus.ts

export default class CommsBus {
    private decoder = new Decoder();

    ...

    public onDataReceived(data: Uint8Array) {
        this.decoder.push(data);

        while (true) {
            const pkt = this.decoder.decode();

            if (pkt) {
                this.handlePacket(pkt);
            } else {
                break;
            }
        }
    }
}
```

Handling a message requires us to pop the next `Pending` request from front of
the `pending` queue and parse the `Packet` into its corresponding `Response`. 
Depending on whether this parse succeeds we can either `resolve()` or `reject()`
the pending request.

```ts
// frontend/src/CommsBus.ts

export default class CommsBus {
    ...

    private handlePacket(pkt: Packet) {
        const pending = this.pending.shift();

        if (!pending) {
            // received a response with no request...
            return;
        }

        try {
            pending.resolve(parse(pkt));
        } catch (error) {
            pending.reject(error);
        }
    }
}
```

Thanks to the `Packet`'s `id` field, and the fact that the only responses we can
handle are empty `Ack` and `Nack` messages, parsing a `Packet` is almost as 
trivial as encoding one.

```ts
// frontend/src/CommsBus.ts

function parse(pkt: Packet): Response {
    switch (pkt.id) {
        case 0:
            return new Ack();
        case 1:
            return new Nack();
        default:
            throw new Error(`Unknown packet type (id: ${pkt.id})`);
    }
}
```

{{% notice info %}}
As part of using `anpp` in our frontend I actually needed to port the original
`anpp` library from C to JavaScript and publish it to NPM. Please raise tickets
on the issue tracker if bugs are found or you have any suggestions!
{{% /notice %}}

## Using the Comms Bus from the Control Panel

We'll pass a `Send` function to our `Controls` component to allow it to send
messages to the backend.

First we'll need to give the `Controls` component a `send` property which is
`fn(Request) -> Promise<Response>`.

```ts
// frontend/src/components/Controls.vue

@Component
export default class Controls extends Vue {
  @Prop({ required: true })
  public send!: (req: Request) => Promise<Response>;

  ...
}
```

Next we'll wire up the *Home* section's submit handler and make it send a 
`GoHome` message.

```vue
// frontend/src/components/Controls.vue

<template>
  <div>
    <b-form inline @submit="onHomePressed">
      ...
    </b-form>
  </div>
</template>

<script lang="ts">
@Component
export default class Controls extends Vue {
  public motion = new MotionParameters();
  @Prop({ required: true })
  public send!: (req: Request) => Promise<Response>;

  public onHomePressed(e: Event) {
    e.preventDefault();
    this.home().then(console.log).catch(console.error);
  }

  private home() {
    return this.send(new GoHome(this.motion.homingSpeed));
  }
}
</script>
```

We also need to make sure the frontend's top-level `App` component provides this
`send()` prop.

```vue
// frontend/src/App.vue

<template>
  <div id="app" class="wrapper">
    <b-card class="body" no-body>
      <b-tabs content-class="mt-3" card>
        ...
          <Controls :send="send" />
        ...
      </b-tabs>
    </b-card>
  </div>
</template>

<script lang="ts">
@Component({ components: { Sidebar, GCodeViewer, Terminal, Controls } })
export default class App extends Vue {
  private comms = new CommsBus();

  ...

  public send(req: Request): Promise<Response> { 
    return this.comms.send(req); 
  }
}
</script>
```

Back in [A Better Frontend][abf] we stubbed out the `send_data()` method (the
callback invoked every time the backend wants to send the frontend some data)
with a `TODO` comment and a `console.log()`. Well now we need to implement it 
for real.

Due to the way we've structured the frontend, this is just a case of sending
the data to the `CommsBus` and letting it handle things.

```vue
// frontend/src/App.vue

<script lang="ts">
@Component({ components: { Sidebar, GCodeViewer, Terminal, Controls } })
export default class App extends Vue {
  private comms = new CommsBus();

  ...

  public send(req: Request): Promise<Response> {
    return this.comms.send(req);
  }
}
</script>
```

The frontend should now be able to communicate with the backend. Let's add a
few well-placed `console.log()` calls to `Controls.onHomePressed()` to make this
easier to see.

```vue
// frontend/src/components/Controls.vue

<script lang="ts">
export default class Controls extends Vue {
  ...

  public onHomePressed(e: Event) {
    e.preventDefault();
    console.log("Going Home!");
    this.home()
      .then(resp => console.log(resp.toString(), resp))
      .catch(console.error);
  }
}
</script>
```

We can also hook into the send/receive process so the *Terminal* is able to 
visually display messages. This requires adding a `Messages[]` property which
contains a message, timestamp it was sent/received, and its direction, and will
be passed through to the `Terminal` control as a prop.

```ts
// frontend/src/CommsBus.ts

export default class CommsBus {
    public messages: Message[] = [];
    ...

    public send(req: Request): Promise<Response> {
        if (this.sendToBackend) {
            this.onRequestSent(req);
            ...
        }
    }

    private handlePacket(pkt: Packet) {
        ...

        try {
            const response = parse(pkt);
            this.onResponseReceived(response);
            pending.resolve(response);
        } catch (error) {
            ...
        }
    }

    private onRequestSent(req: Request) {
        this.pushMessage(Direction.Sent, req);
    }

    private onResponseReceived(resp: Response) {
        this.pushMessage(Direction.Received, resp);
    }

    private pushMessage(direction: Direction, value: any) {
        this.messages.push({ direction, value, timestamp: new Date() });
    }
}
```

```vue
// frontend/src/App.vue

<template>
        ...
        <b-tab title="Terminal">
          <Terminal :messages="messages" />
        </b-tab>
        ...
</template>

<script lang="ts">
@Component({ components: { Sidebar, GCodeViewer, Terminal, Controls } })
export default class App extends Vue {
  ...

  public get messages(): Message[] {
    return this.comms.messages;
  }
}
</script>
```


Pressing the *"Home"* button and pulling up the dev tools now shows the backend
responded with a *NACK* (the default response when the backend doesn't know what
to do with a message). 

{{< figure src="console-log.png" title="Progress!" alt="Clicking Home" >}}

## The Next Step

We're now at the point where the frontend can send messages to the backend, and
the backend can send back a response. This unblocks quite a few features, so 
from here we can:

- Start periodically polling the backend to check its status (e.g. axis
  positions, current [*control mode*][cm])
- Read in a g-code program and send it chunk-by-chunk to the backend so it can
  go through the pipeline of `parse -> motion planning -> execute`
- Continue fleshing out the `Controls` with a software-defined handset (e.g. 
  axis jogging)
- Implement more of the communications monitor so we can manually send arbitrary
  messages
- Add more automation sequences

Let me know which one you'd like to see tackled next.

[next-step]: {{< relref "../a-better-frontend/index.md#the-next-step" >}}
[send-data]: https://michael-f-bryan.github.io/adventures-in-motion-control/aimc_sim/struct.Browser.html#method.send_data
[recv-data]: https://michael-f-bryan.github.io/adventures-in-motion-control/aimc_sim/struct.App.html#method.on_data_received
[anpp-ts]: https://www.npmjs.com/package/anpp
[abf]: {{< relref "../a-better-frontend/index.md#wiring-aimc-sim-up-to-the-frontend-again" >}}
[cm]: {{< relref "../initial-motion-system.md" >}}