---
title: "Common Newbie Mistakes and Bad Practices in Rust: Bad Habits"
publishDate: "2021-09-27T18:30:00+08:00"
tags:
- Rust
- Best Practices
series:
- Rust Best Practices
---

When you are coming to Rust from another language you bring all your previous
experiences with you.

Often this is awesome because it means you aren't learning programming from
scratch! However, you can also bring along bad habits which can lead you down
the wrong rabbit hole or make you write bad code.

{{% notice note %}}
The code written in this article is available on the Rust Playground using the
various [(playground)][playground] links dotted throughout. Feel free to browse
through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
[playground]: https://play.rust-lang.org/
{{% /notice %}}

## Using Sentinel Values

This one is a pet peeve of mine.

In most C-based languages (C, C#, Java, etc.), the way you indicate whether
something failed or couldn't be found is by returning a "special" value.  For
example, C#'s [`String.IndexOf()`][index-of] method will scan an array for a
particular element and return its index. Returning `-1` if nothing is found.

That leads to code like this:

```cs
string sentence = "The fox jumps over the dog";

int index = sentence.IndexOf("fox");

if (index != -1)
{
  string wordsAfterFox = sentence.SubString(index);
  Console.WriteLine(wordsAfterFox);
}
```

You see this sort of *"use a sentinel value to indicate something special"*
practice all the time. Other sentinel values you might find in the wild are
`""`, or `null` (someone once referred to this as their
*["billion-dollar mistake"][billion-dollar-mistake]*).

The general reason why this is a bad idea is that there is absolutely nothing to
stop you from forgetting that check. That means you can accidentally crash your
application with one misplaced assumption or when the code generating the
sentinel is far away from the code using it.

We can do a lot better in Rust, though. Just use `Option`!

By design, there is no way to get the underlying value without dealing with
the possibility that your `Option` may be `None`. This is enforced by the
compiler at compile time, meaning code that forgets to check won't even compile.

```rs
let sentence = "The fox jumps over the dog";
let index = sentence.find("fox");

// let words_after_fox = &sentence[index..]; // Error: Can't index str with Option<usize>

if let Some(fox) = index {
  let words_after_fox = &sentence[fox..];
  println!("{}", words_after_fox);
}
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=ed6d6b8ebdd7581a95b0098258b4f371)

## Hungarian Notation

Back in the 70's, a naming convention called [*Hungarian Notation*][hungarian]
was developed by programmers writing in languages where variables are untyped or
dynamically typed. It works by adding a mnemonic to the start of a name to
indicate what it represents, for example the boolean `visited` variable might be
called `bVisited` or the string `name` might be called `strName`.

You can still see this naming convention in languages Delphi where classes
(types) start with `T`, fields start with `F`, arguments start with `A`, and
so on.

```delphi
type
 TKeyValue = class
  private
    FKey: integer;
    FValue: TObject;
  public
    property Key: integer read FKey write FKey;
    property Value: TObject read FValue write FValue;
    function Frobnicate(ASomeArg: string): string;
  end;
```

C# also has a convention that all interfaces should start with `I`, meaning
programmers coming to Rust from C# will sometimes prefix their traits with `I`
as well.

```rs
trait IClone {
  fn clone(&self) -> Self;
}
```

In this case, just drop the leading `I`. It's not actually helping anyone and
unlike in C#, every place a trait it's unambiguous what the thing is and
sensible code shouldn't cause situations where you may confuse traits and types
(trait definitions start with `trait`, trait objects start with `dyn`, you can
*only* use traits in generics/where clauses, etc.).

You also see this inside functions where people will come up with new names for
something as they convert it from one form to another. Often these names are
silly and/or contrived, providing negligible additional useful information to
the reader.

```rs
let account_bytes: Vec<u8> = read_some_input();
let account_str = String::from_utf8(account_bytes)?;
let account: Account = account_str.parse()?;
```

I mean, if we're calling `String::from_utf8()` we already know `account_str`
will be a `String` so why add the `_str` suffix?

Unlike a lot of other languages, Rust encourages shadowing variables when you
are transforming them from one form to another, especially when the previous
variable is no longer accessible (e.g. because it's been moved).

```rs
let account: Vec<u8> = read_some_input();
let account = String::from_utf8(account)?;
let account: Account = account.parse()?;
```

This is arguably superior because we can use the same name for the same concept.

Other languages [frown on shadowing][shadowing] because it can be easy to lose
track of what type a variable contains (e.g. in a dynamically typed language
like JavaScript) or you can introduce bugs where the programmer thinks a
variable has one type but it actually contains something separate.

Neither of these is particularly relevant to a strongly typed language with
move semantics like Rust, so you can use shadowing freely without worrying
about shooting yourself in the foot.

## An Abundance of `Rc<RefCell<T>>`

A common pattern in Object Oriented languages is to accept a reference to some
object so you can call its methods later on.

On its own there is nothing wrong with this, *Dependency Injection* is a very
good thing to do, but unlike most OO languages Rust doesn't have a garbage
collector and has strong feelings on shared mutability.

Perhaps this will be easier to understand with an example.

Say we are implementing a game where the player needs to beat up a bunch of
monsters until they have inflicted a certain amount of damage (I dunno, maybe
it's for a quest or something).

We create a `Monster` class which has a `health` property and a `takeDamage()`
method, and so we can keep track of how much damage has been inflicted we'll let
people provide callbacks that get called whenever the monster receives damage.

```ts
type OnReceivedDamage = (damageReceived: number) => void;

class Monster {
    health: number = 50;
    receivedDamage: OnReceivedDamage[] = [];

    takeDamage(amount: number) {
        amount = Math.min(this.health, amount);
        this.health -= amount;
        this.receivedDamage.forEach(cb => cb(amount));
    }

    on(event: "damaged", callback: OnReceivedDamage): void {
        this.receivedDamage.push(callback);
    }
}
```

Let's also create a `DamageCounter` class which tracks how much damage we've
inflicted and lets us know when that goal is reached.

```ts
class DamageCounter {
    damageInflicted: number = 0;

    reachedTargetDamage(): boolean {
        return this.damageInflicted > 100;
    }

    onDamageInflicted(amount: number) {
        this.damageInflicted += amount;
    }
}
```

Now we'll create some monsters and keep inflicting a random amount of damage
until the `DamageCounter` is happy.

```ts
const counter = new DamageCounter();

const monsters = [new Monster(), new Monster(), new Monster(), new Monster(), new Monster()];
monsters.forEach(m => m.on("damaged", amount => counter.onDamageInflicted(amount)));

while (!counter.reachedTargetDamage()) {
    // pick a random monster
    const index = Math.floor(Math.random()*monsters.length);
    const target = monsters[index];
    // then damage it a bit
    const damage = Math.round(Math.random() * 50);
    target.takeDamage(damage);

    console.log(`Monster ${index} received ${damage} damage`);
}
```

[(TypeScript Playground)](https://www.typescriptlang.org/play?#code/C4TwDgpgBA8gdgJQgYwgSwG4QCYBECGAtvgObQC8UAFIQFxQCyA9nAM7AQBOANFNkaQhJUmHPTgBXQgCMuASijkAfFAxM02ANwAobcgA2+Vq0Yt2XKAG9tUW1AAWEfPuD3xU2Z0VQArAAYdOyhOFHQsPAEyenhhMJwCYjIAbQBdb1SdGztgfABrCATBKiImCThgdxl5Kyyg2xKy4G8GfFcAOkI0OCpXNFY2x2dXXgbyuUC6217+wZd7KABaSlHgTTrauum2kJFwwrI2gDMmTgBRfGR7KmRpRRUbnvs+kcJSsfGNgF9dIJYqCCw5XoACJ+IkcMDeMhnPppBdctFEKFRBFwXJ6GoNDVJlMnv0dnFUYI2mAJKwrtD9LD4R8gt9vnpDMYoPsIABhN4cLzWIJgwQASTgh30aGQHGwlU83gCPzsIQujmwABV8JwyMBWVR0VBpEwmPonHBsTiQsAJJwjVs+WRBcLReKoCoAIx+GV02W2Fis20isU4YqvRqS6o8nFWyIQH32nBQADUy0D5QmtnpumQZia6caFkocAgAHcWRGOdnOFrMum2E1XlWuCZKEk84XmLWy3JeE3TK2tR2C13zG3e82M1we1BOy2B1qUjoawP+sczgqaHcoIQ2n9QRHsJDqAB9F6chTKKBZ8pcDdwb1C33igNHuQfbT5p4G6gAQjPXO2TkuOBVaoQBqEZagooa2AA9BBUBgKKuRQPgwT4HA2BMIQa4jpwGyVuwUBdNgEAAB7NK09hHPoepli07ScMhqGEFqABUc5cv0BpwCQri0nYOFNDkgFNJQLF1kk+FETOGxQVArgQEa1rQGgTSIdIinYRmfARiRNFvNgVDUWRtEoWhWpQIxvh+NxUyquqbQ5PkmryU+QQ4fqEBtBRJBUAABpOXJQAAJJYYmEZ8wTIuEAWWPJoXydQwBMDk+gaeCeE3tGEqRV+F7yVGfrYJ8XkfJ8QA)

Now let's port this code to Rust. Our `Monster` struct is fairly similar,
although we need to use `Box<dyn Fn(u32)>` for a closure which accepts a single
`u32` argument (all closures in JavaScript are heap allocated by default).

```rs
type OnReceivedDamage = Box<dyn Fn(u32)>;

#[derive(Default)]
struct Monster {
    health: u32,
    received_damage: Vec<OnReceivedDamage>,
}

impl Monster {
    fn take_damage(&mut self, amount: u32) {
        let damage_received = cmp::min(self.health, amount);
        self.health -= damage_received;
        for callback in &mut self.received_damage {
            callback(damage_received);
        }
    }

    fn add_listener(&mut self, listener: OnReceivedDamage) {
        self.received_damage.push(listener);
    }
}
```

Next comes our `DamageCounter`, nothing interesting here.

```rs
#[derive(Default)]
struct DamageCounter {
    damage_inflicted: u32,
}

impl DamageCounter {
    fn reached_target_damage(&self) -> bool {
        self.damage_inflicted > 100
    }

    fn on_damage_received(&mut self, damage: u32) {
        self.damage_inflicted += damage;
    }
}
```

And finally our code that inflicts damage.

```rs
fn main() {
    let mut rng = rand::thread_rng();
    let mut counter = DamageCounter::default();
    let mut monsters: Vec<_> = (0..5).map(|_| Monster::default()).collect();

    for monster in &mut monsters {
        monster.add_listener(Box::new(|damage| counter.on_damage_received(damage)));
    }

    while !counter.reached_target_damage() {
        let index = rng.gen_range(0..monsters.len());
        let target = &mut monsters[index];

        let damage = rng.gen_range(0..50);
        target.take_damage(damage);

        println!("Monster {} received {} damage", index, damage);
    }
}
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=cc701dcf7c02510e3406dc1b3abef5d1)

