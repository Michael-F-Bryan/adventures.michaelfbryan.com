---
title: "Optimised to the Nth Degree - Grouping Objects by a Common Field"
date: "2020-10-02T19:36:01+08:00"
draft: true
tags:
- C#
- Rust
---

I was perusing the Rust User Forums the other day and came across something
fairly common, [a thread][thread] where a new Rustacean had ported some code
they'd written in another language and seen performance characteristics they
weren't expecting.

Normally this isn't too noteworthy; you'll ask if they ran their code with
`--release`, point out some low hanging fruit like unnecessary clones or
using a better data structure, and call it a day.

But at some point in the conversation we had this exchange (emphasis mine):

> **Michael:** (ran the same code and got some rough times)
>
> Which is about the same as C#... Not bad for a commodity computer in the cloud.
>
> Also keep in mind that C# has a pretty good JIT, so I'd expect the two
> languages to take roughly the same amount of time. **Sure, we could squeeze
> more performance out of the Rust implementation without much difficulty but
> it's nice to compare directly equivalent implementations in both languages**.

To which the <abbr title="Original Poster">OP</abbr> replied,

> **OP:** Could you demonstrate some ways of optimising my code? I'm pretty
> new at Rust...

... And here we are.

{{< figure
    src="https://imgs.xkcd.com/comics/nerd_sniping.png"
    link="https://xkcd.com/356/"
    caption="(obligatory XKCD reference)"
    alt="Nerd Sniping"
>}}

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]

[repo]: https://github.com/Michael-F-Bryan/💩🔥🦀
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## The Original Code

To get an idea of the problem let's look at the original C# code.

We start off by defining some simple types, in this case a `Person` and an
`OccupationGroup` (a group of people with the same occupation).

```cs
// cs/Program.cs

class Person
{
    public string Occupation;
    public int Id;
}

class OccupationGroup
{
    public string Occupation;
    public List<Person> People;
}
```

The main algorithm - and the target of today's discussion - is the
`GroupByOccupation` function.

```cs
// cs/Program.cs

class Program
{
    static List<OccupationGroup> GroupByOccupation(List<Person> people)
    {
        var occupations = new List<OccupationGroup>();
        var occupationMap = new Dictionary<string, OccupationGroup>();

        foreach (Person person in people)
        {
            if (!occupationMap.TryGetValue(person.Occupation, out var occupation))
            {
                occupation = new OccupationGroup
                {
                    People = new List<Person>(),
                    Occupation = person.Occupation
                };

                occupations.Add(occupation);
                occupationMap.Add(person.Occupation, occupation);
            }

            occupation.People.Add(person);
        }

        return occupations;
    }
}
```

We've also got a simple `Main()` function that creates a list of people and
times how long it takes to group them.

```cs
// cs/Program.cs

class Program {
    static void Main(string[] args)
    {
        var iterations = args.Length >= 1 ? int.Parse(args[0]) : 10_000_000;

        var people = new List<Person>();

        people.Add(new Person() { Occupation = "1", Id = -9 });

        for (int i = 0; i < iterations; i++)
        {
            people.Add(new Person() { Occupation = i.ToString(), Id = i });
        }

        var stopwatch = Stopwatch.StartNew();
        var result = GroupByOccupation(people);

        Console.WriteLine("C# processed {0:#,##0} people in {1} at {2:f} us/iteration",
                            iterations,
                            stopwatch.Elapsed.TotalSeconds,
                            stopwatch.Elapsed.TotalMilliseconds * 1000 / iterations);
    }
}
```

I can then use `dotnet` to run the program from the command line for a variety
of iteration counts. This should give us an idea of what we're competing against.

```
$ dotnet build -c release

$./bin/Release/netcoreapp3.1/cs 1
C# processed 1 people in 0.0016289 at 1629.00 us/iteration

$ ./bin/Release/netcoreapp3.1/cs 100
C# processed 100 people in 0.0009528 at 9.53 us/iteration

$ ./bin/Release/netcoreapp3.1/cs 1000
C# processed 1,000 people in 0.0012173 at 1.22 us/iteration

$ ./bin/Release/netcoreapp3.1/cs 1000000
C# processed 1,000,000 people in 0.4604188 at 0.46 us/iteration
```

You can see that with larger and larger iteration counts the time per
iteration decreases.

I'm guessing this is because we've given the JIT a chance to warm up, and
amortised the (once-off) cost of JIT compilation across a larger number of
iterations.

## The Rust Implementation

Now let's look at how the C# code was ported to Rust.

Again, we start with a couple types for managing people.

```rust
// rust/src/main.rs

#[derive(Debug, Eq, PartialEq)]
pub struct Person {
    pub occupation: String,
    pub id: usize,
}

#[derive(Debug, Eq, PartialEq)]
pub struct OccupationGroup<'a> {
    pub occupation: &'a str,
    pub people: Vec<&'a Person>,
}
```

{{% notice note %}}
Notice that the `OccupationGroup` is using borrowing here to avoid
unnecessarily copying the `occupation` string. It's also intended as a "view"
of the original people, so we store a list of `&'a Person` instead taking
ownership.

That's a big **+1** for me 👍
{{% /notice %}}

