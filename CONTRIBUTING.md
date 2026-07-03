# Contributing to Power-Safety-UA

Thank you for your interest in contributing to **Power-Safety-UA**! We welcome contributions to improve monitoring reliability, security, and developer experience.

## Code of Conduct
Please be respectful and constructive in all communication and interactions within the community.

## How to Contribute

### 1. Report Bugs / Request Features
Before writing code, please open an Issue to discuss the changes you want to introduce. Mark it with appropriate labels (e.g., `bug`, `enhancement`, `documentation`).

### 2. Branch Workflow
Always use a Pull Request workflow:
1. Create an issue describing the feature or bug.
2. Create a branch locally: `git checkout -b feature/your-feature-name` (or `bugfix/your-bugfix-name`).
3. Implement your changes.
4. Run tests and linting.
5. Push to your fork and create a Pull Request against the `main` branch.

### 3. Signing Commits
All commits to public repositories MUST be signed using your GPG key:
- Commit author name: `weby-homelab`
- Commit email: `rekvizitor.ua@gmail.com`
- GPG Key: `2D49E810C7F2527E`

Command to commit with signature:
```bash
git commit -S -m "Your descriptive commit message"
```

### 4. Running Tests
Verify your changes by running pytest locally inside the virtual environment:
```bash
PYTHONPATH=. pytest tests/ -v
```

### 5. Docker Guidelines
- Follow multi-stage build best practices.
- Do not run the container as root (`USER appuser`).
- Expose the necessary endpoints and keep ports configurable via `.env`.

Thank you for making Power-Safety-UA better! ⚡