But herein lies our first problem, when we try to compile the code `rustc` gives
us not one, but **four** compile errors for the `monster.add_listener()` line 🤣

```rs
error[E0596]: cannot borrow `counter` as mutable, as it is a captured variable in a `Fn` closure
  --> src/main.rs:47:48
   |
47 |         monster.add_listener(Box::new(|damage| counter.on_damage_received(damage)));
   |                                                ^^^^^^^ cannot borrow as mutable

error[E0499]: cannot borrow `counter` as mutable more than once at a time
  --> src/main.rs:47:39
   |
47 |         monster.add_listener(Box::new(|damage| counter.on_damage_received(damage)));
   |                              ---------^^^^^^^^------------------------------------
   |                              |        |        |
   |                              |        |        borrows occur due to use of `counter` in closure
   |                              |        `counter` was mutably borrowed here in the previous iteration of the loop
   |                              cast requires that `counter` is borrowed for `'static`

error[E0597]: `counter` does not live long enough
  --> src/main.rs:47:48
   |
47 |         monster.add_listener(Box::new(|damage| counter.on_damage_received(damage)));
   |                              ------------------^^^^^^^----------------------------
   |                              |        |        |
   |                              |        |        borrowed value does not live long enough
   |                              |        value captured here
   |                              cast requires that `counter` is borrowed for `'static`
