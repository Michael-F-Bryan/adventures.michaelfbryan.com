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

    let session = endpoints::login(
        &client,
        "lastpass.com",
        "my-test-account@example.com",
        "SUPER_SECRET_LOGIN_KEY_I_GOT_FROM_LPASS",
        100100,
    )
    .await?;

    println!("Logged in as my-test-account@example.com {:#?}", session);

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
       lpusername="my-test-account@example.com" email="my-test-account@example.com" loglogins="1"
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

Running the test program shows we've got an actual session.

```console
$ cargo run
Logged in as my-test-account@example.com Session {
    uid: "123456789",
    token: "X3BYcEFjRDFZYlRoVG42r1kTj/UvbBGar2zRpDXgzQyIbQpCMkocUHSFS3AMt3duyU4=",
    private_key: "DEADBEEFCAFEBABE",
    session_id: "3d,UxdQVzFSznYkCXfYXabP2Bw8",
}
```

Success!

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

Now that we're able to log in, let's start getting rid of those hard-coded
values.

### Login Keys

The first thing I'd like to do is create a `LoginKey`. After a little digging,
it looks like we use `kdf_login_key()` to derive the login key based on the
user's username and master password.

```c
// vendor/lastpass-cli/kdf.c

void kdf_login_key(const char *username, const char *password, int iterations, char hex[KDF_HEX_LEN])
{
	unsigned char hash[KDF_HASH_LEN];
	size_t password_len;
	_cleanup_free_ char *user_lower = xstrlower(username);

	password_len = strlen(password);

	if (iterations < 1)
		iterations = 1;

	if (iterations == 1) {
		sha256_hash(user_lower, strlen(user_lower), password, password_len, hash);
		bytes_to_hex(hash, &hex, KDF_HASH_LEN);
		sha256_hash(hex, KDF_HEX_LEN - 1, password, password_len, hash);
	} else {
		pbkdf2_hash(user_lower, strlen(user_lower), password, password_len, iterations, hash);
		pbkdf2_hash(password, password_len, (char *)hash, KDF_HASH_LEN, 1, hash);
	}

	bytes_to_hex(hash, &hex, KDF_HASH_LEN);
	mlock(hex, KDF_HEX_LEN);
}
```

Now we can see that the `iterations` parameter is used by [PBKDF2][pbkdf2] to
increase the number of times the hash is applied, allowing the algorithm to
scale as hardware gets faster.

As a special case, when `iterations <= 1` we do two passes through SHA-256.
This looks like a backwards compatibility thing, where the `LoginKey` used by
older servers or accounts was computed using SHA-256 and they later
transitioned to PBKDF2 for increased security.

Looking through the source code we can see that a login key is `KDF_HASH_LEN`
bytes long, or about 64 bytes + 1 for a null terminator.

```c
// /usr/include/openssl/sha.h

# define SHA256_DIGEST_LENGTH    32


// vendor/lastpass-cli/kdf.h

#include <openssl/sha.h>

#define KDF_HASH_LEN SHA256_DIGEST_LENGTH
#define KDF_HEX_LEN (KDF_HASH_LEN * 2 + 1)
```

This tells us enough to define a `LoginKey`. For now it's just a newtype around
a `[u8; 64]` array.

```rust
// src/keys/login_key.rs

/// A hex-encoded hash of the username and password.
pub struct LoginKey([u8; LoginKey::LEN]);

const KDF_HASH_LEN: usize = 32;

impl LoginKey {
    pub const LEN: usize = KDF_HASH_LEN * 2;
}
```

You can create a `LoginKey` using the `LoginKey::calculate()` constructor. This
just defers to `LoginKey::sha256()` and `LoginKey::pbkdf2()` based on the number
of iterations.

```rust
// src/keys/login_key.rs

impl LoginKey {
    ...

    /// Calculate a new [`LoginKey`].
    pub fn calculate(
        username: &str,
        password: &str,
        iterations: usize,
    ) -> Self {
        let username = username.to_lowercase();

        if iterations <= 1 {
            LoginKey::sha256(&username, password)
        } else {
            LoginKey::pbkdf2(&username, password, iterations)
        }
    }

    fn sha256(username: &str, password: &str) -> Self { unimplemented!() }

    fn pbkdf2(username: &str, password: &str, iterations: usize) -> Self { unimplemented!() }
}
```

I'll start with the `LoginKey::sha256()` constructor because that seems easiest,
so let's have a look at the `sha256_hash()` function used by `lastpass-cli`.

```rust
// vendor/lastpass-cli/kdf.c

static void sha256_hash(const char *username, size_t username_len, const char *password, size_t password_len, unsigned char hash[KDF_HASH_LEN])
{
	SHA256_CTX sha256;

	if (!SHA256_Init(&sha256))
		goto die;
	if (!SHA256_Update(&sha256, username, username_len))
		goto die;
	if (!SHA256_Update(&sha256, password, password_len))
		goto die;
	if (!SHA256_Final(hash, &sha256))
		goto die;
	return;

die:
	die("Failed to compute SHA256 for %s", username);
}
```

Seems fair enough, it'll generate a hash of the `username + password`, then
hash that with the password.

I don't particularly want to implement any of this myself myself, so let's pull
in a couple crates:

- [`sha2`][sha2] - for the SHA-256 algorithm
- [`digest`][digest] - the `digest::Digest` trait comes from the
  [RustCrypto][rust-crypto] project and is used to implement generic
  cryptographic hash functions
- [`hex`][hex] - for converting bytes to their hexadecimal representation and
  back again

And then we can implement `LoginKey::sha256()`.

```rust
// src/keys/login_key.rs

use digest::Digest;
use sha2::Sha256;

impl LoginKey {
    ...

    fn sha256(username: &str, password: &str) -> Self {
        let first_pass = Sha256::new()
            .chain(username)
            .chain(password)
            .result();
        let first_pass_hex = hex::encode(&first_pass);

        let second_pass = Sha256::new()
            .chain(&first_pass_hex)
            .chain(password)
            .result();

        LoginKey::from_bytes(&second_pass)
    }

    fn from_bytes(bytes: &[u8]) -> Self {
        assert_eq!(bytes.len() * 2, LoginKey::LEN);

        let mut key = [0; LoginKey::LEN];
        hex::encode_to_slice(bytes, &mut key)
            .expect("the assert guarantees we've got the right length");

        LoginKey(key)
    }
}
```

To make sure I've implemented this correctly, I gave the `lpass` program a dummy
set of credentials and using the debugger was able to see what they should hash
to.

This lets me write a simple sanity test.

