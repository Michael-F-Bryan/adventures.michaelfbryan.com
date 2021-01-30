---
title: "Parsing PDF Documents in Rust"
date: "2021-01-30T21:52:10+08:00"
draft: true
tags:
- Rust
---

In my spare time I'm a volunteer with my state's emergency services and we
have our own web app for managing unit-specific things like attendance, vehicle
checks, newsletters, and so on.

It's actually a really useful tool, but there is one feature that really
annoys me... The list of member contact details is only available as a PDF
and not a form that can be imported into your phone's contacts. This means if
you need to contact someone, you first need to download the contact list to
your phone, zoom in so you can read the table's rows, find the person's name,
then pan over to their phone number.

I need to do this infrequently enough that it's not worth manually creating a
new contact, but just often enough to be annoying. It'd be *really* nice if I
just needed to download the contact list once and have all the information
available on my phone.

I've contacted one of the developers to see if we can get a better solution
but in the meantime figured that, as a programmer, I should be able to
[bodge][bodge] something together.

{{% notice note %}}
Unfortunately the code written in this article isn't publicly available
because it contains personally identifiable information.

If you found this useful or spotted a bug, let me know on the blog's [issue
tracker][issue]!

[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}

## What's in a PDF?

So our first job is to take a PDF document like this...

![Screenshot of a PDF containing a table with redacted cells](/img/contact-list.png)


... and extract the data in the table.

That's easy enough, there is already a Rust crate (unsurprisingly called
[`pdf`][crate]) for parsing PDF documents so we can reuse that.