...
60 | }
   | - `counter` dropped here while still borrowed

error[E0502]: cannot borrow `counter` as immutable because it is also borrowed as mutable
  --> src/main.rs:50:12
   |
47 |         monster.add_listener(Box::new(|damage| counter.on_damage_received(damage)));
   |                              -----------------------------------------------------
   |                              |        |        |
   |                              |        |        first borrow occurs due to use of `counter` in closure
   |                              |        mutable borrow occurs here
   |                              cast requires that `counter` is borrowed for `'static`
...
50 |     while !counter.reached_target_damage() {
   |            ^^^^^^^ immutable borrow occurs here
```

There are a number of things wrong with this line, but it can be boiled down to:

- The closure captures a reference to `counter`
- The `counter.on_damage_received()` method takes `&mut self` so our closure
  needs a `&mut` reference. We add the closures in a loop so we end up taking
  multiple `&mut` references to the same object at the same time
- Our listener is a boxed closure without any lifetime annotations, meaning it
  needs to own any variables it closes over. We would need to `move` the
  `counter` into the closure, but because we do this in a loop we'll have a
  *"use of moved value"* error
- After passing the `counter` to `add_listener()` we try to use it in our
  loop condition

Overall it's just a bad situation.

The canonical answer to this is to wrap the `DamageCounter` in a
reference-counted pointer so we can have multiple handles to it at the same
time, then because we need to call a `&mut self` method we also need a `RefCell`
to "move" the borrow checking from compile time to run time.

```diff
 fn main() {
     let mut rng = rand::thread_rng();
-    let mut counter = DamageCounter::default();
+    let mut counter = Rc::new(RefCell::new(DamageCounter::default()));
     let mut monsters: Vec<_> = (0..5).map(|_| Monster::default()).collect();

     for monster in &mut monsters {
-        monster.add_listener(Box::new(|damage| counter.on_damage_received(damage)));
+        let counter = Rc::clone(&counter);
+        monster.add_listener(Box::new(move |damage| {
+            counter.borrow_mut().on_damage_received(damage)
+        }));
     }

-    while !counter.reached_target_damage() {
+    while !counter.borrow().reached_target_damage() {
         let index = rng.gen_range(0..monsters.len());
         let target = &mut monsters[index];
         ...
     }
 }
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=ee5b158751580e9d35a09e1f6300dea5)

Well... it works.  But this approach tends to get messy, especially when you are
storing non-trivial things like a `Rc<RefCell<Vec<Foo>>>>` (or its
multi-threaded cousin `Arc<Mutex<Vec<Foo>>>>`) inside structs [^angle-brackets].

It also opens you up to situations where the `RefCell` might be borrowed mutably
multiple times because your code is complex and something higher up in the call
stack is already using the `RefCell`. With a `Mutex` this will cause a deadlock
while the `RefCell` will panic, neither of which is conducive to a reliable
program.

A much better approach is to change your API to not hold long-lived references
to other objects. Depending on the situation, it might make sense to take a
callback argument in the `Monster::take_damage()` method.

```rs
#[derive(Default)]
struct Monster {
    health: u32,
}

impl Monster {
    fn take_damage(&mut self, amount: u32, on_damage_received: impl FnOnce(u32)) {
        let damage_received = cmp::min(self.health, amount);
        self.health -= damage_received;
        on_damage_received(damage_received);
    }
}

...

fn main() {
    let mut rng = rand::thread_rng();
    let mut counter = DamageCounter::default();
    let mut monsters: Vec<_> = (0..5).map(|_| Monster::default()).collect();

    while !counter.reached_target_damage() {
        let index = rng.gen_range(0..monsters.len());
        let target = &mut monsters[index];

        let damage = rng.gen_range(0..50);
        target.take_damage(damage, |dmg| counter.on_damage_received(dmg));

        println!("Monster {} received {} damage", index, damage);
    }
}
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=5d09c3cfab144142a0c1cdb45848b15e)

A nice side-effect of this is that we get rid of all the callback management
boilerplate, meaning this version is only 47 lines long instead of the
`Rc<RefCell<_>>` version's 62.

Other times it may not be acceptable to give `take_damage()` a callback
parameter, in which case you could return a "summary" of what happened so the
caller can decide what to do next.

```rs
impl Monster {
    fn take_damage(&mut self, amount: u32) -> AttackSummary {
        let damage_received = cmp::min(self.health, amount);
        self.health -= damage_received;
        AttackSummary { damage_received }
    }
}

struct AttackSummary {
    damage_received: u32,
}

...

fn main() {
    let mut rng = rand::thread_rng();
    let mut counter = DamageCounter::default();
    let mut monsters: Vec<_> = (0..5).map(|_| Monster::default()).collect();

    while !counter.reached_target_damage() {
        let index = rng.gen_range(0..monsters.len());
        let target = &mut monsters[index];

        let damage = rng.gen_range(0..50);
        let AttackSummary { damage_received } = target.take_damage(damage);
        counter.on_damage_received(damage_received);

        println!("Monster {} received {} damage", index, damage);
    }
}
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=42e5e0c4160e614f73de5fac425a8833)

