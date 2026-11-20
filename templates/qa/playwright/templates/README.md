# Spec templates

The starting point for a new Playwright QA spec, kept at the current rules in the [harness README](../README.md) (Adding a story). It sits outside `tests/`, so no run picks it up.

| File | What it is |
| --- | --- |
| [story.spec.ts](story.spec.ts) | One spec with each kind of step, on the standard Case object: a query step, a flow on video with its opening card, and a screenshot step as a second user. Copy it to `../tests/<ticket>.spec.ts` and replace every TODO. When a rule in the README changes, change this file in the same commit |