```rust
// src/keys/login_key.rs

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn login_key_with_sha256() {
        let username = "my-test-account@example.com";
        let password = "My Super Secret Password!";
        let should_be = LoginKey(*b"b8a31d9784fa9a263d0e7a0d866b70612687f7067733126d74ccde02d3bab494");

        let got = LoginKey::sha256(username, password);

        assert_eq!(got, should_be);
    }
}
```

I can implement the `LoginKey::pbkdf2()` constructor in much the same way,
again letting the proper crate (in this case, [`pbkdf2`][pbkdf2]) do the heavy
lifting.

```rust
// src/keys/login_key.rs

use sha2::Sha256;
use hmac::Hmac;

impl LoginKey {
    ...

    fn pbkdf2(username: &str, password: &str, iterations: usize) -> Self {
        // the first rearranges the password (maintaining length), salting it
        // with the username
        let mut first_pass = [0; KDF_HASH_LEN];
        pbkdf2::pbkdf2::<Hmac<Sha256>>(
            password.as_bytes(),
            username.as_bytes(),
            iterations,
            &mut first_pass,
        );

        // we then hash the previous key, salting with the password
        // previous key
        let mut key = [0; KDF_HASH_LEN];
        pbkdf2::pbkdf2::<Hmac<Sha256>>(
            &first_pass,
            password.as_bytes(),
            1,
            &mut key,
        );

        LoginKey::from_bytes(&key)
    }
}
```

In much the same way, we can use the debugger to find a set of inputs and
outputs to test that our `LoginKey::pbkdf2()` function was implemented
correctly.

```rust
// src/keys/login_key.rs

#[cfg(test)]
mod tests {
    use super::*;

    ...

    #[test]
    fn login_key_with_pbkdf2() {
        let username = "michaelfbryan@gmail.com";
        let password = "My Super Secret Password!";
        let iterations = 100;
        let should_be =
            LoginKey(*b"f93111b2fb6699de187ef8307aa84b1e9fdabf4a46cb821e83e507a95c3f7c97");

        let got = LoginKey::pbkdf2(username, password, iterations);

        assert_eq!(got, should_be);
    }
}
```

Now we can construct a `LoginKey`, we can [update the test executable][main-rs-2]
to accept credentials instead of a hard-coded login key.

```rust
// src/bin/main.rs

use anyhow::Error;
use lastpass::{endpoints, keys::LoginKey};
use reqwest::Client;
use structopt::StructOpt;

#[tokio::main]
async fn main() -> Result<(), Error> {
    env_logger::init();
    let args = Args::from_args();
    log::debug!("Starting application with {:#?}", args);

    let client = Client::builder()
        .user_agent(lastpass::DEFAULT_USER_AGENT)
        .cookie_store(true)
        .build()?;

    let iterations = endpoints::iterations(&client, &args.host, &args.username).await?;

    let login_key = LoginKey::calculate(&args.username, &args.password, iterations);

    endpoints::login(
        &client,
        &args.host,
        &args.username,
        &login_key,
        iterations,
    )
    .await?;

    log::info!("Logged in as {}", args.username);

    Ok(())
}

#[derive(Debug, StructOpt)]
struct Args {
    #[structopt(
        long = "host",
        default_value = "lastpass.com",
        help = "The LastPass server's hostname"
    )]
    host: String,
    #[structopt(short = "u", long = "username", help = "Your username")]
    username: String,
    #[structopt(short = "p", long = "password", help = "Your master password")]
    password: String,
}
```

While you reading through the earlier section, I took the liberty of creating
a function that asks LastPass how many iterations to use when generating a
login key. The `iterations.php` endpoint replies with a single integer, so
it's dead simple.

```rust
// src/endpoints/iterations.rs

pub async fn iterations(
    client: &Client,
    hostname: &str,
    username: &str,
) -> Result<usize, EndpointError> {
    let url = format!("https://{}/iterations.php", hostname);
    let data = IterationsData { email: username };

    let response = client
        .post(&url)
        .form(&data)
        .send()
        .await?
        .error_for_status()?;
    let body = response.text().await?;

    body.trim().parse().map_err(EndpointError::from)
}

#[derive(Debug, Serialize)]
struct IterationsData<'a> {
    email: &'a str,
}
```

### Decryption Keys

To accompany the `LoginKey`, which has been shared with the LastPass servers
to prove who you are, there is also a `DecryptionKey` for decrypting your
actual LastPass vault.

This second key is derived from your master password and never leaves your
computer, hence the claim that LastPass themselves can't read your personal
data.

The `DecryptionKey` is constructed in a similar (but not identical) way to
the `LoginKey`, so I won't go into detail on that. Instead, I'd like to add a
method for decrypting ciphertext using a `DecryptionKey`.

I guess the best place to start is by looking at how the `lastpass-cli` project
decrypts things using the `DecryptionKey`.

```c
// vendor/lastpass-cli/cipher.c

char *cipher_aes_decrypt(const unsigned char *ciphertext, size_t len, const unsigned char key[KDF_HASH_LEN])
{
	EVP_CIPHER_CTX *ctx;
	char *plaintext;
	int out_len;

	if (!len)
		return NULL;

	ctx = EVP_CIPHER_CTX_new();
	if (!ctx)
		return NULL;

	plaintext = xcalloc(len + AES_BLOCK_SIZE + 1, 1);
	if (len >= 33 && len % 16 == 1 && ciphertext[0] == '!') {
		if (!EVP_DecryptInit_ex(ctx, EVP_aes_256_cbc(), NULL, key, (unsigned char *)(ciphertext + 1)))
			goto error;
		ciphertext += 17;
		len -= 17;
	} else {
		if (!EVP_DecryptInit_ex(ctx, EVP_aes_256_ecb(), NULL, key, NULL))
			goto error;
	}
	if (!EVP_DecryptUpdate(ctx, (unsigned char *)plaintext, &out_len, (unsigned char *)ciphertext, len))
		goto error;
	len = out_len;
	if (!EVP_DecryptFinal_ex(ctx, (unsigned char *)(plaintext + out_len), &out_len))
		goto error;
	len += out_len;
	plaintext[len] = '\0';
	EVP_CIPHER_CTX_free(ctx);
	return plaintext;

error:
	EVP_CIPHER_CTX_free(ctx);
	secure_clear(plaintext, len + AES_BLOCK_SIZE + 1);
	free(plaintext);
	return NULL;
}
```

Although the code is a bit convoluted due to way error handling and argument
validation are done, it looks like we switch between two input algorithms at
the start based, then pass the ciphertext through the decryption function.