This is my preferred solution and it works especially well for larger codebases
or when the code is more complex.

## Using the Wrong Integer Type

Another hang-over from writing a lot of C is using the wrong integer type and
getting frustrated because you need to cast to/from `usize` all the time.

I've seen people run into this [so][array-index-1] [many][array-index-2]
[times][array-index-3] in the wild, especially when indexing.

The underlying problem is that C programmers are all taught to use `int` for
indexing and for-loops, so when they come to Rust and they need to store a list
of indices, the programmer will immediately reach for a `Vec<i32>`. They then
get frustrated because Rust is quite strict when it comes to indexing and
standard types like arrays, slices, and `Vec` can only be indexed using `usize`
(the equivalent of `size_t`), meaning their code is cluttered with casts from
`i32` to `usize` and back again.

There are a number of perfectly legitimate reasons for why Rust only allows
indexing by `usize`:

- It doesn't make sense to have a negative index (accessing items before the
  start of a slice is UB), so we can avoid an entire class of bugs by indexing
  with an unsigned integer
- A `usize` is defined to be an integer with the same size as a normal pointer,
  meaning the pointer arithmetic won't have any hidden casts
- The `std::mem::size_of()` and `std::mem::align_of()` functions return `usize`

Of course, when stated this way the solution is clear. Choose the right integer
type for your application but when you are doing things that eventually be used
for indexing, that "right integer type" is probably `usize`.

