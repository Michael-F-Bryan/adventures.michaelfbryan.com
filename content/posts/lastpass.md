---
title: "How I Reverse Engineered the LastPass CLI Tool"
date: "2020-04-13T00:53:39+08:00"
draft: true
tags:
- Rust
- I Made a Thing
---

A couple days ago I was writing an install script for [my dotfiles][dotfiles]
and reached a point where I wanted to grab some secrets (my SSH keys) from my
LastPass vault and copy them to the file system.

This is easy enough to do using the browser plugin, or even when working with
their [command line tool (`lpass`)][lastpass-cli] in an interactive way, but
I found there was no way to ask `lpass` which files are attached to a secret,
and get the output in a machine readable format.

Like most self-respecting members of the open-source community, I
[filed an issue][issue-547] on their GitHub page and started digging into the
source code to find where changes might need to be made. That way I can make
the change myself if it's easy enough, or I'll be able to provide someone else
with a bit more information.

However, reading through the source code got me thinking. There currently
aren't any libraries for working with LastPass, and although the `lpass`
tool's source code is GPL'd and on GitHub, by reading the source code you can
quickly tell it was only ever intended as a command-line tool.

Soo..... Why not rewrite it in Rust?

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/lastpass
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## A Quick Note On Goals

In the long run, I'd like for this to be a fully-featured library for working
with a LastPass vault. Although, in the short term I'm going to make a beeline
for downloading and decrypting attachments, seeing as that was the original
inspiration for this endeavour.

Someone may want to create a nice command-line tool on top of the library, but
I don't have any intention of being that someone (for now, anyways).

I've also got a lot of experience writing FFI code, so I'm intending to write
bindings so the library is usable from Python (my dotfiles install script is
written in Python) and C. I might wait a bit to flesh out the crate's API
though, that way I'll have a better idea of how the bindings should be
consumed and it'll reduce unnecessary code churn.

The `lpass` tool has roughly three responsibilities,