Similar to the `LoginKey::calculate()` function I'm guessing this is because
the encryption algorithm has changed over time. So it was initially just
using AES-256 with the ECB [block cipher mode][cipher-mode], then later they
transitioned to CBC with a 16-byte [initialization vector][iv] (that's why
there's the `ciphertext[0] == '!'` and all that pointer arithmetic).

The [`aes`][aes] and [`block-modes`][block-modes] crates made this a lot easier
than I was expecting.

```rust
// src/keys/decryption_key.rs

use aes::Aes256;
use block_modes::{block_padding::Pkcs7, BlockMode, Cbc, Ecb};

impl DecryptionKey {
    pub fn decrypt(
        &self,
        ciphertext: &[u8],
    ) -> Result<Vec<u8>, DecryptionError> {
        if ciphertext.is_empty() {
            // If there's no input, there's nothing to decrypt
            return Ok(Vec::new());
        }

        let decrypted = if uses_cbc(ciphertext) {
            let iv = &ciphertext[1..17];
            let ciphertext = &ciphertext[17..];

            Cbc::<Aes256, Pkcs7>::new_var(&self.0, &iv)?
                .decrypt_vec(ciphertext)?
        } else {
            Ecb::<Aes256, Pkcs7>::new_var(&self.0, &[])?
                .decrypt_vec(ciphertext)?
        };

        Ok(decrypted)
    }
}

fn uses_cbc(ciphertext: &[u8]) -> bool {
    ciphertext.len() >= 33
        && ciphertext.len() % 16 == 1
        && ciphertext.starts_with(b"!")
}
```

The `lastpass-cli` project doesn't have any tests with examples of decrypted
data (or any tests at all for that matter), so I'll need to resort to using
debugger on `lpass` and seeing how real data is decrypted if I want to make
sure my code works.

```rust
// src/keys/decryption_key.rs

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn decrypt_some_text() {
        let key = DecryptionKey::from_raw(b"...");
        let ciphertext = [
            33, 11, 151, 186, 165, 216, 165, 58, 154, 207, 238, 219, 138, 19,
            26, 178, 141, 91, 241, 31, 28, 69, 189, 39, 5, 10, 161, 76, 57, 10,
            240, 137, 11, 124, 42, 129, 213, 123, 192, 182, 178, 194, 84, 175,
            73, 19, 104, 137, 123,
        ];

        let got = key.decrypt(&ciphertext).unwrap();

        assert_eq!(
            String::from_utf8(got).unwrap(),
            "Example password without folder"
        );
    }
}
```

Well the test passes, so if everything goes to plan we should have everything
we need to decode the vault.

## Reading the Vault

Now we've implemented the fundamental things like crypto and calling a couple
API endpoints, we're getting into the more juicy stuff. The next step is to
download a copy of the password vault and read it into memory.

### Retrieving the Vault

Once you've logged in, retrieving a copy of the password vault from LastPass is
really easy. We don't need to supply any authentication information because
LastPass already gave us a PHP session cookie and I'll be reusing the same
`reqwest::Client` for both calls.

Just like `login.php` and `iterations.php`, we need to send a POST request
to the `getaccts.php` endpoint and read the response body.

```rust
// src/endpoints/vault.rs

use crate::{ Vault, VaultParseError };
use reqwest::{Client, Error as ReqwestError};
use serde_derive::Serialize;

const LASTPASS_CLI_VERSION: &str = "1.3.3.15.g8767b5e";

/// Fetch the latest vault snapshot from LastPass.
pub async fn get_vault(
    client: &Client,
    hostname: &str,
) -> Result<Vault, VaultError> {
    let data = Data {
        mobile: 1,
        request_src: "cli",
        // I'm not sure why lastpass-cli used its version number instead of a
        // bool here, but \_(ツ)_/¯
        has_plugin: LASTPASS_CLI_VERSION,
    };
    let url = format!("https://{}/getaccts.php", hostname);

    let body = client
        .post(&url)
        .form(&data)
        .send()
        .await?
        .error_for_status()?
        .bytes()
        .await?;

    Vault::parse(&body).map_err(VaultError::Parse)
}

#[derive(Debug, Serialize)]
struct Data<'a> {
    mobile: usize,
    #[serde(rename = "requestsrc")]
    request_src: &'a str,
    #[serde(rename = "hasplugin")]
    has_plugin: &'a str,
}

#[derive(Debug, thiserror::Error)]
pub enum VaultError {
    /// The HTTP client encountered an error.
    #[error("Unable to send the request")]
    HttpClient(#[from] ReqwestError),
    #[error("Unable to parse the vault")]
    Parse(#[from] VaultParseError),
}
```

For now I've also stubbed out a `Vault` type and given it a `Vault::parse()`
method that accepts a `&[u8]` and will return either a `Vault` or a
`VaultParseError`.

### Decoding the Vault

Running our test program again and inserting a line which will write the
response `body` to disk shows a big hunk of binary.

Let's print this data out as hex and see if we can spot any patterns...

```
# xxd src/vault_from_dummy_account.bin | head -n 30

00000000: 4c50 4156 0000 0002 3132 4154 5652 0000  LPAV....12ATVR..
00000010: 0001 3145 4e43 5500 0000 2c35 4e5a 5969  ..1ENCU...,5NZYi
00000020: 7967 7236 6659 514d 3950 424f 3765 5243  ygr6fYQM9PBO7eRC
00000030: 6357 6f71 4336 454d 7a6c 3159 594b 705a  cWoqC6EMzl1YYKpZ
00000040: 7357 7272 446b 3d43 4243 5500 0000 0131  sWrrDk=CBCU....1
00000050: 4242 5445 0000 000a 3135 3839 3236 3534  BBTE....15892654
00000060: 3836 4950 5445 0000 000a 3135 3839 3236  86IPTE....158926
00000070: 3534 3836 574d 5445 0000 000a 3135 3839  5486WMTE....1589
00000080: 3236 3534 3836 414e 5445 0000 000a 3135  265486ANTE....15
00000090: 3839 3236 3534 3836 444f 5445 0000 000a  89265486DOTE....
000000a0: 3135 3839 3236 3534 3836 4645 5445 0000  1589265486FETE..
000000b0: 000a 3135 3839 3236 3534 3836 4655 5445  ..1589265486FUTE
000000c0: 0000 000a 3135 3839 3236 3534 3836 5359  ....1589265486SY
000000d0: 5445 0000 000a 3135 3839 3236 3534 3836  TE....1589265486
000000e0: 574f 5445 0000 000a 3135 3839 3236 3534  WOTE....15892654
000000f0: 3836 5441 5445 0000 000a 3135 3839 3236  86TATE....158926
00000100: 3534 3836 5750 5445 0000 000a 3135 3839  5486WPTE....1589
00000110: 3236 3534 3836 5350 4d54 0000 0037 0000  265486SPMT...7..
00000120: 0001 3000 0000 0130 0000 0001 3000 0000  ..0....0....0...
00000130: 0130 0000 0001 3000 0000 0131 0000 0001  .0....0....1....
00000140: 3100 0000 0130 0000 0001 3000 0000 0130  1....0....0....0
00000150: 0000 0001 304e 4d41 4300 0000 0136 4143  ....0NMAC....6AC
00000160: 4354 0000 01c4 0000 0013 3534 3936 3233  CT........549623
00000170: 3039 3734 3133 3031 3830 3637 3300 0000  0974130180673...
00000180: 3121 0b97 baa5 d8a5 3a9a cfee db8a 131a  1!......:.......
00000190: b28d 5bf1 1f1c 45bd 2705 0aa1 4c39 0af0  ..[...E.'...L9..
000001a0: 890b 7c2a 81d5 7bc0 b6b2 c254 af49 1368  ..|*..{....T.I.h
000001b0: 897b 0000 0031 215d ae99 4843 6321 5162  .{...1!]..HCc!Qb
000001c0: 80f5 6587 f669 4628 588e 8ba5 51b5 e6a3  ..e..iF(X...Q...
000001d0: 83ed ba28 65e4 786d 2b2a 7ef8 c7d2 ccf9  ...(e.xm+*~.....
```

{{% notice note %}}
I set up a dummy LastPass account just for this analysis, so I'm not overly
concerned about publishing it on the internet.

Besides, all the "interesting" bits are encrypted and you don't have access
to the master password so the most anyone can see is a couple unencrypted
timestamps.
{{% /notice %}}

After staring at the wall of hex for a couple seconds I noticed an interesting
pattern. This blob contains a repeating pattern...

- a 4-byte ASCII mnemonic
- a 4-byte big-endian integer, `n`
- `n` bytes worth of data, sometimes cleartext (e.g. base64-encoded text or a
  long number that looks like a unix timestamp) and other times it'll look like
  garbage (encrypted data)

Now we have a rough idea of how a vault is structured, let's dive into some
source code and see how it's turned into something more usable.

Internally, it looks like LastPass refer to this thing as a `blob`, and there
happens to be `blob_parse()` function in `blob.h`. Let's start there.

```c
// vendor/lastpass-cli/blob.c

struct blob *blob_parse(const unsigned char *blob, size_t len, const unsigned char key[KDF_HASH_LEN], const struct private_key *private_key)
{
    ...

	while (read_chunk(&blob_pos, &chunk)) {
		if (!strcmp(chunk.name, "LPAV")) {
			versionstr = xstrndup((char *) chunk.data, chunk.len);
			parsed->version = strtoull(versionstr, NULL, 10);
		} else if (!strcmp(chunk.name, "ACCT")) {
			account = account_parse(&chunk, last_share ? last_share->key : key);
			if (!account)
				goto error;

            ...
		} else if (!strcmp(chunk.name, "ACFL") || !strcmp(chunk.name, "ACOF")) {
            ...
		} else if (!strcmp(chunk.name, "LOCL")) {
			parsed->local_version = true;
		} else if (!strcmp(chunk.name, "SHAR")) {
            ...
		} else if (!strcmp(chunk.name, "AACT")) {
            ...
		} else if (!strcmp(chunk.name, "AACF")) {
            ...
		} else if (!strcmp(chunk.name, "ATTA")) {
            ...
	}

	if (!versionstr)
		goto error;
	return parsed;

error:
	blob_free(parsed);
	return NULL;
}
```

This seems simple enough. Those patterns we saw earlier are called `chunk`s, and
parsing a `blob` is just a case of reading each `chunk` in the `blob`,
invoking different routines depending on the mnemonic.

Let's have a look at how each chunk is parsed.

```c
// vendor/lastpass-cli/blob.h

struct chunk {
	char name[4 + 1];
	const unsigned char *data;
	size_t len;
};


// vendor/lastpass-cli/blob.c

static bool read_chunk(struct blob_pos *blob, struct chunk *chunk)
{
	if (blob->len < 4)
		return false;
	chunk->name[0] = blob->data[0];
	chunk->name[1] = blob->data[1];
	chunk->name[2] = blob->data[2];
	chunk->name[3] = blob->data[3];
	chunk->name[4] = '\0';
	blob->len -= 4;
	blob->data += 4;

	if (blob->len < sizeof(uint32_t))
		return false;
	chunk->len = be32toh(*((uint32_t *)blob->data));
	blob->len -= sizeof(uint32_t);
	blob->data += sizeof(uint32_t);

	if (chunk->len > blob->len)
		return false;
	chunk->data = blob->data;
	blob->data += chunk->len;
	blob->len -= chunk->len;

	return true;
}
```

This can be converted fairly mechanically into Rust.

The only difference is that instead of mutating the slice every time we read
some data off the front, I'll return a new slice. This means when the caller
removes some data from a buffer they'll be able to *shadow* the old variable,
making sure it's not possible to accidentally confuse what has been already
parsed and what hasn't. I've found this pattern works quite well when parsing.

```rust
// src/parser.rs

use byteorder::{BigEndian, ByteOrder};

struct Chunk<'a> {
    name: &'a [u8],
    data: &'a [u8],
}

impl<'a> Chunk<'a> {
    fn parse(buffer: &'a [u8]) -> Option<(Chunk<'a>, &'a [u8])> {
        if buffer.len() < 4 { return None; }

        let (name, buffer) = buffer.split_at(4);

        if buffer.len() < std::mem::size_of::<u32>() { return None; }

        let (num_bytes, buffer) = buffer.split_at(std::mem::size_of::<u32>());
        let num_bytes: usize = BigEndian::read_u32(num_bytes).try_into().unwrap();

        if num_bytes > buffer.len() { return None; }

        let (data, rest) = buffer.split_at(num_bytes);
        let chunk = Chunk { name, data };

        Some((chunk, rest))
    }
}
```

Now we can read a `Chunk` from the front of a byte buffer, we can start working
on the `Parser`. Instead of leaving all the state and code inline like they did
in `blob_parse()`, I've decided to pull intermediate values into their own
`Parser` struct and give each chunk type its own `handle_XXX()` method. That
just helps to keep functions at a manageable size and improve readability.

```rust
// src/parser.rs

use crate::{Account, Share, App, DecryptionKey, VaultParseError};

#[derive(Debug, Default)]
struct Parser {
    vault_version: Option<u64>,
    accounts: Vec<Account>,
    shares: Vec<Share>,
    app: Option<App>,
    local: bool,
}

impl Parser {
    fn new() -> Self { Parser::default() }

    fn parse(
        &mut self,
        mut buffer: &[u8],
        decryption_key: &DecryptionKey,
    ) -> Result<(), VaultParseError> {
        while let Some((chunk, rest)) = Chunk::parse(buffer) {
            buffer = rest;
            self.handle_chunk(chunk, decryption_key)?;
        }

        Ok(())
    }
}
```

You can see the `Parser::parse()` method just reads chunks and passes them to
the `Parser::handle_chunk()` method. Likewise, `Parser::handle_chunk()` just
does a `match` on the `chunk`'s name and passes the chunk body to the
appropriate method.

```rust
// src/parser.rs

impl Parser {
    ...

    fn handle_chunk(
        &mut self,
        chunk: Chunk<'_>,
        decryption_key: &DecryptionKey,
    ) -> Result<(), VaultParseError> {
        match chunk.name {
            b"LPAV" => { self.vault_version = chunk.data_as_str()?.parse().ok(); },
            b"ACCT" => self.handle_account(chunk.data, decryption_key)?,
            b"ATTA" => self.handle_attachment(chunk.data)?,
            b"LOCL" => self.local = true,
            b"SHAR" => self.handle_share(chunk.data)?,
            b"AACT" => self.handle_app(chunk.data, decryption_key)?,
            _ => {},
        }

        Ok(())
    }

    fn handle_account(&mut self, buffer: &[u8], decryption_key: &DecryptionKey) -> Result<(), VaultParseError> {
        self.accounts.push(parse_account(buffer, decryption_key)?);
        Ok(())
    }

    fn handle_attachment(&mut self, buffer: &[u8]) -> Result<(), VaultParseError> {
        let attachment = parse_attachment(buffer)?;

        match self.accounts.iter_mut().find(|account| account.id == attachment.parent)
        {
            Some(parent) => { parent.attachments.push(attachment); },
            None => return Err(VaultParseError::AttachmentWithoutAccount {
                attachment_id: attachment.id,
                account_id: attachment.parent,
            }),
        }

        Ok(())
    }

    fn handle_share(&mut self, buffer: &[u8]) -> Result<(), VaultParseError> {
        self.shares.push(parse_share(buffer)?);
        Ok(())
    }

    fn handle_app(&mut self, buffer: &[u8], decryption_key: &DecryptionKey) -> Result<(), VaultParseError> {
        self.app = Some(parse_app(buffer, decryption_key)?);

        Ok(())
    }
}
```

Let's have a think about what we'll need to write the `parse_account()`
function.

In LastPass parlance, an `Account` is the fundamental unit in the vault.
These are used to represent things like account credentials (e.g. username
and password), it lets you attach a URL so you can quickly jump to the
website, you can have notes (a free-form string), attached files, and much
more.

As I've coded it, an `Account` looks something like this:

```rust
// src/account.rs

use crate::{Attachment, DecryptionError, DecryptionKey, Id};
use url::Url;

/// A single entry, typically a password or address.
pub struct Account {
    pub id: Id,
    /// The account's name.
    pub name: String,
    /// Which group the account is in (think of it like a directory).
    pub group: String,
    /// The URL associated with this account.
    pub url: Url,
    /// Any notes that may be attached.
    pub note: String,
    pub note_type: String,
    /// Did the user mark this [`Account`] as a favourite?
    pub favourite: bool,
    /// The associated username.
    pub username: String,
    /// The associated password.
    pub password: String,
    /// Should we prompt for the master password before showing details to the
    /// user?
    pub password_protected: bool,
    /// An encrypted copy of the key used to decode this [`Account`]'s
    /// attachments.
    pub encrypted_attachment_key: String,
    /// Does this account have any [`Attachment`]s?
    pub attachment_present: bool,
    pub last_touch: String,
    pub last_modified: String,
    /// Files which may be attached to this [`Account`].
    pub attachments: Vec<Attachment>,
}


// src/attachment.rs

/// Metadata about an attached file.
pub struct Attachment {
    pub id: Id,
    /// The ID of the parent [`Account`].
    pub parent: Id,
    /// The file's mimetype.
    pub mime_type: String,
    /// An opaque string which is used by the backend to find the correct
    /// version of an attached file.
    pub storage_key: String,
    /// The size of the attachment, in bytes.
    pub size: u64,
    /// The attachment's filename, encrypted using the account's
    /// `attachment_key`.
    pub encrypted_filename: String,
}
```

Like a lot of core business objects tend to do, you can see the `Account` has
grown a large number of fields over the years.

To help handle the monotony of parsing dozens of fields, `lastpass-cli` has
introduced a couple helper macros and functions.

```c
// vendor/lastpass-cli/blob.c

static bool read_item(struct chunk *chunk, struct item *item) { ... }

static char *read_hex_string(struct chunk *chunk) { ... }

static char *read_plain_string(struct chunk *chunk) { ... }

static char *read_crypt_string(struct chunk *chunk,
                               const unsigned char key[KDF_HASH_LEN],
                               char **stored_base64) { ... }

static int read_boolean(struct chunk *chunk) { ... }

#define entry_plain_at(base, var) do { \
	char *__entry_val__ = read_plain_string(chunk); \
	if (!__entry_val__) \
		goto error; \
	base->var = __entry_val__; \
	} while (0)
#define entry_plain(var) entry_plain_at(parsed, var)
#define entry_hex_at(base, var) do { \
	char *__entry_val__ = read_hex_string(chunk); \
	if (!__entry_val__) \
		goto error; \
	base->var = __entry_val__; \
	} while (0)
#define entry_hex(var) entry_hex_at(parsed, var)
#define entry_boolean(var) do { \
	int __entry_val__ = read_boolean(chunk); \
	if (__entry_val__ < 0) \
		goto error; \
	parsed->var = __entry_val__; \
	} while (0)
#define entry_crypt_at(base, var) do { \
	char *__entry_val__ = read_crypt_string(chunk, key, &base->var##_encrypted); \
	if (!__entry_val__) \
		goto error; \
	base->var = __entry_val__; \
	} while (0)
#define entry_crypt(var) entry_crypt_at(parsed, var)
#define skip(placeholder) do { \
	struct item skip_item; \
	if (!read_item(chunk, &skip_item)) \
		goto error; \
	} while (0)
```

The only non-trivial helper is `read_crypt_string()`, the equivalent of our
`DecodeKey::decode()`. The rest just pop the next item from a `Chunk` and
parse it into the desired format.

From here, we can see how the `account_parse()` function is implemented. It's
not complicated per-se, just long.

```c
// vendor/lastpass-cli/blob.c

static struct account *account_parse(struct chunk *chunk, const unsigned char key[KDF_HASH_LEN])
{
	struct account *parsed = new_account();

	entry_plain(id);
	entry_crypt(name);
	entry_crypt(group);
	entry_hex(url);
	entry_crypt(note);
	entry_boolean(fav);
	skip(sharedfromaid);
	entry_crypt(username);
	entry_crypt(password);
	entry_boolean(pwprotect);
	skip(genpw);
	skip(sn);
	entry_plain(last_touch);
	skip(autologin);
	skip(never_autofill);
	skip(realm_data);
	skip(fiid);
	skip(custom_js);
	skip(submit_id);
	skip(captcha_id);
	skip(urid);
	skip(basic_auth);
	skip(method);
	skip(action);
	skip(groupid);
	skip(deleted);
	entry_plain(attachkey_encrypted);
	entry_boolean(attachpresent);
	skip(individualshare);
	skip(notetype);
	skip(noalert);
	entry_plain(last_modified_gmt);
	skip(hasbeenshared);
	skip(last_pwchange_gmt);
	skip(created_gmt);
	skip(vulnerable);

	if (parsed->name[0] == 16)
		parsed->name[0] = '\0';
	if (parsed->group[0] == 16)
		parsed->group[0] = '\0';

	if (strlen(parsed->attachkey_encrypted)) {
		parsed->attachkey = cipher_aes_decrypt_base64(
			parsed->attachkey_encrypted, key);
	}
	if (!parsed->attachkey)
		parsed->attachkey = xstrdup("");

	/* use name as 'fullname' only if there's no assigned group */
	if (strlen(parsed->group) &&
	    (strlen(parsed->name) || account_is_group(parsed)))
		xasprintf(&parsed->fullname, "%s/%s", parsed->group, parsed->name);
	else
		parsed->fullname = xstrdup(parsed->name);

	return parsed;

error:
	account_free(parsed);
	return NULL;
}
```

Our `parse_account()` function looks quite similar, although deciding to just
use helper functions and not macros means it's more visually cluttered.

```rust

pub(crate) fn parse_account(
    buffer: &[u8],
    decryption_key: &DecryptionKey,
) -> Result<Account, VaultParseError> {
    let (id, buffer) = read_parsed(buffer, "account.id")?;
    let (name, buffer) = read_encrypted(buffer, "account.name", decryption_key)?;
    let (group, buffer) = read_encrypted(buffer, "account.group", decryption_key)?;
    let (url, buffer) = read_hex_string(buffer, "account.url")?;
    let (note, buffer) = read_encrypted(buffer, "account.note", &decryption_key)?;
    let (fav, buffer) = read_bool(buffer, "account.fav")?;
    let buffer = skip(buffer, "account.sharedfromaid")?;
    let (username, buffer) = read_encrypted(buffer, "account.username", decryption_key)?;
    let (password, buffer) = read_encrypted(buffer, "account.password", decryption_key)?;
    let (password_protected, buffer) = read_bool(buffer, "account.pwprotect")?;
    let buffer = skip(buffer, "account.genpw")?;
    let buffer = skip(buffer, "account.sn")?;
    let (last_touch, buffer) = read_str_item(buffer, "account.last_touch")?;
    let buffer = skip(buffer, "account.autologin")?;
    let buffer = skip(buffer, "account.never_autofill")?;
    let buffer = skip(buffer, "account.realm_data")?;
    let buffer = skip(buffer, "account.fiid")?;
    let buffer = skip(buffer, "account.custom_js")?;
    let buffer = skip(buffer, "account.submit_id")?;
    let buffer = skip(buffer, "account.captcha_id")?;
    let buffer = skip(buffer, "account.urid")?;
    let buffer = skip(buffer, "account.basic_auth")?;
    let buffer = skip(buffer, "account.method")?;
    let buffer = skip(buffer, "account.action")?;
    let buffer = skip(buffer, "account.groupid")?;
    let buffer = skip(buffer, "account.deleted")?;
    let (attachkey_encrypted, buffer) = read_str_item(buffer, "account.attachkey_encrypted")?;
    let (attachment_present, buffer) = read_bool(buffer, "account.attachpresent")?;
    let buffer = skip(buffer, "account.individualshare")?;
    let (note_type, buffer) = read_str_item(buffer, "account.notetype")?;
    let buffer = skip(buffer, "account.noalert")?;
    let (last_modified_gmt, buffer) = read_str_item(buffer, "account.last_modified_gmt")?;
    let buffer = skip(buffer, "account.hasbeenshared")?;
    let buffer = skip(buffer, "account.last_pwchange_gmt")?;
    let buffer = skip(buffer, "account.created_gmt")?;
    let buffer = skip(buffer, "account.vulnerable")?;

    let _ = buffer;

    Ok(Account {
        id,
        name,
        username,
        password,
        password_protected,
        note: note.to_string(),
        note_type: note_type.to_string(),
        last_touch: last_touch.to_string(),
        encrypted_attachment_key: attachkey_encrypted.to_string(),
        attachment_present,
        favourite: fav,
        group,
        last_modified: last_modified_gmt.to_string(),
        url: Url::parse(&url).map_err(|e| VaultParseError::BadParse {
            field: "account.url",
            inner: Box::new(e),
        })?,
        attachments: Vec::new(),
    })
}
```

{{% notice note %}}
You may have noticed that each helper function is passed a string with the
field name. That comes about because I'm trying to give really clear error
messages when things go wrong (that way they're easier to debug), so instead of
saying *"unable to parse the vault"*, we'll be able to say something more useful
like *"Unable to decrypt account.password"*).

This is the full declaration for `VaultParseError`. You'll notice we're using
[`thiserror`][thiserror] to automatically derive `std::fmt::Display` and make
sure things like `Error::source()` will return the underlying issue if one is
present.

```rust
// src/parser.rs

/// Errors that can happen when parsing a [`Vault`] from raw bytes.
#[derive(Debug, thiserror::Error)]
pub enum VaultParseError {
    #[error("The \"{}\" chunk should contain a UTF-8 string", name)]
    ChunkShouldBeString {
        name: String,
        #[source]
        inner: Utf8Error,
    },
    #[error("Parsing didn't find, {}", name)]
    MissingField { name: &'static str },
    #[error("Reached the end of input while looking for {}", expected_field)]
    UnexpectedEOF { expected_field: &'static str },
    #[error("Unable to decrypt {}", field)]
    UnableToDecrypt {
        field: &'static str,
        #[source]
        inner: DecryptionError,
    },
    #[error("Parsing the {} field failed", field)]
    BadParse {
        field: &'static str,
        #[source]
        inner: Box<dyn Error + Send + Sync + 'static>,
    },
}
```

[thiserror]: https://crates.io/crates/thiserror
{{% /notice %}}

I'm not going to go show too much more parsing code (because it's all kinda the
same and you can [read it on github][parser-rs]), but I'd like to show how
simple it is to read an encrypted field is. Most of the code is actually
dedicated to providing detailed parse errors to the caller.

