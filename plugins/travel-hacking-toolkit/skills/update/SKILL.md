---
name: update
description: Efficiently bring upstream travel-hacking-toolkit updates into a customized install, with preview, selective cherry-pick, and low token usage.
category: meta
summary: Pull upstream updates safely. Preview, merge, and re-apply local skill disables.
api_key: None
---

# About

Your travel-hacking-toolkit fork drifts from upstream as you customize it. This skill pulls upstream changes into your install without losing your modifications.

Run `/update` in Claude Code.

## How it works

**Preflight**: checks for clean working tree (`git status --porcelain`). If `upstream` remote is missing, asks you for the URL (defaults to `https://github.com/borski/travel-hacking-toolkit.git`) and adds it. Detects the upstream branch name (`main` or `master`).

**Backup**: creates a timestamped backup branch and tag (`backup/pre-update-<hash>-<timestamp>`, `pre-update-<hash>-<timestamp>`) before touching anything. Safe to run multiple times.

**Preview**: runs `git log` and `git diff` against the merge base to show upstream changes since your last sync. Groups changed files into categories:

- **Skills** (`.claude/skills/`): unlikely to conflict unless you edited an upstream skill
- **Source** (`CLAUDE.md`): may conflict if you modified the same files
- **Build/config** (`package.json`, `.mcp.json`): review needed

**Update paths** (you pick one):

- `merge` (default): `git merge upstream/<branch>`. Resolves all conflicts in one pass.
- `cherry-pick`: `git cherry-pick <hashes>`. Pull in only the commits you want.
- `rebase`: `git rebase upstream/<branch>`. Linear history, but conflicts resolve per-commit.
- `abort`: just view the changelog, change nothing.

**Conflict preview**: before merging, runs a dry-run (`git merge --no-commit --no-ff`) to show which files would conflict. You can still abort at this point.

**Conflict resolution**: opens only conflicted files, resolves the conflict markers, keeps your local customizations intact.

## Rollback

The backup tag is printed at the end of each run:

```
git reset --hard pre-update-<hash>-<timestamp>
```

Backup branch `backup/pre-update-<hash>-<timestamp>` also exists.

## Token usage

Only opens files with actual conflicts. Uses `git log`, `git diff`, and `git status` for everything else. Does not scan or refactor unrelated code.

---

# Goal

Help a user with a customized travel-hacking-toolkit install safely incorporate upstream changes without a fresh reinstall and without blowing tokens.

# Operating principles

- Never proceed with a dirty working tree.
- Always create a rollback point (backup branch + tag) before touching anything.
- Prefer git-native operations (fetch, merge, cherry-pick). Do not manually rewrite files except conflict markers.
- Default to MERGE (one-pass conflict resolution). Offer REBASE as an explicit option.
- Keep token usage low: rely on `git status`, `git log`, `git diff`, and open only conflicted files.

# Step 0: Preflight (stop early if unsafe)

Run:

- `git status --porcelain`
  If output is non-empty:
- Tell the user to commit or stash first, then stop.

Confirm remotes:

- `git remote -v`
  If `upstream` is missing:
- Ask the user for the upstream repo URL (default: `https://github.com/borski/travel-hacking-toolkit.git`).
- Add it: `git remote add upstream <user-provided-url>`
- Then: `git fetch upstream --prune`

Determine the upstream branch name:

- `git branch -r | grep upstream/`
- If `upstream/main` exists, use `main`.
- If only `upstream/master` exists, use `master`.
- Otherwise, ask the user which branch to use.
- Store this as UPSTREAM_BRANCH for all subsequent commands. Every command below that references `upstream/main` should use `upstream/$UPSTREAM_BRANCH` instead.

Fetch:

- `git fetch upstream --prune`

# Step 1: Create a safety net

Capture current state:

- `HASH=$(git rev-parse --short HEAD)`
- `TIMESTAMP=$(date +%Y%m%d-%H%M%S)`

Create backup branch and tag (using timestamp to avoid collisions on retry):

- `git branch backup/pre-update-$HASH-$TIMESTAMP`
- `git tag pre-update-$HASH-$TIMESTAMP`

Save the tag name for later reference in the summary and rollback instructions.

# Step 2: Preview what upstream changed (no edits yet)

Compute common base:

- `BASE=$(git merge-base HEAD upstream/$UPSTREAM_BRANCH)`

Show upstream commits since BASE:

- `git log --oneline $BASE..upstream/$UPSTREAM_BRANCH`

Show local commits since BASE (custom drift):

- `git log --oneline $BASE..HEAD`

Show file-level impact from upstream:

- `git diff --name-only $BASE..upstream/$UPSTREAM_BRANCH`

