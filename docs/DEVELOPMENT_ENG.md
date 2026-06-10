<p align="center">
  <a href="DEVELOPMENT_ENG.md">
    <img src="https://img.shields.io/badge/🇬🇧_English-00D4FF?style=for-the-badge&logo=readme&logoColor=white" alt="English README">
  </a>
  <a href="DEVELOPMENT.md">
    <img src="https://img.shields.io/badge/🇺🇦_Українська-FF4D00?style=for-the-badge&logo=readme&logoColor=white" alt="Українська версія">
  </a>
</p>

<br>

# Development Rules (Zero Regression Tolerance Protocol)

This document describes the strict development rules that all developers (and AI assistants) must follow when working on projects in this repository.

## 1. Prohibition of "Blind" Commits
Before every `git commit` and `git push`, you must always review the changes:
```bash
git diff --cached
```
**Carefully read every line.** If you see unexpected code deletions or logic changes you didn't plan to make, stop immediately and revert the changes. It is forbidden to blindly accept merge conflicts using `git checkout --theirs` or `git checkout --ours` for Python files or logic files. You are required to open the file and resolve the conflict manually.

## 2. Branching Strategy
The project uses one main branch:
- `main` - for the Docker environment (production and testing).

**Never make changes directly to `main`.** 
- Use temporary branches (`fix/...`, `feat/...`, `docs/...`).
- Before merging a temporary branch into `main`, always ensure your branch is up to date (`git pull --rebase origin main`).

## 3. Isolation of Changes
- If the task is to update documentation (`README.md`), include **only** documentation files in the commit.
- It is forbidden to use `git add .` unless you are absolutely sure about all the changed files. 

## 4. Mandatory Testing (Unit Tests)
- No change in the logic of the scripts (report generation, time calculations) can be deployed without coverage by automated tests.
- Tests are located in the `tests/` directory.
- Before pushing, be sure to run the check:
```bash
python3 -m pytest tests/
```
If the tests fail, pushing is forbidden!

## 5. Pre-Release Checklist
1. Check tests (`pytest`).
2. Ensure your branch is up to date with `main`.
3. Update the `VERSION` file.
4. Update the version in `docker-compose.yml`, `README.md`, and `README_ENG.md`.
5. Create `git tag vX.Y.Z` and push the code to the server.