---
title: "Self Modifying Tests"
date: "2023-08-20T00:15:39+08:00"
draft: true
---

### 1. Introduction

- **Problem Statement:** Outline the problem of keeping generated Rust code up to date.
- **Solution Overview:** Briefly introduce the technique of using tests to automatically re-generate code.
- **Importance:** Explain why this method is valuable to the Rust community, and perhaps mention its adaptation from Rust Analyzer.

Last year I came across this cool technique for 

Ever found yourself neck-deep in code, orchestrating data generation, and then
realizing that things are drifting out of sync? Trust me, I've been there, and
I'm sure you have too. Staring at an auto-generated GraphQL schema that somehow
got divorced from reality can feel like watching a train derail in slow motion.

But fear not, my fellow Rustaceans and code wranglers! There's a beautiful
solution to this quagmire, lurking in the very place where we seek solace from
our coding mishaps – the world of testing. In fact, we're about to embark on a
coding adventure that will not only align our stars but keep them that way. 🚀

We'll dive headfirst into a technique that leverages the power of tests to
automatically generate data (whether it be code, a GraphQL schema, or that
secret sauce you use in your projects) and keep it all neatly aligned. You might
even say it's like having a personal robot assistant that tirelessly ensures
everything is in its right place. (I, for one, welcome our new robot overlords!)

So grab your favorite beverage, cozy up to your keyboard, and let's get started.
By the end of this post, you'll have the tools to keep your generated data in
perfect harmony. We'll explore real-world scenarios, get our hands dirty with
some code, and maybe even share a laugh or two along the way.

Ready to simplify your life, one test at a time? Let's dive in!

### 2. Background and Context
- **Existing Methods:** Provide a brief overview of the traditional methods of keeping generated Rust code up to date.
- **Inspiration:** Mention the adaptation from Rust Analyzer and matklad's blog post, providing context to your solution.

### 3. The Technique in Detail
- **Code Generation Tests:** Dive into the core part of the technique, explaining how tests can be written to re-generate code.
- **Examples:** Include the code snippets you've provided, explaining each part in detail.
- **Magic Moment:** Explain the 'magic' in `ensure_file_contents`, highlighting its role in the process.

### 4. Application and Use Cases
- **Real-World Examples:** Show how you've applied this technique in generating concrete syntax tree code for parsing.
- **Potential Other Use Cases:** Explore other scenarios where this technique can be beneficial.

### 5. Considerations and Caveats
- **Potential Pitfalls:** Discuss any challenges or things to be aware of when implementing this method.
- **Best Practices:** Provide guidance on how to avoid these pitfalls.

### 6. Conclusion
- **Summary:** Recap the key points of the article.
- **Call to Action:** Encourage readers to try out the technique, and invite them to share their experiences or ask questions.

### Tips for Overcoming Motivation Struggles:
- **Set Small Goals:** Break the article into sections and tackle one at a time.
- **Create a Routine:** Dedicate specific time slots to writing.
- **Seek Feedback:** Share drafts with peers for encouragement and constructive criticism.
