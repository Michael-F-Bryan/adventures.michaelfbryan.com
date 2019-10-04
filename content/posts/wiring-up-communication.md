---
title: "Wiring Up Communication"
date: "2019-10-01T20:51:35+08:00"
draft: true
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

[next-step]: {{< ref "a-better-frontend/index.md#the-next-step" >}}
[send-data]: https://michael-f-bryan.github.io/adventures-in-motion-control/aimc_sim/struct.Browser.html#method.send_data
[recv-data]: https://michael-f-bryan.github.io/adventures-in-motion-control/aimc_sim/struct.App.html#method.on_data_received