```rust
// src/parser.rs

fn read_encrypted<'a>(
    buffer: &'a [u8],
    field: &'static str,
    decryption_key: &DecryptionKey,
) -> Result<(String, &'a [u8]), VaultParseError> {
    // read the next "item" (&[u8]) from the front of our buffer
    let (ciphertext, buffer) = read_item(buffer, field)?;

    // then decrypt it using our decryption key
    let decrypted = decryption_key
        .decrypt(ciphertext)
        .map_err(|e| VaultParseError::UnableToDecrypt { field, inner: e })?;

    // and interpret the decrypted text as a UTF-8 string
    let decrypted = String::from_utf8(decrypted)
        .map_err(|e| VaultParseError::BadParse { field, inner: Box::new(e) })?;

    Ok((decrypted, buffer))
}
```

We're actually able to read the `Vault` into memory and start looking at its
contents now!

Let's update the example executable so it'll log in and print out the first
`Account` in my test vault.

```console
$ RUST_LOG=info cargo run --username $EMAIL --password=$PASSWORD
Sending a request to https://lastpass.com/getaccts.php
Account {
    id: Id(
        "533903346832032070",
    ),
    name: "Another Password",
    group: "",
    url: "https://google.com/",
    note: "This is a super secure note.",
    note_type: "Generic",
    favourite: false,
    username: "user",
    password: "My Super Secret Password!!1!",
    password_protected: false,
    encrypted_attachment_key: "!MOEcIddt5GaMMH8eoMWyRA==|BWdjMSoIvClMRyWrDdIlz38tZiU3O1nmcbg95PRXCT4zKLTTG4s0OD9v/co2l2PwNaKL4oaVPSIB8oUFhk3kAl77qBbrkAH03lWY/wIModA=",
    attachment_present: true,
    last_touch: "0",
    last_modified: "1586717786",
    attachments: [
        Attachment {
            id: Id(
                "533923346832032065-27281",
            ),
            parent: Id(
                "533923346832032065",
            ),
            mime_type: "other:txt",
            storage_key: "100000020283",
            size: 70,
            encrypted_filename: "!zdLMAcQ2okxs3MFWNjoCaw==|B7NqfcNPX0IbYFXNtykqEw==",
        },
    ],
}
```