[array-index-1]: https://users.rust-lang.org/t/type-of-array-index/53632
[array-index-2]: https://users.rust-lang.org/t/is-there-a-way-to-allow-indexing-vec-by-i32-in-my-program/15755/
[array-index-3]: https://stackoverflow.com/questions/38888724/how-to-index-vectors-with-integer-types-besides-usize-without-explicit-cast?noredirect=1&lq=1

## Unsafe - I Know What I'm Doing

&lt;rant&gt;

There's an old Rust koan on the *User Forums* by Daniel Keep that comes to mind
every time I see a grizzled C programmer reach for raw pointers or
`std::mem::transmute()` because the borrow checker keeps rejecting their code:
[*Obstacles*](https://users.rust-lang.org/t/rust-koans/2408?u=michael-f-bryan).

You should go read it. It's okay, I'll wait.

Too often you see people wanting to hack around privacy, create
self-referencing structs, or create global mutable variables using `unsafe`.
Frequently this will be accompanied by comments like *"but I know this program
will only use a single thread so accessing the `static mut` is fine"* or *"but
this works perfectly fine in C"*.

The reality is that `unsafe` code is nuanced and you need to have a good
intuition for Rust's borrow checking rules and memory model. I hate to be a gate
keeper and say *"you must be this tall to write ~~multi-threaded~~ `unsafe`
code"* [^must-be-this-tall], but there's a good chance that if you are new to
the language you won't have this intuition and are opening yourself and your
colleagues up to a lot of pain.

It's fine to play around with `unsafe` if you are trying to learn more about
Rust or you know what you are doing and are using it legitimately, but `unsafe`
is **not** a magical escape hatch which will make the compiler stop complaining
and let you write C with Rust syntax.

&lt;/rant&gt;

## Not Using Namespaces

A common practice in C is to prefix functions with the name of the library or
module to help readers understand where it comes from and avoid duplicate
symbol errors (e.g. `rune_wasmer_runtime_load()`).

However, Rust has real namespaces and lets you attach methods to types (e.g.
`rune::wasmer::Runtime::load()`). Just use them - it's what they are there for.

## Overusing Slice Indexing

The for-loop and indexing is the bread and butter for most C-based languages.

```rs
let points: Vec<Coordinate> = ...;
let differences = Vec::new();

for i in 1..points.len() [
  let current = points[i];
  let previous = points[i-1];
  differences.push(current - previous);
]
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=62d33c91cf741e9f89b84054cf6a827d)

However, it's easy to accidentally introduce an off-by-one error when using
indexing (e.g. I needed to remember to start looping from `1` and subtract `1`
to get the `previous` point) and even seasoned programmers aren't immune from
crashing due to an index-out-of-bounds error.

In situations like these, Rust encourages you to reach for iterators instead.
The slice type even comes with high-level tools like the `windows()` and
`array_windows()` methods to let you iterate over adjacent pairs of elements.

```rs
let points: Vec<Coordinate> = ...;
let mut differences = Vec::new();

for [previous, current] in points.array_windows().copied() {
  differences.push(current - previous);
}
```

[(playground)](https://play.rust-lang.org/?version=nightly&mode=debug&edition=2018&gist=e647c18bfec0b8d629e5bcbb7b6a66f1)

You could even remove the for-loop and mutation of `differences` altogether.

```rs
let differences: Vec<_> = points
  .array_windows()
  .copied()
  .map(|[previous, current]| current - previous)
  .collect();
```

[(playground)](https://play.rust-lang.org/?version=nightly&mode=debug&edition=2018&gist=030d0b491a2bc8204499f65b38f2aefd)

Some would argue the version with `map()` and `collect()` is cleaner or more
"functional", but I'll let you be the judge there.

As a bonus, iterators can often allow better performance because checks can be
done as part the looping condition instead of being separate[^benchmark-it]
(Alice has a good explanation [here][iter-is-faster]).

## Overusing Iterators

Once you start drinking the Kool-Aid that is Rust's iterators you can run into
the opposite problem - *when all you have is a hammer everything looks like a
nail*.

Long chains of `map()`, `filter()`, and `and_then()` calls can get quite hard to
read and keep track of what is actually going on, especially when type inference
lets you omit a closure argument's type.

Other times your iterator-based solution is just unnecessarily complicated.

As an example, have a look at this snippet of code and see if you can figure
out what it is trying to do.

```rs
pub fn functional_blur(input: &Matrix) -> Matrix {
    assert!(input.width >= 3);
    assert!(input.height >= 3);

    // Stash away the top and bottom rows so they can be
    // directly copied across later
    let mut rows = input.rows();
    let first_row = rows.next().unwrap();
    let last_row = rows.next_back().unwrap();

    let top_row = input.rows();
    let middle_row = input.rows().skip(1);
    let bottom_row = input.rows().skip(2);

    let blurred_elements = top_row
        .zip(middle_row)
        .zip(bottom_row)
        .flat_map(|((top, middle), bottom)| blur_rows(top, middle, bottom));

    let elements: Vec<f32> = first_row
        .iter()
        .copied()
        .chain(blurred_elements)
        .chain(last_row.iter().copied())
        .collect();

    Matrix::new_row_major(elements, input.width, input.height)
}

fn blur_rows<'a>(
    top_row: &'a [f32],
    middle_row: &'a [f32],
    bottom_row: &'a [f32],
) -> impl Iterator<Item = f32> + 'a {
    // stash away the left-most and right-most elements so they can be copied across directly.
    let &first = middle_row.first().unwrap();
    let &last = middle_row.last().unwrap();

    // Get the top, middle, and bottom row of our 3x3 sub-matrix so they can be
    // averaged.
    let top_window = top_row.windows(3);
    let middle_window = middle_row.windows(3);
    let bottom_window = bottom_row.windows(3);

    // slide the 3x3 window across our middle row so we can get the average
    // of everything except the left-most and right-most elements.
    let averages = top_window
        .zip(middle_window)
        .zip(bottom_window)
        .map(|((top, middle), bottom)| top.iter().chain(middle).chain(bottom).sum::<f32>() / 9.0);

    std::iter::once(first)
        .chain(averages)
        .chain(std::iter::once(last))
}
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=da8fa6e55ca5a0de6005b13672688c14)

