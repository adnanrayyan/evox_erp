# Development Workflow — evox_erp

This document defines the Git and development workflow for the `evox_erp` custom Frappe/ERPNext app.

**Site:** `evox.localhost`
**ERPNext Version:** v16 (stay on `version-16` only)
**Setup:** Docker-based via `frappe_docker` + `evox-erp-infra`

All `bench` commands are run inside the Docker backend container. The shorthand used throughout this document is:

```powershell
# Run from: C:\Users\acer\Desktop\Accounting\ERPNext\evox-erp\evox-erp-infra
.\scripts\windows\<script>.ps1

# Or directly via Docker Compose:
docker compose --env-file env\local-production.env `
  --project-name evox_erpnext `
  -f ..\frappe_docker\compose.yaml `
  -f ..\frappe_docker\overrides\compose.mariadb.yaml `
  -f ..\frappe_docker\overrides\compose.redis.yaml `
  -f ..\frappe_docker\overrides\compose.noproxy.yaml `
  exec -T backend bench --site evox.localhost <command>
```

---

## A. Branch Structure

| Branch | Purpose |
|---|---|
| `main` | Stable/safe. Only tested and approved code. Future production uses this. |
| `staging` | Final testing before merging to main. Near-production state. |
| `development` | Integration branch. Feature/fix branches merge here first. |
| `feature/*` | New features. Always branched from `development`. |
| `fix/*` | Bug fixes. Always branched from `development`. |
| `chore/*` | Maintenance tasks (updates, refactors, config). Branched from `development`. |
| `hotfix/*` | Urgent production fixes only. Branched from `main`, merged to `main` AND `development`. |

### Rules

- Never commit directly to `main`.
- Never commit directly to `staging`.
- Avoid committing directly to `development` except controlled merge commits.
- All new work starts from `development`.
- Merges always use `--no-ff` to preserve history.

### Expected Merge Flow

```
feature/* or fix/* or chore/*
    → development
        → staging
            → main
```

---

## B. Daily Development Flow

### Start new work

```bash
git checkout development
git pull origin development
git checkout -b feature/name-of-feature
```

### Work and commit

```bash
git status
git diff
git add path/to/changed/file.py
git commit -m "feat: clear description of what this commit does"
git push origin feature/name-of-feature
```

### Merge into development

```bash
git checkout development
git pull origin development
git merge --no-ff feature/name-of-feature
git push origin development
```

Then test `development`. After it passes, promote to `staging`:

```bash
git checkout staging
git pull origin staging
git merge --no-ff development
git push origin staging
```

Test `staging`. After it passes, promote to `main`:

```bash
git checkout main
git pull origin main
git merge --no-ff staging
git push origin main
```

---

## C. What to Run After Each Code Change

### Python / Controller / Server-Side Logic

```powershell
# Inside evox-erp-infra\:
docker compose ... exec -T backend bench --site evox.localhost clear-cache
docker compose ... restart backend websocket queue-short queue-long scheduler
```

Or via script:

```powershell
.\scripts\windows\restart-local-production.ps1
```

### JavaScript / CSS / Client Scripts

```powershell
docker compose ... exec -T backend bench build --app evox_erp
docker compose ... exec -T backend bench --site evox.localhost clear-cache
```

### DocType / Custom Fields / Fixtures / Patches (schema changes)

```powershell
docker compose ... exec -T backend bench --site evox.localhost migrate
docker compose ... exec -T backend bench --site evox.localhost clear-cache
docker compose ... restart backend websocket queue-short queue-long scheduler
```

### After Modifying Fixtures

```bash
# Export fixtures from inside the container, or copy updated fixture files,
# then review what changed:
git diff evox_erp/fixtures/
```

---

## D. Branch Testing Process

Follow these steps before merging any branch. See also `BRANCH_TESTING_GUIDE.md`.

1. Save current work (commit or stash).
2. Switch to the branch to test.
3. Pull latest.
4. Run migrate if schema changed.
5. Run build if JS/CSS changed.
6. Clear cache.
7. Restart bench services.
8. Test manually using `PHASE_1_CHEQUE_TESTING_CHECKLIST.md`.
9. Check logs for errors.
10. Only merge if everything passes.

```powershell
git checkout feature/branch-name
git pull origin feature/branch-name

docker compose ... exec -T backend bench --site evox.localhost migrate
docker compose ... exec -T backend bench build --app evox_erp
docker compose ... exec -T backend bench --site evox.localhost clear-cache
docker compose ... exec -T backend bench --site evox.localhost clear-website-cache
docker compose ... restart backend websocket queue-short queue-long scheduler frontend
```

Check logs:

```powershell
docker compose ... exec -T backend bench --site evox.localhost doctor
```

Or tail live logs from `evox-erp-infra\`:

```powershell
.\scripts\windows\logs-local-production.ps1
```

---

## E. ERPNext Update Workflow

Before updating ERPNext or Frappe:

1. Take a full backup.
2. Create an update branch.
3. Stay on `version-16` only — do NOT update to version-17 or develop.
4. Do not update directly on `main`.

```bash
git checkout development
git checkout -b chore/update-erpnext-v16-x
```

Take backup first:

```powershell
.\scripts\windows\backup-site.ps1
```

Then update (from inside the frappe_docker directory or via infra scripts):

```powershell
# Switch ERPNext/Frappe to version-16 (already should be)
# bench switch-to-branch version-16 frappe erpnext  # only if needed
# bench update                                       # only if needed

docker compose ... exec -T backend bench --site evox.localhost migrate
docker compose ... exec -T backend bench build --app evox_erp
docker compose ... restart backend websocket queue-short queue-long scheduler frontend
```

Test the update branch, then merge:

```
chore/update-erpnext-v16-x → development → staging → main
```

---

## F. What NOT to Do

- **Do not edit `apps/erpnext` directly.** Customize via custom app only.
- **Do not edit `apps/frappe` directly.** Use hooks, overrides, and custom doctypes.
- **Do not commit secrets, passwords, API keys, or `site_config.json`.**
- **Do not commit `env/local-production.env`.**
- **Do not merge to `main` without testing `staging`.**
- **Do not switch to version-17 or develop branches** of ERPNext or Frappe.
- **Do not run destructive database commands without a backup.**
- **Do not force push** to `main`, `staging`, or `development`.
- **Do not reset `--hard`** without confirming you have a backup.
- **Do not skip Git hooks** (`--no-verify`).
