title: Refactoring My Website in the Age of Vibe Coding
date: 05-16-2026
description: A technical write-up on refactoring my website's gallery, ingestion, color handling, Dropbox sync, and CI workflow with GPT-5.4.
status: published
slug: refactoring-my-website-in-the-age-of-vibe-coding

I recently gave my website a fairly substantial refactor.

All of this was done alongside GPT-5.4.

That was genuinely useful. A lot of the HTML and CSS work would have been much harder without it, simply because that part of the stack is less familiar territory for me. Having a rapid iteration loop for frontend development and layout changes made it much easier to tackle areas of the refactor that would otherwise have involved a lot more trial and error.

At the same time, it was also a good reminder that **LLM-assisted development needs a brake pedal**. Once a feature is implemented, the model is almost always happy to suggest one more abstraction, one more cleanup, one more enhancement, one more *"while we're here"* improvement. That is how a small refactor quietly turns into a much larger and more complicated system than the project ever needed.

That ended up being the main lesson from the whole exercise: with LLMs, it is very easy to keep going just because more is possible. The harder and more important skill is deciding when to stop, recognizing that every extra feature comes with a long-term maintenance cost.

Every now and then, I will also make a point of going through the process of implementing a new idea myself and then let the agent roast me afterwards. The most valuable learning will always come from wrestling with a problem on your own first.

***Vibe, but not too close to the sun.***

## Changelog

- Gallery browsing upgraded with GLightbox and direct template-driven photo rendering.
- Photos no longer modeled as Pelican articles.
- Ingestion rebuilt to generate display/thumbnail WebP derivatives plus JSON metadata.
- Colour profile handling fixed during image conversion.
- Dropbox-to-GitHub publishing automation added.
- CI, tests, packaging, and workflow guards tightened.