Believe it or not, but that's one of the more readable versions I've seen...
Now let's look at the imperative implementation.

```rs
pub fn imperative_blur(input: &Matrix) -> Matrix {
    assert!(input.width >= 3);
    assert!(input.height >= 3);

    // allocate our output matrix, copying from the input so
    // we don't need to worry about the edge cases.
    let mut output = input.clone();

    for y in 1..(input.height - 1) {
        for x in 1..(input.width - 1) {
            let mut pixel_value = 0.0;

            pixel_value += input[[x - 1, y - 1]];
            pixel_value += input[[x, y - 1]];
            pixel_value += input[[x + 1, y - 1]];

            pixel_value += input[[x - 1, y]];
            pixel_value += input[[x, y]];
            pixel_value += input[[x + 1, y]];

            pixel_value += input[[x - 1, y + 1]];
            pixel_value += input[[x, y + 1]];
            pixel_value += input[[x + 1, y + 1]];

            output[[x, y]] = pixel_value / 9.0;
        }
    }

    output
}
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=ed5a8cbe8cfab762c32466c551957810)

I know which version I prefer.

## Not Leveraging Pattern Matching

In most other mainstream languages it is quite common to see the programmer
write a check before they do an operation which may throw an exception. Our
C# `IndexOf()` snippet from earlier is a good example of this:

```cs
int index = sentence.IndexOf("fox");