For these sorts of jobs, it's just a case of reading
[the crate's API docs][online-docs] and using the provided functionality to
get at the information you want.

After a bit of clicking through I figured out that [`pdf::file::File`][file]
represented the overall document and was just a fancy list of
[`pdf::object::Page`s][page], where a `Page`'s [content][content] is just a
list of [`Operation`s][operation]... And that's where my understanding of PDF
documents was completely turned on its head.

You see, I used to believe that a PDF was a declarative format containing a
bunch of high-level objects like `Table` and `Heading` and so on, almost like
HTML... However, after skimming through [the PDF format spec][reference] from
Adobe (which is itself a PDF - how meta!) it was evident that PDF is more
like an interpreted language where you'll go through each `Operation` in a
page executing draw calls and updating the renderer's state as you go.

That makes things interesting.

It means I can't just look for a (hypothetical) `Table` object and iterate
over its `cells` field. Instead I'll need to iterate over every instruction
and keep track of the current state.

These instructions are pretty low-level, too. Here are (as best I can tell) the
instructions for drawing the *"Surname"* and *"First Name"* cells.

```postscript
BT :
Td : 31.19, 555.43
Tj : "Surname"
ET :
Q :
re : 184.26, 566.93, 155.91, -17.01
f :
m : 184.26, 566.93
l : 184.26, 549.92
S :
m : 184.26, 566.93
l : 340.16, 566.93
S :
m : 340.16, 566.93
l : 340.16, 549.92
S :
q :
g : 0
BT :
Td : 187.09, 555.43
Tj : "First Name"
ET :
```

Luckily the PDF reference from earlier included a table explaining the different
op-codes.

| Op-code | Description              |
| ------- | ------------------------ |
| BT      | Begin Text               |
| ET      | End Text                 |
| g       | Set Grey Level           |
| l       | Line To                  |
| m       | Move To                  |
| Q       | Restore graphics state   |
| q       | Save graphics state      |
| re      | Append rectangle to path |
| S       | Stroke                   |
| Td      | Move text position       |
| Tj      | Show text                |

So PDF documents don't even contain tables, it's all just a lie!

That means to identify the rows and cells in a document I'll need to find
each of the text objects (everything between `BT` and `ET` operations) and do
something funky with their coordinates.

First, I'll create something to represent text objects and stub out a type
which we can take a stream of `Operation`s and turn them into a stream of
`TextObject`s.

```rust
// src/lib.rs

fn text_objects(operations: &[Operation]) -> impl Iterator<Item = TextObject<'_>> + '_ {
    TextObjectParser {
        ops: operations.iter(),
    }
}

#[derive(Debug, Clone, PartialEq)]
struct TextObject<'src> {
    pub x: f32,
    pub y: f32,
    pub text: Cow<'src, str>,
}

#[derive(Debug, Clone)]
struct TextObjectParser<'src> {
    ops: std::slice::Iter<'src, Operation>,
}
```

Turning `TextObjectParser` into an `Iterator` turned out to be pretty easy
thanks to pattern matching.

The idea is that every time someone calls `TextObjectParser`'s `next()` method
we'll keep consuming `Operation`s, updating some temporary state, until we see
an `"ET"` operation.

```rust
// src/lib.rs

impl<'src> Iterator for TextObjectParser<'src> {
    type Item = TextObject<'src>;

    fn next(&mut self) -> Option<Self::Item> {
        let mut last_coords = None;
        let mut last_text = None;

        while let Some(Operation { operator, operands }) = self.ops.next() {
            match (operator.as_str(), operands.as_slice()) {
                ("BT", _) => {
                    // Clear all prior state because we've just seen a
                    // "begin text" op
                    last_coords = None;
                    last_text = None;
                }
                ("Td", [Primitive::Number(x), Primitive::Number(y)]) => {
                    // "Text Location" contains the location of the text on the
                    // current page.
                    last_coords = Some((*x, *y));
                }
                ("Tj", [Primitive::String(text)]) => {
                    // "Show text" - the operation that actually contains the
                    // text to be displayed.
                    last_text = text.as_str().ok();
                }
                ("ET", _) => {
                    // "end of text" - we should have finished this text object,
                    // if we got all the right information then we can yield it
                    // to the caller. Otherwise, use take() to clear anything
                    // we've seen so far and continue.
                    if let (Some((x, y)), Some(text)) = (last_coords.take(), last_text.take()) {
                        return Some(TextObject { x, y, text });
                    }
                }
                _ => continue,
            }
        }

        None
    }
}
```

This isn't a serious program, so it means we can tailor it to work *just* for
the contact list PDF and not worry about recognising arbitrary tables (which
would easily require an order of magnitude more effort).

To identify "rows" I'm just going to group items by their vertical location.
That means we'll be including all bits of text in the document and treating them
as rows with one column, but they can be filtered out later.

There is a `group_by()` method in [the `itertools` crate][itertools], but I
figured I may as well roll my own because this is just a simple project and
`group_by()` is only 50 lines or so.

Don't be intimidated by the number of generics and the complicated `where`-clause,
all will be explained in a sec.

```rust
// src/lib.rs

use std::{iter::Peekable, marker::PhantimData};

pub fn group_by<I, F, K>(iterator: I, grouper: F) -> impl Iterator<Item = Vec<I::Item>>
where
    I: IntoIterator,
    F: FnMut(&I::Item) -> K,
    K: PartialEq,
{
    GroupBy {
        iter: iterator.into_iter().peekable(),
        grouper,
        _key: PhantomData,
    }
}

struct GroupBy<I: Iterator, F, K> {
    iter: Peekable<I>,
    grouper: F,
    _key: PhantomData<fn() -> K>,
}
```

The idea is we'll take something which can be turned into an iterator and
invoke the specified function to get some sort of "key".

From there we can just keep popping items off the iterator until we find an
item with a different key (or run out of items). That tells us we've found
all items in the group and can yield the group to the caller.

```rust
// src/lib.rs

impl<I, F, K> Iterator for GroupBy<I, F, K>
where
    I: Iterator,
    F: FnMut(&I::Item) -> K,
    K: PartialEq,
{
    type Item = Vec<I::Item>;

    fn next(&mut self) -> Option<Self::Item> {
        let first_item = self.iter.next()?;
        let key = (self.grouper)(&first_item);

        let mut items = vec![first_item];

        while let Some(peek) = self.iter.peek() {
            if (self.grouper)(peek) != key {
                break;
            }

            items.push(
                self.iter
                    .next()
                    .expect("Peek guarantees there is another item"),
            );
        }

        Some(items)
    }
}
```

{{% notice note %}}
Something I like about this implementation is that we can use the `?` operator
at the very top to return early when the underlying stream of items is empty.

That reduces a lot of the complexity, whereas your typical for-loop
implementation would constantly need to handle the case where there may or
may not be a `key` yet.
{{% /notice %}}

## Parsing the Contact List

Now we've got some primitives for extracting text from a page and grouping it
into rows, let's make some functions for parsing member information from a
`Page`.

I've decided to represent the parsed data as a `ContactList` which contains a
list of `MemberInfo`s.

```rust
// src/lib.rs

pub struct ContactList {
    pub members: Vec<MemberInfo>,
}

pub struct MemberInfo {
    pub first_name: String,
    pub surname: String,
    pub email: String,
    pub mobile: String,
}
```

Using the `text_objects()` and `group_by()` helpers from before, we get a
`parse_members_on_page()` function which looks something like this.

```rust
// src/lib.rs

fn parse_members_on_page(page: &Page) -> Result<Vec<MemberInfo>, Error> {
    let content = match &page.contents {
        Some(c) => c,
        None => return Ok(Vec::new()),
    };

    let text_objects = text_objects(&content.operations);

    let rows = group_by(text_objects, |t| t.y)
        // ignore everything up to the table header
        .skip_while(|row| row[0].text != "Surname")
        // then skip the header
        .skip(1)
        // every row in the contact table is guaranteed to have 6 cells
        .take_while(|row| row.len() == 6);

    let mut info = Vec::new();

    for row in rows {
        info.push(parse_row(row)?);
    }

    Ok(info)
}
```

Again, we only ever want things to work with this PDF so identifying the
table's header is just a case of finding the first "row" where the first cell
contains `"Surname"`.

We also know that our table has 6 columns and that every cell will have
something in it, so that gives us a nice condition to pass to `take_while()`.

Parsing a single row and copying the individual cell text into the
`MemberInfo` is pretty easy to do with slice patterns.

```rust
// src/lib.rs

use heck::TitleCase;

fn parse_row(row: Vec<TextObject<'_>>) -> Result<MemberInfo, Error> {
    match row.as_slice() {
        [TextObject { text: surname, .. },
         TextObject { text: first_name, .. },
         TextObject { text: email, .. },
         TextObject { text: mobile, .. },
         _, _] =>
        {
            Ok(MemberInfo {
                surname: surname.to_title_case(),
                first_name: first_name.to_string(),
                email: email.to_string(),
                mobile: mobile.to_string(),
            })
        }
        other => Err(anyhow::anyhow!(
            "A row should have exactly 6 text fields, found {}",
            other.len()
        )),
    }
}
```

{{% notice note %}}
In the original document, surnames are in UPPERCASE (e.g. `BRYAN`) so we
use [the `heck` crate](https://crates.io/crates/heck) to convert them to the
more useful TitleCase.

I don't particularly want my phone to scream a person's name whenever I get a
message from them.
{{% /notice %}}

We can wrap everything up into a single `parse()` function by iterating over
each page in a `pdf::file::File` and appending the parsed `MemberInfo` to a
list.

```rust
// src/lib.rs

use std::anyhow::{Context, Error};
use pdf::file::File;

pub fn parse(pdf_blob: &[u8]) -> Result<ContactList, Error> {
    let pdf = File::from_data(pdf_blob)
        .context("Unable to parse the data as a PDF")?;

    let mut members = Vec::new();

    for (i, page) in pdf.pages().enumerate() {
        let page = page?;
        let members_on_page = parse_members_on_page(&page)
            .with_context(|| format!("Unable to parse the members on page {}", i + 1))?;

        members.extend(members_on_page);
    }

    Ok(ContactList { members })
}
```

The code itself isn't overly interesting, although I've chosen to use the
`anyhow` crate for managing my errors. That way I can use the `Context`
extension trait to attach useful context to errors so when my code (inevitably)
fails I'll be greeted with something like this...

```text
Error: Unable to parse the contacts list

Caused by:
    0: Unable to parse the members on page 1
    1: Found a row containg "Michael"
```

... Instead of something useless like *"Unable to parse the file"*.

## Exporting to Google Contacts

The final part of our task is exporting the parsed data in a form that *Google
Contacts* can handle.

Rust has a lot of useful libraries for writing command-line utilities, but for
this application we'll only need [the `structopt` crate][structopt] for
declaring something our command-line arguments can be parsed into.

```rust
// src/bin/export-to-google-contacts.rs

use structopt::StructOpt;
use std::path::PathBuf;

#[derive(Debug, Clone, StructOpt)]
pub struct Args {
    #[structopt(short, long, parse(from_os_str),
                help = "The file to parse, or STDIN if not provided.")]
    input: Option<PathBuf>,
    #[structopt(short, long, parse(from_os_str), default_value = "contacts.csv",
                help = "The file to save the contacts to")]
    output: PathBuf,
}
```

We'll also give it a utility method for parsing the input, correctly switching
between a file or `stdin` depending on whether a `--input` argument was
provided.

```rust
// src/bin/export-to-google-contacts.rs

use std::io::Read;
use anyhow::{Context, Error};

impl Args {
    fn input(&self) -> Result<Vec<u8>, Error> {
        match &self.input {
            Some(filename) => std::fs::read(filename)
                .with_context(|| format!("Couldn't read \"{}\"", filename.display())),
            None => {
                let mut buffer = Vec::new();
                io::stdin()
                    .read_to_end(&mut buffer)
                    .context("Unable to read from STDIN")?;
                Ok(buffer)
            }
        }
    }
}
```

According to their docs, *Google Contacts* can import contacts from
[vCards][vcard] or a CSV file. They've provided [a CSV template][csv-template]
so that's what I've decided to export my data as.

Inspecting the `contacts.csv` file shows we've got quite a lot of fields to
choose from.

```console
$ cat ~/Downloads/contacts.csv | sed -e 's/,/\n/g'
Name
Given Name
Additional Name
Family Name
Yomi Name
Given Name Yomi
Additional Name Yomi
Family Name Yomi
Name Prefix
Name Suffix
Initials
Nickname
Short Name
Maiden Name
Birthday
Gender
Location
Billing Information
Directory Server
Mileage
Occupation
Hobby
Sensitivity
Priority
Subject
Notes
Language
Photo
Group Membership
E-mail 1 - Type
E-mail 1 - Value
IM 1 - Type
IM 1 - Service
IM 1 - Value
Website 1 - Type
Website 1 - Value
```

In this case we only have data for a couple fields so all the others can be
skipped.

- `Given Name`
- `Family Name`
- `E-mail 1 - Value`
- `Phone 1 - Type` (will always be `"Mobile"`)
- `Phone 1 - Value`

Because the `export-to-google-contacts` executable is so simple, we can throw
the argument parsing, contact list parsing, and CSV generation all into a single
`main()` function and call it a day.

```rust
// src/bin/export-to-google-contacts.rs

use csv::Writer;
use std::fs::File;

fn main() -> Result<(), Error> {
    let args = Args::from_args();

    let raw = args.input()?;
    let contacts = contacts_parser::parse(&raw)
        .context("Unable to parse the contacts list")?;

    let w = File::create(&args.output)
        .with_context(|| format!("Unable to open \"{}\"", args.output.display()))?;
    let mut csv_writer = Writer::from_writer(w);

    csv_writer.write_record(&[
            "Given Name", "Family Name", "E-mail 1 - Value",
            "Phone 1 - Type", "Phone 1 - Value",
        ])
        .context("Unable to write the header")?;

    for member in &contacts.members {
        let MemberInfo { surname, first_name, email, mobile, .. } = member;

        let row = &[
            first_name.as_str(),
            surname.as_str(),
            email.as_str(),
            "Mobile",
            mobile.as_str(),
        ];

        csv_writer
            .write_record(row)
            .with_context(|| format!("Unable to write \"{} {}\"", first_name, surname))?;
    }

    Ok(())
}
```

Once that is done, we can use `cargo run` to run the program and convert the
contact list PDF to a CSV.

```console
$ cargo run -- -i ~/Downloads/contact-list.pdf
  Finished dev [unoptimized + debuginfo] target(s) in 0.03s
   Running `target/debug/export-to-google-contacts -i /home/michael/Downloads/contact-list.pdf`
$ ls
  Cargo.lock  Cargo.toml  LICENSE_APACHE.md  LICENSE_MIT.md  README.md  src
  target tests contacts.csv
               ^^^^^^^^^^^^
$ wc contacts.csv
  57   70 3196 contacts.csv
```

Now it's just a case of [importing the `contacts.csv`][importing] on a computer
and letting your phone pick it up next time it does a sync.

## Conclusions

This was a fun little experiment!

Honestly, I was expecting it to be a massive pain and that I'd need to
traverse some sort of DOM to extract data, something that tends to be a quite
verbose in statically typed languages.

Taking the time to understand the PDF spec and writing that `text_objects()`
helper really simplified things, though. Instead of needing half a weekend I
was able to hack my way from nothing to 50+ new contacts in under 90 minutes
and 400 lines of code.

Let me know if you find these sorts of *"programming Rust in the real world"*
articles interesting. I always enjoy hearing war stories from fellow
programmers!

[bodge]: https://www.youtube.com/watch?v=lIFE7h3m40U
[crate]: https://crates.io/crates/pdf
[online-docs]: https://docs.rs/pdf/
[file]: https://docs.rs/pdf/0.7.1/pdf/file/struct.File.html
[page]: https://docs.rs/pdf/0.7.1/pdf/object/struct.Page.html
[content]: https://docs.rs/pdf/0.7.1/pdf/content/struct.Content.html
[operation]: https://docs.rs/pdf/0.7.1/pdf/content/struct.Operation.html
[reference]: https://www.adobe.com/content/dam/acom/en/devnet/pdf/pdfs/pdf_reference_archives/PDFReference.pdf
[itertools]: https://docs.rs/itertools/
[vcard]: https://en.wikipedia.org/wiki/VCard
[csv-template]: https://storage.googleapis.com/support-kms-prod/ItcoC4pjx2kK5azWNE4zeEWEckt4W5GkSnLN
[structopt]: https://crates.io/crates/structopt
[importing]: https://support.google.com/contacts/answer/1069522?co=GENIE.Platform%3DDesktop&hl=en&oco=1#zippy=%2Ccant-import-my-contacts%2Cfrom-a-file
