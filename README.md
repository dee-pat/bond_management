### Bond Management

Portfolio management with bonds

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app bond_management
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/bond_management
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade
- Frappe Semgrep rules through the shared verification script
- Bond Management Semgrep rules with positive and negative regression fixtures
### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app, runs the server verification gate, and runs a separate
  focused headless Cypress smoke gate on pushes to `main` and `version-16`.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
