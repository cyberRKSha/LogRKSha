# Contributing to LogRKSha

Thank you for your interest in contributing to LogRKSha. This document outlines the process for submitting changes.

## Getting Started

1. Fork the repository and clone your fork locally.
2. Follow the [Installation](README.md#installation) instructions in the README.
3. Create a new branch from `master` for your work:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Setup

Ensure all infrastructure services (PostgreSQL, Redis, RabbitMQ) are running before starting development. The `.env.example` file contains all required configuration variables.

```bash
# Activate the virtual environment
source venv-s/bin/activate

# Run the test suite to verify your setup
pytest
```

## Making Changes

- Keep commits focused and atomic. Each commit should represent a single logical change.
- Write descriptive commit messages. Use the imperative mood ("Add detection module" not "Added detection module").
- Follow the existing code style. The project uses standard Python conventions (PEP 8).
- Add or update tests for any new functionality.

## Submitting a Pull Request

1. Push your branch to your fork.
2. Open a pull request against the `master` branch of the upstream repository.
3. Provide a clear description of the changes and the problem they solve.
4. Ensure the CI pipeline passes (pytest runs automatically on PRs).

## Reporting Issues

Use the GitHub issue tracker to report bugs or request features. When reporting a bug, include:

- Steps to reproduce the issue
- Expected behavior
- Actual behavior
- Python version, OS, and relevant service versions (PostgreSQL, Redis, RabbitMQ)

## Code Structure

Before making changes, familiarize yourself with the [Project Structure](README.md#project-structure) section of the README. Key areas:

- **Detection logic**: `scripts/worker.py`, `scripts/sigma_engine.py`, `scripts/zeek_ml_engine.py`
- **API endpoints**: `app/api/`
- **Frontend**: `app/static/js/`, `app/templates/`
- **Database models**: `app/db_models.py`
- **Tests**: `tests/`

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