1. Communicate with the LastPass HTTP API
2. Perform the appropriate crypto so we can encrypt/decrypt the LastPass vault
3. Use the file system and a daemon to allow caching of the vault and persist
   login sessions across multiple invocations of the `lpass` command (e.g. so
   you don't need to keep entering your master password every time)

As a library, the third point is usually left up to the frontend application
so we've already made our job easier.

I'd also consider the HTTP bit a solved problem. The [`reqwest`][reqwest]
crate provides a robust and fully-featured asynchronous HTTP client, and we
can leverage [`serde`][serde]'s serialisation superpowers to make sending or
receiving structured data a breeze.

I'm a little worried about the crypto side of things. On one hand, we don't
need to implement any cryptography routines ourselves (the [`aes`][aes] and
[`pbkdf2`][pbkdf2] crates already exist and are well-respected), but it's
easy to mess things up an accidentally introduce a security vulnerability.

I figure the best course of action here is to just copy what `lpass` do.

{{% notice warning %}}
If you've read this far hopefully you've realised this isn't one of those
*"LastPass is broken!"* posts. I'm just reverse-engineering how the `lpass`
program works so I can implement it myself.

If anything, after spending several hours banging my head against a wall and
trying to figure out why things weren't working, I can assure you that the
LastPass does a pretty good job at keeping people out.
{{% /notice %}}

## Baby Steps

After creating the repository, the first thing to do is get a copy of the
`lastpass/lastpas-cli` project so we can refer to the source code when needed.

```console
$ git submodule init
$ git submodule add git@github.com:lastpass/lastpass-cli.git vendor/lastpass-cli
Cloning into '/home/michael/Documents/lastpass/vendor/lastpass-cli'...
remote: Enumerating objects: 2388, done.
remote: Total 2388 (delta 0), reused 0 (delta 0), pack-reused 2388
Receiving objects: 100% (2388/2388), 821.19 KiB | 463.00 KiB/s, done.
Resolving deltas: 100% (1565/1565), done.
```

There are a couple strategies you can use when trying to reverse engineer an
existing application. The *Bottom-Up* strategy involves finding the snippet
of code you care about (e.g. sending a HTTP request to the login endpoint)
and tracing backwards to see how you construct the right inputs. On the other
hand, the *Top-Down* approach starts at `main()` and steps through the program
until you hit the juicy parts, similar to how a debugger works.

My first aim will be to log in and get any necessary session tokens. I know the
LastPass API endpoint for logging in will almost certainly be a string starting
with `login`, so we can start from there.

```console
$ rg '"login' vendor/lastpass-cli
vendor/lastpass-cli/endpoints.c
236:	reply = http_post_lastpass("login_check.php", session, NULL, "method", "cli", NULL);

vendor/lastpass-cli/endpoints-login.c
170:	*reply = http_post_lastpass_v(login_server, "login.php", NULL, NULL, args);
228:	        *reply = http_post_lastpass_v(login_server, "login.php", NULL, NULL, args);
296:	        *reply = http_post_lastpass_v(login_server, "login.php", NULL, NULL, args);

vendor/lastpass-cli/contrib/lpass_zsh_completion
116:          "login:Authenticate with the LastPass server and initialize a local cache"

vendor/lastpass-cli/cmd.h
75:#define cmd_login_usage "login [--trust] [--plaintext-key [--force, -f]] " color_usage " USERNAME"
```

I'm guessing the file we're looking for is the aptly-named `endpoints-login.c`.
Opening the file up and jumping to the appropriate lines show there are three
login functions.

```c
// vendor/lastpass-cli/endpoints-login.c

static bool ordinary_login(const char *login_server, const unsigned char key[KDF_HASH_LEN], char **args, char **cause, char **message, char **reply, struct session **session,
			   char **ret_login_server)
{
	char *server;

	free(*reply);
	*reply = http_post_lastpass_v(login_server, "login.php", NULL, NULL, args);
	if (!*reply)
		return error_post(message, session);

	*session = xml_ok_session(*reply, key);
	if (*session) {
		(*session)->server = xstrdup(login_server);
		return true;
	}

	*cause = xml_error_cause(*reply, "cause");
	if (!*cause)
		return error_other(message, session, "Unable to determine login failure cause.");

	*ret_login_server = xstrdup(login_server);
	return false;
}

static bool oob_login(const char *login_server, const unsigned char key[KDF_HASH_LEN], char **args, char **message, char **reply, char **oob_name, struct session **session)
{
    ...

	terminal_fprintf(stderr, TERMINAL_FG_YELLOW TERMINAL_BOLD "Waiting for approval of out-of-band %s login%s" TERMINAL_NO_BOLD "...", *oob_name, can_do_passcode ? ", or press Ctrl+C to enter a passcode" : "");
	append_post(args, "outofbandrequest", "1");
	for (;;) {
		free(*reply);
		*reply = http_post_lastpass_v(login_server, "login.php", NULL, NULL, args);
		if (!*reply) {
			if (can_do_passcode) {
				append_post(args, "outofbandrequest", "0");
				append_post(args, "outofbandretry", "0");
				append_post(args, "outofbandretryid", "");
				xstrappend(oob_name, " OTP");
				goto failure;
			} else {
				error_post(message, session);
				goto success;
			}
		}

        ...
	}

    ...
}

static bool otp_login(const char *login_server, const unsigned char key[KDF_HASH_LEN], char **args, char **message, char **reply, const char *otp_name, const char *cause, const char *username, struct session **session)
{
    ...

	for (;;) {
		multifactor = password_prompt("Code", multifactor_error, "Please enter your %s for <%s>.", otp_name ? otp_name : replied_multifactor->name, username);
		if (!multifactor)
			return error_other(message, session, "Aborted multifactor authentication.");
		append_post(args, replied_multifactor->post_var, multifactor);

		free(*reply);
		*reply = http_post_lastpass_v(login_server, "login.php", NULL, NULL, args);

        ...
    }
}
```

So it looks like there are 3 methods for doing login, I'm guessing the
`ordinary_login()` is for a standard username/password login, and `oob_login()`
and `otp_login()` are for multi-factor authentication where you've got an
out-of-band authentication device (e.g. a USB dongle) or are using an app that
uses one-time-pads (e.g. the Google Authenticator app).

I don't care about multi-factor authentication for now, so let's have a skim
through `ordinary_login()` and try to identify the important bits.

I'm not 100% sure what the `_v` suffix in `http_post_lastpass_v()` means, but
it seems to be a function that sends a HTTP POST request to `lastpass.com`.
The two `NULL` parameters are a pointer to a session (presumably for auth,
but we haven't logged in yet so we don't have one) and a place to put the
`reply` string's length (which we don't care about because it's a
null-terminated string).

