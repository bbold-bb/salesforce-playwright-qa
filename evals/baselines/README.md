# Saved baselines

Scores saved with `--save <label>`, named `<date>-<model>-<label>`. Each `.md` is the score table; each `.json` holds every hard-check finding per run.

| Date | Label | What it is |
| --- | --- | --- |
| 2026-11-21 | `first` | The first full offline run: both tiers, 3 runs, with and without the skill, default model, Claude Code 2.1.330. Two case-arms timed out on every run under 4-at-a-time (`steps-ACME-11` without the skill, `steps-ACME-12` with it), which the 600-second limit then in place scored as failures |
| 2026-11-21 | `first-timeout-rerun`, `first-timeout-rerun-11` | Those two cases rerun with the 20-minute limit. Read these rows in place of the timed-out ones above |