## Downloading Attachments

An interesting part about accounts is that each gets an
`encrypted_attachment_key` field. This is a key that is base64-encoded and
encrypted using your master key, and is what you use for all
attachment-related decryption.

Let's give the `Account` a helper method for extracting the account key.

```rust
// src/account.rs

impl Account {
    /// Get the key used to work with this [`Account`]'s attachments.
    pub fn attachment_key(
        &self,
        decryption_key: &DecryptionKey,
    ) -> Result<DecryptionKey, DecryptionError> {
        let hex = decryption_key.decrypt_base64(&self.encrypted_attachment_key)?;
        let key = DecryptionKey::from_hex(&hex)?;

        Ok(key)
    }
}
```

Now we've got the attachment key, we can decrypt an `Attachment`'s filename from
the metadata stored in the vault.

```rust
// src/attachment.rs

use crate::{DecryptionError, DecryptionKey, Id};

/// Metadata about an attached file.
#[derive(Debug, Clone, PartialEq)]
#[non_exhaustive]
pub struct Attachment {
    pub id: Id,
    /// The ID of the parent [`crate::Account`].
    pub parent: Id,
    /// The file's mimetype.
    pub mime_type: String,
    /// An opaque string which is used by the backend to find the correct
    /// version of an attached file.
    pub storage_key: String,
    /// The size of the attachment, in bytes.
    pub size: u64,
    /// The attachment's filename, encrypted using the account's `attachment_key`.
    pub encrypted_filename: String,
}

impl Attachment {
    pub fn filename(
        &self,
        attachment_key: &DecryptionKey,
    ) -> Result<String, DecryptionError> {
        attachment_key
            .decrypt_base64(&self.encrypted_filename)
            .map(|filename| String::from_utf8(filename).unwrap())
    }
}
```