From there, it looks like the response body is parsed as XML into a `session`
using `xml_ok_session()`. Interestingly, we need to pass in a `key`, so
presumably parts of the response will be encrypted with our master password.
If parsing was successful, the parsed session is "returned" to the caller via
the `session` pointer and we return. The rest of the function seems to be
around identifying the cause for a login failure, so we can ignore it for the
time being.

Jumping to the function that calls `ordinary_login()`, we reach
`lastpass_login()`.

```c
// vendor/lastpass-cli/endpoints-login.c

struct session *lastpass_login(const char *username, const char hash[KDF_HEX_LEN], const unsigned char key[KDF_HASH_LEN], int iterations, char **error_message, bool trust)
{
	char *args[33];
    ...

	memset(args, 0, sizeof(args));
	append_post(args, "xml", "2");
	append_post(args, "username", user_lower);
	append_post(args, "hash", hash);
	append_post(args, "iterations", iters);
	append_post(args, "includeprivatekeyenc", "1");
	append_post(args, "method", "cli");
	append_post(args, "outofbandsupported", "1");
	if (trusted_id)
		append_post(args, "uuid", trusted_id);

	if (ordinary_login(LASTPASS_SERVER, key, args, &cause, error_message, &reply, &session, &login_server))
		return session;

    ...
}
```

It looks like this is responsible for constructing the POST data and sending
a request to `ordinary_login()`. I've elided the bits afterwards because they
just fall back to the out-of-band and one-time-pad logins, and we don't
really care about that for now.

If you squint at `append_post()` calls in the previous snippet, you'll see
that we're constructing the key-value pairs to submit a HTML form.

At this point we actually know enough to start sending login requests to the
LastPass API.

I'm going to use the HTTP client from the [`reqwest`][reqwest] crate for this.
As well as having nice things like connection pooling, `async`, TLS,
and automatic cookie storage, there's this awesome feature where you can use
anything implementing `serde::Serialize` as the form data.

First, we'll create a struct with all the data to be submitted in the form.

```rust
// src/endpoints/login.rs

use serde_derive::Serialize;

#[derive(Debug, Serialize)]
struct Data<'a> {
    xml: usize,
    username: &'a str,
    hash: &'a str,
    iterations: usize,
    includeprivatekeyenc: usize,
    method: &'a str,
    outofbandsupported: usize,
    uuid: Option<&'a str>,
}
```

Then we can write a function to send this data to the `login.php` endpoint.

```rust
// src/endpoints/login.rs

pub async fn login(
    client: &Client,
    hostname: &str,
    username: &str,
    login_key: &str,
    iterations: usize,
) -> Result<Session, LoginError> {
    let data = Data {
        xml: 2,
        username,
        hash: login_key,
        iterations,
        includeprivatekeyenc: 1,
        method: "cli",
        outofbandsupported: 1,
        trusted_id,
    };
    let url = format!("https://{}/login.php", hostname);
    let response = client
        .post(&url)
        .form(&data)
        .send()
        .await?
        .error_for_status()?;

    let body = response.text().await?;

    unimplemented!("How do we parse the body into a session? {}", body);
}
```

{{% notice note %}}
As a side note, I think the decision to make `await` a postfix operator works
really well with Rust's expression-centric syntax and `?` operator.

Having used async-await in C# and Python, I was initially quite skeptical of
writing `some_expr.await` instead of `await some_expr`, but after having used
it in the real world I think this syntax reduces visual noise and the
unnecessary parentheses or temporary variables you'd normally get when
working with the returned value.

The interaction with the `?` operator also just *"rolls off the tongue"*
(e.g. `let foo = some_expr.await?` instead of `let foo = (await
some_expr)?`).