Bucket the upstream changed files:

- **Skills** (`.claude/skills/`): unlikely to conflict unless the user edited an upstream skill
- **Source** (`CLAUDE.md`): may conflict if user modified the same files
- **Build/config** (`package.json`, `.mcp.json`): review needed
- **Other**: docs, tests, misc

Present these buckets to the user and ask them to choose one path using AskUserQuestion:

- A) **Full update**: merge all upstream changes
- B) **Selective update**: cherry-pick specific upstream commits
- C) **Abort**: they only wanted the preview
- D) **Rebase mode**: advanced, linear history (warn: resolves conflicts per-commit)

If Abort: stop here.

# Step 3: Conflict preview (before committing anything)

If Full update or Rebase:

- Dry-run merge to preview conflicts. Run these as a single chained command so the abort always executes:
  ```
  git merge --no-commit --no-ff upstream/$UPSTREAM_BRANCH; git diff --name-only --diff-filter=U; git merge --abort
  ```
- If conflicts were listed: show them and ask user if they want to proceed.
- If no conflicts: tell user it is clean and proceed.

# Step 4A: Full update (MERGE, default)

Run:

- `git merge upstream/$UPSTREAM_BRANCH --no-edit`

If conflicts occur:

- Run `git status` and identify conflicted files.
- For each conflicted file:
  - Open the file.
  - Resolve only conflict markers.
  - Preserve intentional local customizations.
  - Incorporate upstream fixes/improvements.
  - Do not refactor surrounding code.
  - `git add <file>`
- When all resolved:
  - If merge did not auto-commit: `git commit --no-edit`

# Step 4B: Selective update (CHERRY-PICK)

If user chose Selective:

- Recompute BASE if needed: `BASE=$(git merge-base HEAD upstream/$UPSTREAM_BRANCH)`
- Show commit list again: `git log --oneline $BASE..upstream/$UPSTREAM_BRANCH`
- Ask user which commit hashes they want.
- Apply: `git cherry-pick <hash1> <hash2> ...`

If conflicts during cherry-pick:

- Resolve only conflict markers, then:
  - `git add <file>`
  - `git cherry-pick --continue`
    If user wants to stop:
  - `git cherry-pick --abort`

# Step 4C: Rebase (only if user explicitly chose option D)

Run:

- `git rebase upstream/$UPSTREAM_BRANCH`

If conflicts:

- Resolve conflict markers only, then:
  - `git add <file>`
  - `git rebase --continue`
    If it gets messy (more than 3 rounds of conflicts):
  - `git rebase --abort`
  - Recommend merge instead.

# Step 4.5: Re-apply local skill disables (post-merge)

After a successful merge, cherry-pick, or rebase that touched
`plugins/travel-hacking-toolkit/skills/`, re-run the disable script so any
skills upstream restored are turned off again:

```
bash scripts/disable-skills.sh
```

The list of disabled skills lives in `disabled-skills.txt`. The script renames
each skill's `SKILL.md` to `SKILL.md.disabled`, which hides it from skill
discovery without deleting content. Idempotent — safe to run when nothing
needs disabling.

If the script reports newly disabled skills, stage and amend them into the
merge commit (or make a follow-up commit):

```
git add plugins/travel-hacking-toolkit/skills/*/SKILL.md.disabled
git commit -m "chore: re-disable skills after upstream merge"
```

# Step 4.6: Re-sync generated artifacts (post-merge)

Upstream's smoke test (`bash scripts/smoke-test.sh --quick`, also wired into
GitHub Actions) checks for drift between source files and generated artifacts.
After the merge resolves, run these and commit any changes:

```
bash scripts/sync-agent.sh        # CLAUDE.md -> agents/travel-hacker.md
bash scripts/gen-skill-tables.sh  # SKILL.md frontmatter -> README.md, llms.txt
bash scripts/smoke-test.sh --quick
```

If the smoke test reports `MISSING-FIELDS` for a skill, it needs
`category`, `summary`, and `api_key` in its frontmatter — add them and re-run.

# Step 5: Summary + rollback instructions

Show:

- Backup tag: the tag name created in Step 1
- New HEAD: `git rev-parse --short HEAD`
- Upstream HEAD: `git rev-parse --short upstream/$UPSTREAM_BRANCH`
- Conflicts resolved (list files, if any)
- Breaking changes applied (list skills run, if any)
- Remaining local diff vs upstream: `git diff --name-only upstream/$UPSTREAM_BRANCH..HEAD`

Tell the user:

- To rollback: `git reset --hard <backup-tag-from-step-1>`
- Backup branch also exists: `backup/pre-update-<HASH>-<TIMESTAMP>`
