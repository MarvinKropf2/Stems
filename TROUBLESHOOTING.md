# Troubleshooting

## Error 1 — `npm install` fails with `EALLOWREMOTE` (SIX Artifactory)

```
npm error code EALLOWREMOTE
npm error Fetching packages of type "remote" have been disabled
npm error Refusing to fetch "vite@https://artifactory.six-group.net/.../vite-8.2.1.tgz"
```

**Cause:** npm is trying to download packages from the SIX corporate Artifactory
(`artifactory.six-group.net`) instead of the public npm registry. This comes from
(a) an old `package-lock.json` whose URLs point at Artifactory, and/or (b) a global
npm config on your Mac that forces the SIX registry.

**Fix:**

1. **Get the cleaned lockfile.** The `package-lock.json` on `main` now points at
   `registry.npmjs.org`. Make sure you have it (if `git pull` is blocked, do Error 2 first):

   ```bash
   git pull origin main
   ```

2. **Point npm at the public registry** (overrides a corporate global config):

   ```bash
   npm config set registry https://registry.npmjs.org/
   npm config get registry    # should print https://registry.npmjs.org/
   ```

3. **Remove any leftover SIX lines from your global npm config:**

   ```bash
   cat ~/.npmrc
   ```

   Delete any line mentioning `six-group`, `artifactory`, `_auth`, or `always-auth`,
   then save the file.

4. **Clean reinstall:**

   ```bash
   cd frontend
   rm -rf node_modules
   npm install
   ```

---

## Error 2 — `git pull` fails: "Need to specify how to reconcile divergent branches"

```
hint: You have divergent branches and need to specify how to reconcile them.
fatal: Need to specify how to reconcile divergent branches.
```

**Cause:** Your local `main` and the GitHub `main` have both moved on separately,
so git won't guess how to combine them.

**Fix — pick one:**

- **Keep your local commits (merge):**

  ```bash
  git config pull.rebase false
  git pull origin main
  ```

  If there's a conflict in `package-lock.json`, take the GitHub version:

  ```bash
  git checkout --theirs frontend/package-lock.json
  git add frontend/package-lock.json
  git commit
  ```

- **Discard local changes and just take the GitHub version** (⚠️ throws away any
  local commits/edits):

  ```bash
  git fetch origin
  git reset --hard origin/main
  ```

To avoid the prompt in future, set a default once:

```bash
git config --global pull.rebase false
```
