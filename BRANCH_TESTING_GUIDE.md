# Branch Testing Guide — evox_erp

How to safely test any branch before merging it.

**Site:** `evox.localhost`
**Infra directory:** `C:\Users\acer\Desktop\Accounting\ERPNext\evox-erp\evox-erp-infra\`
**App repo:** `C:\Users\acer\Desktop\Accounting\ERPNext\evox-erp\evox_erp\`

---

## A. Before Switching Branch

Always save your current work first.

```bash
cd C:\Users\acer\Desktop\Accounting\ERPNext\evox-erp\evox_erp
git status
```

**If there are uncommitted changes — commit them:**

```bash
git add path/to/file
git commit -m "WIP: save current changes before switching branch"
```

**Or stash them safely:**

```bash
git stash push -m "WIP before switching to branch-name"
```

To restore a stash later:

```bash
git stash list
git stash pop
```

---

## B. Switch to the Branch

```bash
git checkout branch-name
git pull origin branch-name
```

Example:

```bash
git checkout feature/phase-1-cheque-management
git pull origin feature/phase-1-cheque-management
```

---

## C. Run ERPNext Commands After Switching

Run these from the `evox-erp-infra\` directory (PowerShell):

```powershell
cd C:\Users\acer\Desktop\Accounting\ERPNext\evox-erp\evox-erp-infra
```

**1. Rebuild the custom Docker image** (required if Python files or DocType JSON changed):

```powershell
.\scripts\windows\build-custom-image.ps1
.\scripts\windows\start-local-production.ps1
```

**2. Run migrate** (required if DocType, fixtures, or patches changed):

```powershell
docker compose --env-file env\local-production.env `
  --project-name evox_erpnext `
  -f ..\frappe_docker\compose.yaml `
  -f ..\frappe_docker\overrides\compose.mariadb.yaml `
  -f ..\frappe_docker\overrides\compose.redis.yaml `
  -f ..\frappe_docker\overrides\compose.noproxy.yaml `
  exec -T backend bench --site evox.localhost migrate
```

**3. Build assets** (required if JS or CSS changed):

```powershell
docker compose ... exec -T backend bench build --app evox_erp
```

**4. Clear cache:**

```powershell
docker compose ... exec -T backend bench --site evox.localhost clear-cache
docker compose ... exec -T backend bench --site evox.localhost clear-website-cache
```

**5. Restart services:**

```powershell
.\scripts\windows\restart-local-production.ps1
```

Or manually:

```powershell
docker compose ... restart backend websocket queue-short queue-long scheduler frontend
```

---

## D. Test Manually

Open `http://evox.localhost:8080` in your browser and test using:

**`PHASE_1_CHEQUE_TESTING_CHECKLIST.md`**

Work through every section (A through L) that applies to this branch.

---

## E. Check Logs

View live logs from `evox-erp-infra\`:

```powershell
.\scripts\windows\logs-local-production.ps1
```

Or check specific log files directly inside the container:

```powershell
docker compose ... exec -T backend tail -n 100 logs/web.error.log
docker compose ... exec -T backend tail -n 100 logs/worker.error.log
```

Run a site health check:

```powershell
docker compose ... exec -T backend bench --site evox.localhost doctor
```

---

## F. If Branch Passes — Merge Up

### Merge feature branch into development

```bash
cd C:\Users\acer\Desktop\Accounting\ERPNext\evox-erp\evox_erp
git checkout development
git pull origin development
git merge --no-ff feature/branch-name
git push origin development
```

**Then test `development` using steps C–E above before promoting.**

### Merge development into staging

```bash
git checkout staging
git pull origin staging
git merge --no-ff development
git push origin staging
```

**Then test `staging` using steps C–E above before promoting.**

### Merge staging into main

```bash
git checkout main
git pull origin main
git merge --no-ff staging
git push origin main
```

---

## G. If Branch Fails — Do Not Merge

1. Do NOT merge.
2. Note exactly what failed (screenshot, log lines, error message).
3. Go back to the feature/fix branch:

   ```bash
   git checkout feature/branch-name
   ```

4. Fix the issue.
5. Commit the fix:

   ```bash
   git add path/to/file
   git commit -m "fix: description of what was fixed"
   git push origin feature/branch-name
   ```

6. Run the full test cycle again from step C.
7. Only merge after the full checklist passes.

---

## H. Quick Reference — Common Docker Bench Commands

All commands run from `evox-erp-infra\` directory. Replace `docker compose ...` with the full compose command or wrap it in a PowerShell function.

| Task | Command |
|---|---|
| Migrate | `exec -T backend bench --site evox.localhost migrate` |
| Build assets | `exec -T backend bench build --app evox_erp` |
| Clear cache | `exec -T backend bench --site evox.localhost clear-cache` |
| Clear website cache | `exec -T backend bench --site evox.localhost clear-website-cache` |
| Restart all | `restart backend websocket queue-short queue-long scheduler frontend` |
| Site doctor | `exec -T backend bench --site evox.localhost doctor` |
| Tail web errors | `exec -T backend tail -n 100 logs/web.error.log` |
| Tail worker errors | `exec -T backend tail -n 100 logs/worker.error.log` |
| Backup site | `.\scripts\windows\backup-site.ps1` |
| Diagnose | `.\scripts\windows\diagnose-local-production.ps1` |
