# GitHub branch protection rulesets (importable)

Reusable [GitHub Rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets) JSON files. Import the same file into every repository or once at the **organization** level.

## Quick import (one repo)

1. Open the repo on GitHub → **Settings** → **Rules** → **Rulesets**
2. **New ruleset** → **Import a ruleset**
3. Choose a JSON file from this folder
4. Review **Bypass list** (not included in export/import — add org admins if needed)
5. Set **Enforcement** to **Active** (start with **Evaluate** to test)
6. Click **Create**

## Org-wide (all repos)

1. **Organization** → **Settings** → **Repository** → **Rules** → **Rulesets**
2. **New ruleset** → **Import a ruleset**
3. Use `org-main-standard.json` (or `org-main-strict.json`)
4. Under **Target repositories**, confirm `~ALL` or pick a subset
5. **Create**

Official recipes: [github/ruleset-recipes](https://github.com/github/ruleset-recipes)

## Which file to use

| File | Scope | Use when |
|------|-------|----------|
| `repo-main-standard.json` | `main` / default branch | **Default for most projects** — PR + 1 review + CI |
| `repo-main-strict.json` | `main` / default branch | Production libs — 2 reviews + CODEOWNERS + conventional commits |
| `repo-main-solo.json` | `main` / default branch | Solo maintainer — CI gate, no review required |
| `repo-develop-light.json` | `develop` | Integration branch — block force-push/delete only |
| `org-main-standard.json` | Org → all repos → default branch | Same as standard, applied org-wide |
| `org-main-strict.json` | Org → all repos → default branch | Same as strict, applied org-wide |
| `repo-release-tags.json` | Tags `v*` | Prevent deleting release tags |

## After import — required checks

`required_status_checks` uses the **GitHub Actions job name** as `context` (not the workflow filename).

| This repo | Check context to require |
|-----------|--------------------------|
| `aws-serverless-datamesh-framework` | `lint-and-test` (workflow: **CI**) |

Other repos: open a merged PR → **Checks** tab → copy the exact job name into the ruleset.

If import fails on `integration_id`, edit the ruleset in the UI and re-select checks from the dropdown (GitHub fills the ID).

## Bypass actors (add manually after import)

| Actor | `actor_type` | Typical `actor_id` |
|-------|----------------|-------------------|
| Organization admin | `OrganizationAdmin` | `1` |
| Repository admin | `RepositoryRole` | `5` |

Use bypass only for break-glass (incident hotfix), not day-to-day merges.

## Optional: sync with GitHub CLI

```bash
# Repo ruleset (needs admin:repo_hook or repo admin)
gh api repos/OWNER/REPO/rulesets --method POST --input .github/rulesets/repo-main-standard.json
```

Org ruleset:

```bash
gh api orgs/ORG/rulesets --method POST --input .github/rulesets/org-main-standard.json
```

## Recommended stack for this framework

1. `repo-main-standard.json` on `main`
2. `repo-develop-light.json` if you use `develop`
3. `repo-release-tags.json` for `v*` tags
4. Enable **Require signed commits** in UI if your org uses GPG/SSH signing
