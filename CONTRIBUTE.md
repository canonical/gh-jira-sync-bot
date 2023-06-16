## Table of Contents

<!-- toc -->

- [Configure your environment](#configure-your-environment)
- [Run all tests and validations via tox](#run-all-tests-and-validations-via-tox)
- [Build package](#build-package)

<!-- tocstop -->

## Configure your environment
Install all dependencies
```bash
pip install .[test]
```

Install pre-commit
```bash
pre-commit install
```

Install tox globally on your machine. See [tox installation](https://tox.wiki/en/latest/install.html)

## Run all tests and validations via tox
```bash
tox
```


## Build package
package is built using:
```bash
flit build
```

## Build docker
```bash
version=0.0.5
sudo docker buildx build -t github_jira_sync_app --output type=docker .
sudo docker tag github_jira_sync_app ghcr.io/canonical/gh-jira-sync-bot:$version
sudo docker push ghcr.io/canonical/gh-jira-sync-bot:$version
```