# Writing a QA sub-task's Test Steps

The Test Steps on a QA sub-task are the contract for everything that follows. They say what is tested, as which user, against which acceptance criterion, and with which evidence. The script implements them word for word, so they're written and approved before any script exists.

For who does what at each stage, see [how-test-steps-flow.md](how-test-steps-flow.md).

## The rules

### Test Steps first

Before any script, Claude drafts the QA sub-task's Test Steps from the story's acceptance criteria and the story's own Test Steps:

- Step 1 is the build check.
- The other steps are grouped into flows. Each flow names the persona it runs as, never one tester's user, so any tester can run it, and each step names the criterion it tests and its evidence tag.
- The steps end with a Coverage section.

The Solution Architect approves that text, and the script implements it as written. How a screen behaves (where a button hides, how a list loads) goes into the harness helpers, never into the steps.

### User steps come from the story, not the build

Draft the flows from the story's acceptance criteria and what the client needs to do, before reading the build sub-task. The build sub-task's spec feeds only step 1, the build check.

That split is the point. The build check answers "was it built as specified?", and the flows answer "does it do what the client needs?". If the build drifted from a criterion, a flow written from the story fails. A flow written from the build would have copied the drift in and passed.

### Every criterion is accounted for

The Test Steps end with a **Coverage** section: one bullet per acceptance criterion, by number, each reading as a sentence and saying one of three things:

- the step or flow that proves it
- the other story or ticket that tests it, linked
- why it isn't tested

A criterion missing from Coverage shows at approval, before any script is written.

A role or permission story's QA proves the access exists (build check and queries). What a permission lets a user do on screen is tested in the story that uses it, so a foundation story doesn't wait on later builds.

### Keep steps simple

Avoid complexity without losing coverage:

1. **One step per criterion where possible**, with one expected result, so each step passes or fails against one criterion.
2. **Plain user words in the flows** ("complete the case with no owner"). API names belong in the build check.
3. **The fewest users, records and flows needed.** Add a second user only when the criterion is about a second person: a handoff, access, a supervisor.
4. **The build check carries the bulk:** value lists, which sections show where, field access. Videos show only what has to be done to be proven.
5. **Nothing the story doesn't ask for:** no platform behaviour, admin Setup or another story's work. Those go in Coverage as one sentence, not as steps.

A step that's cut still has its criterion in Coverage, saying where it's proven.

## Evidence tags

Each step or flow carries one evidence tag, chosen when the steps are drafted so the approver sees it with them. The script's scenario list copies the ticket's tags. Nothing sets a tag automatically.

Almost every QA sub-task has a build check of what its build adds or changes, including a flow or validation rule the story touches, even when a video also shows it firing. The build check shows what changed; the other evidence shows it behaves. It isn't a weaker video: it covers every value on every record type, where a video shows one path.

Then, for each criterion, take the first answer that proves it:

| Order | Question | Tag | Example |
| --- | --- | --- | --- |
| 1 | Is it about what exists or what's offered? | [Build check] | Fields, value lists, values per record type, page sections, a flow being active |
| 2 | Can records or access settings answer it, with nothing run as a user? | [Query] | Who's in a queue, a permission set's access, status history rows, record counts |
| 3 | Is it what a user sees at one moment, with no process to follow? | [Screenshot] | A report's totals, a list view |
| 4 | Does the proof depend on actions or a rule firing? | [Video] | A save blocked, a value kept after a record type change, a record created end to end |

Steps run by the same user in the same session share one video, even if one of them alone would only need a screenshot. A step with a video gets no screenshot on top.

### Decided cases

Start your project with these rules, and add a row each time the approver settles an unclear tag, so the rules get more specific over time. Keep the table in your harness README's Adding a story section.

| Case | Rule |
| --- | --- |
| A flow or validation rule the story adds or changes | Build check, plus a video when firing is what the criterion asks |
| A criterion that says a save is blocked | Video, since the attempt is the proof |
| A report run in the same session as a flow | The flow's video covers it, with no screenshot. A report run as a different user gets one screenshot |
| Which page sections show on which record type | Build check, by reading the page's visibility rules. A flow shows the rule working once where the story changes record type |
| What an administrator does in Setup (add, rename or retire a picklist value) | Build check only, showing the build uses the standard configuration an admin edits. Videos are for what end users do; QA doesn't change Setup to show Salesforce's own behaviour |

## Group the steps into flows

A flow is one user's session through several steps end to end, such as signing in, opening a case and closing it. It records one video, `<ticket>-F<n>.webm`, instead of one video per step:

- **Opening card.** Every flow video starts with a card: the ticket and its title, what the video shows, the steps it covers, who it runs as, and the org and round. A reader who opens one video on its own knows what it's about. It says only what this video covers: no count of videos and no pointer to other evidence.
- **A chapter per step.** Each step gets its own card ("Step 3 of 5: ...") and keeps its own result.
- **A failure stops the flow.** The steps after it show as not run until the flow is rerun.
- A step that stands alone (a different user, or one that needs its own records) can be its own test.

Name the flows in the Test Steps too, so the ticket reads as a workflow and the reviewer has fewer videos to watch.

## When a run shows a step is wrong

After approval, the steps change only if a run shows they're wrong: a criterion can't be proven the way it's written, or the story's wording doesn't match what the org can do. Take it back to the approver as a change to what's tested, with the reason and a recommendation. Don't fold it quietly into the final wording.

Once the approver accepts the new text, update the Test Steps on the ticket, update the script to match, and rerun with the attempt reason `steps-changed`. If the script was wrong and the steps were right, the reason is `script-fix` instead.

## Template

Paste this into the QA sub-task's Test Steps field and fill it in. Keep the tags in square brackets so the script can copy them.

```text
1. Build check [Build check]
   Compare the org with the build sub-task's spec (PROJ-20): <what the build adds or changes>.

Flow F1, as <persona, for example Specialist>
2. <What the user does, in plain words>. Expected: <one result>. Criterion 1. [Video]
3. <What the user does>. Expected: <one result>. Criterion 2. [Video]

Flow F2, as <second persona, only if a criterion is about a second person>
4. <What the user does>. Expected: <one result>. Criterion 3. [Screenshot]

5. <What a query shows, with nothing run as a user>. Expected: <one result>. Criterion 4. [Query]

Coverage
- Criterion 1: flow F1, step 2.
- Criterion 2: flow F1, step 3.
- Criterion 3: step 4.
- Criterion 4: step 5.
- Criterion 5: tested in <other story> (PROJ-34).
- Criterion 6: step 1, the build check. <Why no user step is needed.>
```
