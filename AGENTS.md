# Working agreements

- Use short, concrete checkpoint commit messages in the style `add: ...` and
  `fix: ...`, as requested by the user. Commit and push after meaningful,
  verified progress, not after every tool call. Do not fabricate stages or
  rewrite existing history to imitate another repository.
- Keep model implementation pending until the user reviews the proposed plan
  in `docs/PLAN.md`. Documentation and research for that review are authorized.
- Keep raw snapshots immutable and preserve their source URLs and checksums.
- Use chronological evaluation and audit feature and label availability at
  each forecast origin. Never tune on the final holdout.