So now we're able to read an attachment's filename.

It may not sound like much, but by this point we've actually gone through
three levels of encryption...

1. First we needed a login key to prove who we are
2. Then we needed to use the master decryption key so we can read things like
   an account's name, associated username and password, and extract the
   attachment key
3. Then we used the attachment key to read the attachment's filename

Talk about defence in depth!

### Downloading Attachments

It looks like the `Attachment`'s `storage_key` field doesn't actually have
anything to do with encryption.

Don't just take my word on it though, here's the `Debug` representation of
an `Attachment`

```rust
Attachment {
    id: Id(
        "533903346832032070-27282",
    ),
    parent: Id(
        "533903346832032070",
    ),
    mime_type: "other:txt",
    storage_key: "100000027282",
    size: 70,
    encrypted_filename: "!zdLMAcQ9okxR3MFWNjoCaw==|B7NqfcNPX0IayFXNtxkqEw==",
}
```

The value `100000027282` seems far too regular to be anything related to
crypto, so I'm guessing the use of the word *"key"* is intended as *"unique
identifier"*.

I'm guessing it's an ID that LastPass use to refer to a particular resource
stored on S3 or in a database somewhere. I doubt only 27282 attachments have
been uploaded to LastPass, so that means they're probably randomising storage
keys instead of using an auto-incrementing number.

