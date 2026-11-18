# Contributing to CodeScape

Keep `main` ready for the capabilities currently implemented. Build each change
on a short-lived branch and merge it through a pull request after validation.
The first empty-repository bootstrap is the only direct initial push to `main`.

## Branches and pull requests

Use names such as `feat/phase-1-backend`, `fix/sandbox-timeout`,
`docs/setup-guide` or `chore/dependency-update`. One branch should address one
coherent outcome. A permanent `develop` branch is unnecessary for this single-user
project; add release branches only when maintaining multiple shipped versions.

Start from the latest main with a clean working tree:

```bash
git switch main
git pull --ff-only origin main
git switch -c feat/short-description
```

Inspect `git status` and `git diff` before staging. Stage named files or selected
hunks with `git add --patch`, then inspect `git diff --cached`. Exclude `.env`,
credentials, caches, generated runs and machine-specific evidence. Never commit
an access token in a remote URL or configuration file.

Push the feature branch and open a PR against `main`. Describe the concrete
behavior, validation, intentional limitations and rollback plan. Address feedback
with focused follow-up commits. Prefer a **merge commit** for a PR whose component
commits should be preserved; squash would discard that individual history. Leave
the PR open until required checks pass and its changes have been reviewed.

When there is only one maintainer, self-review the diff after tests; do not claim
an independent approval occurred. Branch protection should require passing CI,
resolved discussions and up-to-date branches, block force-push/deletion, and
apply to administrators. An external reviewer can be required once another
maintainer is available. Repository settings and plan limitations determine
which protections are actually enforceable; a written policy alone is not one.

## Commit messages

Use `<type>(<scope>): <specific outcome>` with an imperative subject. Types include
`feat`, `fix`, `test`, `docs`, `ci`, `chore` and `refactor`. Add a body explaining
the problem, decisions and validation where these help the reviewer. For example:

```text
fix(sandbox): provide writable tmpfs for pytest startup

Pytest initializes output capture even for its version probe. Give that
container the same bounded temporary filesystem as baseline runs while
retaining the read-only root and repository.

Validation: container version probe and four-test baseline pass.
```

Keep logically independent changes in separate commits. Keep tightly coupled
files together so a commit is understandable and useful to revert. Do not make
one commit per file merely to inflate history. Initial imported work is grouped
by responsibility; its commits record this import honestly and are not backdated
to simulate a development history that was never recorded.

## Code comments and fixture changes

Use docstrings for public behavior/contracts and comments for non-obvious reasons,
security boundaries, constraints and intentional defects. Avoid comments that
merely repeat the next line. Document a workaround with its reason and removal
condition. Keep comments current when behavior changes.

The showcase signature verifier is deliberately defective. Its docstring explains
the contract and purpose; do not silently repair it as cleanup. The reviewed
source/oracle hashes must be reviewed and updated together if fixture bytes change.
Line-ending rules in `.gitattributes` preserve those bytes on Windows and Linux.

## Validation

Phase-specific checks are documented with each implementation. For Phase 0, use
the host-safe structural validator and tooling unit tests, then run the application
baseline and contract oracle only in Docker. The expected red contract suite is
not a failing clean baseline. CI checks actual outcomes and rejects missing,
skipped or inconsistent evidence. Keep later task-tracker features planned until
their own acceptance criteria pass.

## Rollback without rewriting shared history

Use `git log --oneline --decorate` and inspect the relevant diff before reverting.
Create a fix branch from current `main` and make the revert through a new PR.
For one focused commit:

```bash
git switch main
git pull --ff-only origin main
git switch -c fix/revert-description
git revert <commit-sha>
```

For a whole PR merged with a merge commit, first confirm parent 1 is the original
mainline, then use `git revert -m 1 <merge-commit-sha>`. This creates a new commit
undoing that PR while retaining its history. Reverting a merge also affects later
re-merging of the same commits; review the resulting diff and dependencies.

Run the checks and submit the rollback PR. A revert may require dependent changes
or a database migration plan; passing Git's merge check does not prove runtime
compatibility. Avoid `git reset --hard` and force-pushes on shared branches.
After a reviewed milestone is merged and verified on `main`, create an annotated
release tag pointing at that exact commit. Tags are reference points, not backups
of databases, secrets or local artifacts.