if (index != -1)
{
  string wordsAfterFox = sentence.SubString(index);
  Console.WriteLine(wordsAfterFox);
}
```

Closer to home, you might see code like this:

```rs
let opt: Option<_> = ...;

if opt.is_some() {
  let value = opt.unwrap();
  ...
}
```

or this:

```rs
let list: &[f32] = ...;

if !list.is_empty() {
  let first = list[0];
  ...
}
```

Now both snippets are perfectly valid pieces of code and will never fail, but
similar to [sentinel values](#using-sentinel-values) you are making it easy
for future refactoring to introduce a bug.

Using things like pattern matching and `Option` help you avoid this situation
by making sure the *only* way you can access a value is if it is valid.

```rs
if let Some(value) = opt {
  ...
}

if let [first, ..] = list {
  ...
}
```

{{% notice tip %}}
I'm sure most of you have seen `if let Some(...)` before, but if
`if let [first, ..]` is unfamiliar you may find my article on
[*Slice Patterns*]({{<ref "/posts/daily/slice-patterns">}}) interesting.
{{% /notice %}}

Depending on where it is used and how smart LLVM or your CPU's branch predictor
are, this may also generate slower code because the fallible operation
(`opt.unwrap()` or `list[index]` in that example) needs to do unnecessary checks
[^benchmark-it].

## Initialize After Construction

In many languages, it is normal to call an object's constructor and initialize
its fields afterwards (either manually or by calling some `init()` method),
however this goes against Rust's general convention of *"make invalid states
unrepresentable"*.

Say you are writing a NLP application and have a dictionary containing all the
possible words you can handle.

This is one way you could create the dictionary:

```rs
let mut dict = Dictionary::new();
// read the file and populate some internal HashMap or Vec
dict.load_from_file("./words.txt")?;
```

However, writing `Dictionary` this way means it now has two (hidden) states -
empty and populated.

All downstream code that uses the `Dictionary` will assume it's been populated
already and write code accordingly. This may include doing things like indexing
into the dictionary with `dict["word"]` which may panic if `"word"` isn't there.

Now you've opened yourself up to a situation where passing an empty dictionary
to code that expects a populated dictionary may trigger a panic.

But that's completely unnecessary.

Just make sure the `Dictionary` is usable immediately after constructing it
instead of populating it after the fact.

```rust
let dict = Dictionary::from_file("./words.txt")?;

impl Dictionary {
  fn from_file(filename: impl AsRef<Path>) -> Result<Self, Error> {
    let text = std::fs::read_to_string(filename)?;
    let mut words = Vec::new();
    for line in text.lines() {
      words.push(line);
    }
    Ok(Dictionary { words })
  }
}
```

Internally the `Dictionary::from_file()` might create an empty `Vec` and
populate it incrementally, but it won't be stored in the `Dictionary`'s `words`
field yet so there is no assumption that it is populated and useful.

How frequently you run fall into this anti-pattern depends a lot on your
background and coding style.

Functional languages are often completely immutable so you'll fall into the
idiomatic pattern naturally. It's kinda hard to create a half-initialized thing
and populate it later when you aren't allowed to mutate anything, after all.

On the other hand, OO languages are much happier to let you initialize an object
after it has been constructed, especially because object references can be null
by default and they have no qualms about mutability... You could argue this
contributes to why OO languages have a propensity for crashing due to an
unexpected `NullPointerException`.

## Defensive Copies

To point out the obvious, a really nice property of immutable objects is that
you can rely on them to never change. However, in languages like Python and
Java, immutability isn't transitive - i.e. if `x` is an immutable object, `x.y`
isn't guaranteed to be immutable unless it was explicitly defined that way.

This means it's possible to write code like this...

```py
class ImmutablePerson:
  def __init__(self, name: str, age: int, addresses: List[str]):
    self._name = name
    self._age = age
    self._addresses = addresses

  # read-only properties
  @property
  def name(self): return self._name
  @property
  def age(self): return self._age
  @property
  def addresses(self): return self._addresses