To figure out how attachments are downloaded, let's have another look at the
`lastpass-cli` source code.

At the very bottom of `endpoints.h` there's a declaration for the
`lastpass_load_attachment()` function... That seems promising.

```c
// vendor/lastpass-cli/endpoints.c

/*
 * Get the attachment for a given attachment id.  The crypttext is returned
 * and should be decrypted with account->attachkey.  The pointer returned
 * in *result should be freed by the caller.
 */
int lastpass_load_attachment(const struct session *session,
			     const char *shareid,
			     struct attach *attach,
			     char **result)
{
	char *reply = NULL;
	char *p;

	*result = NULL;

	struct http_param_set params = {
		.argv = NULL,
		.n_alloced = 0
	};

	http_post_add_params(&params,
			     "token", session->token,
			     "getattach", attach->storagekey,
			     NULL);

	if (shareid) {
		http_post_add_params(&params,
				     "sharedfolderid", shareid,
				     NULL);
	}

	reply = http_post_lastpass_param_set("getattach.php",
					     session, NULL,
					     &params);

	free(params.argv);
	if (!reply)
		return -ENOENT;

	/* returned string is json-encoded base64 string; unescape it */
	if (reply[0] == '"')
		memmove(reply, reply+1, strlen(reply));
	if (reply[strlen(reply)-1] == '"')
		reply[strlen(reply)-1] = 0;

	p = reply;
	while (*p) {
		if (*p == '\\') {
			memmove(p, p + 1, strlen(p));
		} else {
			p++;
		}
	}

	*result = reply;
	return 0;
}
```

{{% notice tip %}}
For reference, the `attach` struct is almost identical to our `Attachment`,
except written in C.

