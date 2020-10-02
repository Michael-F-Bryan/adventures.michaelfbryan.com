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

To which the OP replied,

> **OP:** Could you demonstrate some ways of optimizing my code? I'm pretty
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
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/💩🔥🦀
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## The Original Code

To get an idea of the problem let's look at the original C# code.

We start off by defining some simple types, in this case a `Person` and an
`OccupationGroup` (a group of people with the same occupation).

```cs
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


[thread]:https://users.rust-lang.org/t/why-is-this-rust-code-slower-than-c/49564