It looks like the OP did some experimenting before making a thread on the forums
so we get to check out *two* implementations.

The first implementation is almost identical to the C#. You can see they've
used `Rc` and `RefCell` to emulate C#'s garbage collection and mutation.

```rust
// rust/src/v1_refcell.rs

pub fn group_by_occupation(people: &Vec<Person>) -> Vec<OccupationGroup> {
    let mut occupations: Vec<Rc<RefCell<OccupationGroup>>> = vec![];
    let mut occupation_map: HashMap<&str, Weak<RefCell<OccupationGroup>>> =
        HashMap::new();

    for person in people {
        let occupation_group = occupation_map
            .entry(person.occupation.as_str())
            .or_insert_with(|| {
                let new_occupation_refcell =
                    Rc::new(RefCell::new(OccupationGroup {
                        people: vec![],
                        occupation: &person.occupation,
                    }));
                let weak_ref = Rc::downgrade(&new_occupation_refcell);
                occupations.push(new_occupation_refcell);

                weak_ref
            });

        occupation_group
            .upgrade()
            .unwrap()
            .borrow_mut()
            .people
            .push(person);
    }

    occupations
        .into_iter()
        .map(|x| Rc::try_unwrap(x).unwrap().into_inner())
        .collect()
}
```

Just like the C# implementation we,

1. Create a list (`occupations`) for storing our result and a dictionary
   (`occupation_map`) so we can quickly look up `OccupationGroup`s by their name
2. Iterate over each person in the list of people looking up the
   `OccupationGroup` for that person's occupation
3. If an `OccupationGroup` doesn't yet exist we create one, adding a reference
   to it to *both* the `occupations` list, then
4. Add a reference to the current person to that `OccupationGroup`
5. Finally, unwrap all the `Rc<RefCell<OccupationGroup>>`s we stored in
   `occupations` so we can return a flattened `Vec<OccupationGroup>`

The messing about with `Rc` and `RefCell` and `Weak` adds a fair amount of
noise, but it's still quite recognisable as our C# algorithm.

The second implementation uses indices instead of pointers (`Rc<RefCell<_>>`)
and turns out to be a bit cleaner.

```rust
// rust/src/v2_indices.rs

pub fn group_by_occupation(people: &Vec<Person>) -> Vec<OccupationGroup> {
    let mut occupations: Vec<OccupationGroup> = vec![];

    // map to index instead of ref
    let mut occupation_map: HashMap<&str, usize> = HashMap::new();

    for person in people {
        let occupation_index = *occupation_map
            .entry(person.occupation.as_str())
            .or_insert_with(|| {
                let new_occupation = OccupationGroup {
                    people: vec![],
                    occupation: &person.occupation,
                };
                occupations.push(new_occupation);

                occupations.len() - 1
            });

        occupations[occupation_index].people.push(person);
    }

    occupations
}
```

It took me a couple seconds to recognise but you can see we're doing exactly
the same thing - maintain a list of results and some sort of lookup table
which points into that list of results so we can access `OccupationGroup`s by
name. This version just uses indices to avoid the ugliness of `RefCell`'s
internal mutation.

{{% notice note %}}
This approach reminds me of the sentiment that people use indices in Rust as
a workaround for dealing with the borrow checker... but that's a whole other
topic and I don't want to open that can of works right now.
{{% /notice %}}

There's also a `main()` function which will run our two implementations.

```rust
pub fn main() {
    let iterations = std::env::args()
        .nth(1)
        .and_then(|a| a.parse::<isize>().ok())
        .unwrap_or(10_000_000);

    let mut people = vec![Person {
        occupation: "1".to_string(),
        id: -9,
    }];

    for i in 0..iterations {
        people.push(Person {
            occupation: i.to_string(),
            id: i,
        });
    }

    let now = Instant::now();
    let _result = v1_refcell::group_by_occupation(&people);
    let duration = now.elapsed().as_secs_f64();
    println!(
        "Time for RefCell implementation: {} ({:.3} us/iteration)",
        duration,
        duration * 1_000_000.0 / iterations as f64,
    );

    let now = Instant::now();
    let _result = v2_indices::group_by_occupation(&people);
    let duration = now.elapsed().as_secs_f64();

    println!(
        "Time for index implementation: {} ({:.3} us/iteration)",
        duration,
        duration * 1_000_000.0 / iterations as f64,
    );
}
```

Next, let's run the program and see how it compares to the C# implementation.

```
$ cargo run -- 10000000
    Finished dev [unoptimized + debuginfo] target(s) in 0.01s
     Running `target/debug/group_by_occupation 10000000`
Time for RefCell implementation: 44.191034136 (4.419 us/iteration)
Time for index implementation: 32.717441629 (3.272 us/iteration)
```

Oh hang on, I forgot to compile with optimisations.

```
$ cargo run --release -- 10000000
    Finished release [optimized] target(s) in 0.03s
     Running `target/release/group_by_occupation 10000000`
Time for RefCell implementation: 8.12443462 (0.812 us/iteration)
Time for index implementation: 10.627504373 (1.063 us/iteration)
```

[thread]:https://users.rust-lang.org/t/why-is-this-rust-code-slower-than-c/49564