```c
// vendor/lastpass-cli/blob.h

struct attach {
	char *id;
	char *parent;
	char *mimetype;
	char *storagekey;
	char *size;
	char *filename;

	struct list_head list;
};
```
{{% /notice %}}

This `lastpass_load_attachment()` function seems fairly straightforward.

1. Send a request to `getattach.php` with a `token` and `getattach`, our
   `storage_key` (I don't care about shared folders for now, so we can ignore
   the `sharedfolderid` parameter)
2. Parse the string that's returned as a JSON string (i.e. wrapped in quotes and
   with escape characters)
3. Base64-decode it to get the blob of bytes that makes up the encrypted
   attachment
4. Decrypt the attachment using the attachment key. This isn't strictly part of
   `lastpass_load_attachment()`, but I'd prefer to do it all in the same
   function so callers don't need to remember the `Vec<u8>` they've got is
   still encrypted

By now you've already seen me write several endpoint definitions, and we've
used the `DecryptionKey` once or twice, so nothing should be overly new here.

First we define a `Data` type to hold our form data.

```rust
// src/endpoints/load_attachment.rs

use serde_derive::Serialize;

#[derive(Debug, Serialize)]
struct Data<'a> {
    token: &'a str,
    #[serde(rename = "getattach")]
    storage_key: &'a str,
}
```

I'm also creating a dedicated error type, because no other endpoints deal with
*just* base64-decoding and decryption errors.

```rust
// src/endpoints/load_attachment.rs

#[derive(Debug, thiserror::Error)]
pub enum LoadAttachmentError {
    /// The HTTP client encountered an error.
    #[error("Unable to send the request")]
    HttpClient(#[from] reqwest::Error),
    #[error("Unable to decrypt the payload")]
    Decrypt(#[from] crate::DecryptionError),
    #[error("Unable to decode the decrypted attachment")]
    Decode(#[from] base64::DecodeError),
}
```

And finally, the endpoint function itself.

```rust
// src/endpoints/load_attachment.rs

pub async fn load_attachment(
    client: &Client,
    hostname: &str,
    token: &str,
    storage_key: &str,
    decryption_key: &DecryptionKey,
) -> Result<Vec<u8>, LoadAttachmentError> {
    let data = Data { token, storage_key };
    let url = format!("https://{}/getattach.php", hostname);

    let response = client
        .post(&url)
        .form(&data)
        .send()
        .await?
        .error_for_status()?;

    let ciphertext: String = response.text().await?;
    let data = decryption_key.decrypt_base64(&ciphertext)?;

    // not only was the ciphertext in base64, the attachment body was too
    base64::decode(data).map_err(LoadAttachmentError::Decode)
}
```

The thing I really like about this is once you have the underlying
abstractions (key management, an ergonomic HTTP client, async-await, the
`base64` crate, serialization to/from arbitrary formats, etc.) everything
sort of *falls into place*.

I mean loading an attachment only took about 30 lines of easily readable
code, and about half of that is taken up by the definitions for `Data` and
`LoadAttachmentError`.

And look...

```
*** My Secure Note - hello-world.txt (70 bytes) ***
Sending a request to https://lastpass.com/getattach.php
Hello, World
```

It was able to download our `hello-world.txt` attachment! 🎉

## Conclusions

Sorry if it took a while, but we got there in the end. It turns out reading
through the source code for a 15,000-line C program and explaining how my
2,000-line Rust implementation works takes a while...

It was fun to play around with crypto again, even if I barely went further
than passing around keys and calling library functions.

I'm also no professional cartographer, but it seems like the LastPass system
has been pretty well designed. They've deliberately separated the `LoginKey`
from the key you use to decrypt your vault. Plus the defence-in-depth (e.g.
attachment keys) should help protect users from attacking a vault that's been
cached locally.

I'm also pleasantly surprised at how easy this was to implement. Rust has a
really nice ecosystem, and thanks to the work of projects like
[`serde`][serde], [`reqwest`][reqwest], and [RustCrypto][rust-crypto], I have
all the necessary pieces at my fingertips. You'd hardly notice that
async-await is only 4 months old.

The hardest bit was actually deciphering the `blob` parsing code, and that's
because it was written in C and the lack of existing unit tests meant I spent
a fair amount of time running `lpass` under the debugger to see what certain
values are meant to be. It's not a deal breaker, but you'd think a C program
for accessing your passwords and bank account details would have some sort of
unit testing or input fuzzing...

{{% notice note %}}
I'd be keen to hear from you if you are a developer from LastPass! What are
your thoughts on my efforts? Has the analysis been accurate, and can you spot
any bugs or issues?

I feel like having an official library that lets developers work with the
LastPass API can enable a lot of benefits for customers, and I'd like to help
out on that front 😁
{{% /notice %}}

[dotfiles]: https://github.com/Michael-F-Bryan/dotfiles
[lastpass-cli]: https://github.com/lastpass/lastpass-cli
[issue-547]: https://github.com/lastpass/lastpass-cli/issues/547
[cleanup]: https://gcc.gnu.org/onlinedocs/gcc/Common-Variable-Attributes.html#index-cleanup-variable-attribute
[install-py]: https://github.com/Michael-F-Bryan/dotfiles/blob/master/install.py
[reqwest]: https://crates.io/crates/reqwest
[serde]: https://serde.rs/
[aes]: https://crates.io/crates/aes
[block-modes]: https://crates.io/crates/block_modes
[pbkdf2]: https://crates.io/crates/pbkdf2
[rust-crypto]: https://github.com/RustCrypto
[main-rs-1]: https://github.com/Michael-F-Bryan/lastpass/blob/0a5da0262548d475e81138f91a22fa125658ea3e/src/bin/main.rs
[main-rs-2]: https://github.com/Michael-F-Bryan/lastpass/blob/c0b7d260dcdf78cbaae83b15d9059573913f3366/src/bin/main.rs
[serde-xml-rs]: https://crates.io/crates/serde_xml_rs
[primitive-obsession]: https://refactoring.guru/smells/primitive-obsession
[doubly-linked-list]: https://github.com/lastpass/lastpass-cli/blob/8767b5e53192ad4e72d1352db4aa9218e928cbe1/list.h
[pbkdf2]: https://en.wikipedia.org/wiki/PBKDF2
[sha2]: https://crates.io/crates/sha2
[digest]: https://crates.io/crates/digest
[hex]: https://crates.io/crates/hex
[cipher-mode]: https://en.wikipedia.org/wiki/Block_cipher_mode_of_operation
[iv]: https://en.wikipedia.org/wiki/Initialization_vector
[parser-rs]: https://github.com/Michael-F-Bryan/lastpass/blob/60499b7531689c4f3f5dc7180bc705528cd64bf4/src/parser.rs