Nice work, language designers 👍
{{% /notice %}}

I've also taken the liberty of stubbing out a `Session` type based on the
`session` struct in `session.h`.

```rust
// src/session.rs

#[derive(Debug, Clone, PartialEq)]
pub struct Session {
    pub uid: String,
    pub token: String,
    pub private_key: Vec<u8>,
    pub session_id: String,
}


// vendor/lastpass-cli/session.h

struct session {
	char *uid;
	char *sessionid;
	char *token;
	char *server;
	struct private_key private_key;
};
```

I also hacked together [a quick program][main-rs-1] to send requests to
LastPass and dump the login response.

```rust
// src/bin/main.rs

use anyhow::Error;
use reqwest::Client;

use lastpass::endpoints;

#[tokio::main]
async fn main() -> Result<(), Error> {
    env_logger::init();
    let client = Client::builder()
        .user_agent(lastpass::DEFAULT_USER_AGENT)
        .cookie_store(true)
        .build()?;

    endpoints::login(
        &client,
        "lastpass.com",
        "my-test-account@example.com",
        "SUPER_SECRET_LOGIN_KEY_I_GOT_FROM_LPASS",
        100100,
    )
    .await?;

    Ok(())
}
```

{{% notice tip %}}
I don't want to worry about deriving a login key or that `iterations`
variable for now, so I recompiled `lastpass-cli` with debug symbols and ran
`lpass login my-test-account@example.com` under the VS Code debugger to get
the right values.

When you're hacking together a proof-of-concept like this it's okay to use
hard-coded variables. Once we know that we can talk to the LastPass API we
can take a step back, start looking for patterns, and derive nice
abstractions.
{{% /notice %}}

Assuming we used the correct `login_key`, the `login.php` endpoint sends us
back a big blob of XML.

{{% expand "A big blob of XML" %}}
```xml
<?xml version="1.0" encoding="UTF-8"?>
<response>
   <ok sitesver="" formfillver="" bigicon="5617" bigiconenabled="1"
       uid="999999999" language="en-US" sessionid="SESSIONID1234"
       disableoffline="0"
       pushserver="https://lp-push-server-455.lastpass.com/ws/1111111111111111111111111111111111111 main"
       new_save_site="1" first_time_login="0" infield_enabled="1"
       mobile_active="1" ziggy="1" better_generate_password_enabled="1"
       omar_ia="1" retire_3_0="1" family_shared_folders_enabled="1"
       family_legacy_shared_folders_enabled="1" try_families_enabled="1"
       premium_sharing_restricted="1" emergency_access_restricted="1"
       is_families_trial_started="" predates_families="0" seen_vault_post_families="1"
       privatekeyenc="DEADBEEF"
       migrated="0" autofill_https_test="1" nopassword_integration_enabled="1"
       save_a_site_otp="1" site_feedback="1" omar_vault_migration="0" account_version_tracking=""
       blob_version_set="1" yubikeyenabled="0" googleauthenabled="1" microsoftauthenabled="0"
       outofbandenabled="0" serverts="1586587085100000" iconsversion="85" isadmin="0"
       lpusername="michaelfbryan@gmail.com" email="michaelfbryan@gmail.com" loglogins="1"
       client_enc="1" accts_version="198"
       pwdeckey="PASSWORDDECODEKEY"
       hih="0" genh="0" addh="0" seclvl="0" updated_enc="1"
       login_site_prompt="0" edit_site_prompt="0" edit_sn_prompt="0"
       view_pw_prompt="0" view_ff_prompt="0" improve="1"
       switch_identity_prompt="1" switch_f_prompt="0" multifactor_reprompt=""
       multifactor_singlefactor="" singlefactortype="" country="AU" model="3"
       banner="0" ratings_prompt="1" reqdversion="1.39" pollinterval="-1"
       logoff_other_ses="0" generatedpw="0" pageloadthres="800000"
       attachversion="3" pwresetreqd="0" accountlinkrequired="0"
       trialduration="30"
       token="BASE64ENCODEDTOKEN="
       companyadmin="0" iterations="123456" showcredmon="0" adlogin="0"
       note_title="" note_text="" note_button="" note_url=""
       lastchallengets="0" extended_shared_folder_log="0"
       multifactorscore="9" disablepwalerts="0" emailverified="1" prefdata=""
       pbt="1" logloginsvr="loglogin.lastpass.com"
       pollserver="pollserver.lastpass.com" do_totp="1"
      newsettings_enabled = '0' show_extension_popup = '0' is_legacy_premium="0"
      />
</response>
```
{{% /expand  %}}