```

Then someone else comes along and accidentally messes up the address list as
part of their normal code.

```py
def send_letters(message: str, addresses: List[str]):
  # Note: the post office's API only works with with uppercase letters so we
  # need to pre-process the address list
  for i, address in enumerate(addresses):
    addresses[i] = addresses.upper()

  client = PostOfficeClient()
  client.send_bulk_mail(message, addresses)


person = ImmutablePerson("Joe Bloggs", 42, ["123 Fake Street"])

send_letters(
  f"Dear {person.name}, I Nigerian prince. Please help me moving my monies.",
  person.addresses
)

print(person.addresses) # ["123 FAKE STREET"]
```

While I admit the example is a bit contrived, it's not uncommon for functions to
modify the arguments they are given. Normally this is fine, but when your
`ImmutablePerson` assumes its `addresses` field will never change, it's annoying
for some random piece of code on the other side of the project to modify it
without you knowing.

The typical solution to this is to preemptively copy the list so even if the
caller tries to mutate its contents, they'll be mutating a copy and not the
original `addresses` field.

```py
class ImmutablePerson:
  ...

  @property
  def addresses(self): return self._addresses.copy()
```

In general, you'll see defensive copies being used anywhere code wants to be
sure that another piece of code won't modify some shared object at an
inopportune time.

Considering this is an article about Rust, you've probably guessed what the
root cause of this is - a combination of aliasing and mutation.

You've also probably guessed why defensive copies aren't really necessary when
writing Rust code - lifetimes and the "shared immutable XOR single mutable" rule
for references means it just isn't possible for code to modify something without
first asking its original owner for mutable access or explicitly opting into
shared mutation by using a type like `std::sync::Mutex<T>`.

{{% notice note %}}
You *may* sometimes see people using `clone()` to get around borrow checker
errors, and exclaim *"Ha! See, Rust forces you to make defensive copies too!"*

To which I would argue that these copies are mostly caused by a lack of
familiarity with lifetimes, or an architecture issue which forces the programmer
to make more copies than they need to.
{{% /notice %}}

## Conclusions

There are a bunch of other bad habits that I haven't had a chance to touch on
or which weren't included because I couldn't come up with a concise example.

Thanks to everyone that replied to [my post][post] on the Rust User Forums with
suggestions for bad habits. Even though I kinda derailed the thread towards the
end with talk about DI frameworks, it was really interesting to hear war stories
from other veteran Rustaceans 🙂

[^must-be-this-tall]: [*Must be This Tall to Write Multi-Threaded Code* - Bobby Holley](https://bholley.net/blog/2015/must-be-this-tall-to-write-multi-threaded-code.html)

[^benchmark-it]: Don't just listen to some random guy on the internet. If you
  care about performance then write a benchmark.

[^angle-brackets]: Out of curiosity, how many people noticed there are 4 `>`'s
  in `Rc<RefCell<Vec<Foo>>>>` but only 3 `<`'s?

[post]: https://users.rust-lang.org/t/common-newbie-mistakes-or-bad-practices/64821
[index-of]: https://docs.microsoft.com/en-us/dotnet/api/system.string.indexof?view=net-5.0
[hungarian]: https://en.wikipedia.org/wiki/Hungarian_notation
[shadowing]: https://rules.sonarsource.com/cpp/RSPEC-1117
[train-wreck]: https://wiki.c2.com/?TrainWreck
[billion-dollar-mistake]: https://www.infoq.com/presentations/Null-References-The-Billion-Dollar-Mistake-Tony-Hoare/
[iter-is-faster]: https://users.rust-lang.org/t/we-all-know-iter-is-faster-than-loop-but-why/51486/7?u=michael-f-bryan
