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