Considering the `Session` struct only has a handful of fields, it's safe to
assume most of this is unnecessary information that's probably used by other
LastPass products (e.g. their browser extension).

To see how the relevant information is extracted, I'm going to look at the
`xml_ok_session()` function (which tries to parse the happy case out of the XML)
and see if anything jumps out.

```c
// vendor/lastpass-cli/xml.c

#include "xml.h"
#include "util.h"
#include "blob.h"
#include <string.h>
#include <libxml/parser.h>
#include <libxml/tree.h>
#include <errno.h>

struct session *xml_ok_session(const char *buf, unsigned const char key[KDF_HASH_LEN])
{
	struct session *session = NULL;
	xmlDoc *doc = NULL;
	xmlNode *root;
	doc = xmlReadMemory(buf, strlen(buf), NULL, NULL, 0);

	if (!doc)
		goto out;

	root = xmlDocGetRootElement(doc);
	if (root && !xmlStrcmp(root->name, BAD_CAST "response")) {
		for (root = root->children; root; root = root->next) {
			if (!xmlStrcmp(root->name, BAD_CAST "ok"))
				break;
		}
	}
	if (root && !xmlStrcmp(root->name, BAD_CAST "ok")) {
		session = session_new();
		for (xmlAttrPtr attr = root->properties; attr; attr = attr->next) {
			if (!xmlStrcmp(attr->name, BAD_CAST "uid"))
				session->uid = (char *)xmlNodeListGetString(doc, attr->children, 1);
			if (!xmlStrcmp(attr->name, BAD_CAST "sessionid"))
				session->sessionid = (char *)xmlNodeListGetString(doc, attr->children, 1);
			if (!xmlStrcmp(attr->name, BAD_CAST "token"))
				session->token = (char *)xmlNodeListGetString(doc, attr->children, 1);
			if (!xmlStrcmp(attr->name, BAD_CAST "privatekeyenc")) {
				_cleanup_free_ char *private_key = (char *)xmlNodeListGetString(doc, attr->children, 1);
				session_set_private_key(session, key, private_key);
			}
		}
	}
out:
	if (doc)
		xmlFreeDoc(doc);
	if (!session_is_valid(session)) {
		session_free(session);
		return NULL;
	}
	return session;
}
```

Looking at just the string literals, it seems like we're expecting a root
`<ok>` node. From there we skim through the `<ok>` node's attributes and copy
`"uid"`, `"sessionid"`, `"token"`, and `"privatekeyenc"` to the relevant
fields on `session`.

That seems easy enough.

I'll be using the [`serde_xml_rs`][serde-xml-rs] crate to parse the response
document. This lets us declaratively define how an "ok" document should look,
then lean on `serde` and `serde_xml_rs` to do the heavy lifting.

```rust
// src/endpoints/login.rs

#[derive(Debug, Deserialize)]
struct Document {
    #[serde(rename = "$value")]
    root: Root,
}

#[derive(Debug, Deserialize)]
enum Root {
    #[serde(rename = "ok")]
    Ok {
        uid: String,
        /// A base64-encoded token.
        token: String,
        #[serde(rename = "privatekeyenc")]
        private_key: String,
        /// The PHP session ID.
        #[serde(rename = "sessionid")]
        session_id: String,
        /// The user's username.
        #[serde(rename = "lpusername")]
        username: String,
        /// The user's primary email address
        email: String,
    },
    ...
}
```

Now we've got something that represents the document schema, we actually have
everything we need to parse it into a `Session`.

```rust
// src/endpoints/login.rs

pub async fn login(
    client: &Client,
    hostname: &str,
    username: &str,
    login_key: &str,
    iterations: usize,
) -> Result<Session, LoginError> {
    ...

    let body = response.text().await?;
    let doc: Document = serde_xml_rs::from_str(&body)?;

    interpret_response(doc.root)
}

fn interpret_response(root: Root) -> Result<Session, LoginError> {
    match root {
        Root::Ok {
            uid,
            token,
            private_key,
            session_id,
            username,
            ..
        } => Ok(Session { uid, token, private_key, session_id }
        ...
    }
}
```

While it may seem like we've written a lot of code our quick'n'dirty login
function, complete with error handling code (which I've skipped for simplicity),
and a test program, only took about 100 lines of Rust.

The vast majority of time was actually spent reading through the
`lastpass-cli` project's source code and figuring out how all the components
interact. This was made a lot harder because C promotes a culture of
[*Primitive Obsession*][primitive-obsession], so everything is a `char *`
(the login key is a `char *`, the response is a `char *`, errors are a `char *`,
the key-value pairs for our POST form is a `char **` array where even
items are keys and odd items are values, etc.). The lack of generics and RAII
also makes it hard to create nice layers of abstraction in a C program because
you are constantly interspersing business logic with memory management, or
you need to [implement your own doubly-linked list][doubly-linked-list].

## Creating an Abstraction for Key Management

<!--
    TODO: write about
    - what keys are needed to log in?
    - how do I get the iteration count?
    - generate a login key
    - generate a decryption key
    - implement decryption routines for DecryptionKey
 -->

## Parsing the Vault Into Memory
<!--
    TODO: write about
    - grab a copy of the vault
    - what are chunks?
    - what's with the big if-else chain?
    - parsing account info
    - parsing attachment metadata
 -->

## Downloading Attachments
<!--
    TODO: write about
    - download the attachment
    - decrypting the filename
    - decrypting the account's attachment key
    - using the attachment key to decode the attachment
    - turn it back into binary (from base64)
    - put it all together in an example application
 -->


## Conclusions

I enjoyed playing around with crypto again, even though I barely went further
than passing around keys and calling library functions, it's a big difference
to the code I write at my day job.

I'm also surprised at how easy this was to implement. Rust has a really nice
ecosystem, and thanks to the work of projects like [`serde`][serde],
[`reqwest`][reqwest], and [RustCrypto][rust-crypto], I have all the necessary
pieces at my fingertips. The hardest bit was deciphering the `blob` parsing
code, and that's because it was written in C.

Oh, and I'm still working on [my dotfiles script][install-py] by the way.
It's massively over-engineered, but there's no kill like overkill, after all.

{{% notice note %}}
Also I'd be keen to hear from you if you are a developer from LastPass! What
are your thoughts on my efforts? Has the analysis been accurate, and can you
spot any bugs or issues?

I feel like having an official library that lets developers work with the
LastPass API can enable a lot of benefits for customers, and I'd like to help
out on that front.
{{% /notice %}}

[dotfiles]: https://github.com/Michael-F-Bryan/dotfiles
[lastpass-cli]: https://github.com/lastpass/lastpass-cli
[issue-547]: https://github.com/lastpass/lastpass-cli/issues/547
[cleanup]: https://gcc.gnu.org/onlinedocs/gcc/Common-Variable-Attributes.html#index-cleanup-variable-attribute
[install-py]: https://github.com/Michael-F-Bryan/dotfiles/blob/master/install.py
[reqwest]: https://crates.io/crates/reqwest
[serde]: https://serde.rs/
[aes]: https://crates.io/crates/aes
[pbkdf2]: https://crates.io/crates/pbkdf2
[rust-crypto]: https://github.com/RustCrypto
[main-rs-1]: https://github.com/Michael-F-Bryan/lastpass/blob/0a5da0262548d475e81138f91a22fa125658ea3e/src/bin/main.rs
[serde-xml-rs]: https://crates.io/crates/serde_xml_rs
[primitive-obsession]: https://refactoring.guru/smells/primitive-obsession
[doubly-linked-list]: https://github.com/lastpass/lastpass-cli/blob/8767b5e53192ad4e72d1352db4aa9218e928cbe1/list.h
