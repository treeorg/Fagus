# Contributing to TreeO

:+1: :partying_face: First off, welcome and thank you for taking the time to contribute to TreeO! Any contribution, big or small, is welcome to make TreeO more useful such that more people can benefit from it. :+1: :partying_face:

The following is a set of guidelines for contribution to TreeO, which is hosted by the [treeorg](https://github.com/treeorg) organisation on GitHub. They are mostly guidelines, not rules. All of this can be discussed - use your best judgement, and feel free to propose changes to this document in a pull request.

### Table of contents
[TreeO Principles](#treeo-principles)

[How Can I Contribute?](#how-can-i-contribute)
  * [Reporting Bugs](#reporting-bugs)
  * [Requesting New Features](#requesting-new-features)

[Developing TreeO](#developing-treeo)
  * [Software Dependencies for Development](#software-dependencies-for-development)
  * [Code Styling Guidelines](#code-styling-guidelines)
  * [Setting Up A Local TreeO Developing Environment](#setting-up-a-local-treeo-developing-environment)
  * [Submitting Pull Requests For TreeO](#submitting-pull-requests-for-treeo)

## TreeO Principles
1. **No external dependencies**: TreeO runs on native Python without 3rd party dependencies.
2. **Documented**: All functions / modules / arguments / classes have docstrings.
3. **Tested**: All the functions shall have tests for as many edge cases as possible. It's never possible to imagine all edge-cases, but if e.g. a bug is fixed which there is no test for, a new test case should be added to prevent the bug from being reintroduced.
4. **Consistent**: TreeO's function arguments follow a common structure to be as consistent as possible.
5. **Static and Instance**: All functions in TreeO (except from \_\_internals\_\_) should be able to run static `TreeO.function(obj)` or at a TreeO-instance `obj = TreeO(); obj.function()`.
6. **Simple and efficient**: If you have suggestions on how to make the code more efficient, feel free to submit.

## How Can I Contribute?

### Reporting Bugs

This section guides you through submitting a bug report for TreeO. Following these guidelines helps maintainers and the community understand your report :pencil:, reproduce the behavior :computer: :computer:, and find related reports :mag_right:.

#### Before Submitting A Bug Report

* **Check the [FAQ](https://github.com/treeorg/TreeO/discussions/categories/q-a) and the [discussions](https://github.com/treeorg/TreeO/discussions)** for a list of common questions and problems.
* **Check [issues](https://github.com/treeorg/TreeO/issues) to see if your issue has already been reported**
  * If it has been reported **and the issue is still open**, add a comment to the existing issue instead of opening a new one.
  * If you find a **Closed** issue that seems like it is the same thing that you're experiencing, open a new issue and include a link to the original issue in the body of your new one.

#### How Do I Submit A (Good) Bug Report?

Bugs are tracked as [GitHub issues](https://guides.github.com/features/issues/). When you are creating a bug report, please [include as many details as possible (in particular test-data)](#how-do-i-submit-a-good-bug-report). Fill out [the required template](https://github.com/treeorg/TreeO/issues/new?template=bug_report.md), the information it asks for helps us resolve issues faster.

### Requesting New Features

This section guides you through submitting an enhancement suggestion for TreeO, including completely new features and minor improvements to existing functionality. Following these guidelines helps maintainers and the community understand your suggestion :pencil: and find related suggestions :mag_right:.

#### Before Submitting A Feature Request

* **Check the [FAQ](https://github.com/treeorg/TreeO/discussions/categories/q-a) and the [discussions](https://github.com/treeorg/TreeO/discussions)** for a list of common questions and problems. Probably there already is a solution for your feature-request?
* **Check [issues](https://github.com/treeorg/TreeO/issues) to see if your feature request has already been reported**
  * If it has been reported **and the feature request is still open**, add a comment to the existing issue instead of opening a new one. You can also give it a like to get it prioritized.
  * If you find a **Closed** feature request that seems like it is the same thing that you would like to get added, you can create a new one and include a link to the old one. If many people would like to have a new feature it is more likely to get prioritized.

#### How Do I Submit A (Good) Feature Request?

Feature requests are tracked as [GitHub issues](https://guides.github.com/features/issues/). When you are creating a feature request, please [include as many details as possible (in particular test-data)](#how-do-i-submit-a-good-feature-request). Fill out [the required template](https://github.com/treeorg/TreeO/issues/new?template=feature_request.md), the information it asks for helps us to better judge and understand your suggestion.

## Developing TreeO
This section shows you how you can set up a local environment to test and develop TreeO, and finally how you can make your contribution.

### Software Dependencies For Development
* [Python](https://www.python.org/) (at least 3.6.2)
* [Poetry](https://python-poetry.org) for dependency management and deployment (creating packages for PyPi), instructions are found in [installation steps](#steps-for-setting-up-a-local-treeo-developing-environment)
* [Git](https://git-scm.com/) to checkout this repo
* An IDE, I used [Intellij PyCharm Community](https://www.jetbrains.com/pycharm/download/). Not mandatory, but I found it handy to see how the data is modified in the debugger.
* TreeO itself has no external dependencies, but some packages are used to smoothen the development process. They are installed and set up through poetry, check [pyproject.toml](https://github.com/treeorg/TreeO/blob/main/pyproject.toml) or [Code Styling Rules](#code-styling-rules) for a list.

### Code Styling Guidelines
* **Code formatting**: The code is formatted using the [PEP-8-Standard](https://peps.python.org/pep-0008/), but with a line length of 120 characters.
    * The code is automatically formatted correctly by using [black](https://github.com/psf/black). Run `black .` to ensure correct formatting for all py-files in the repo.
    * The PEP-8-rules are verified through [flake8](https://flake8.pycqa.org/en/latest/). This tool only shows what is wrong - you'll have to fix it yourself.
* **Docstrings**: All public functions in TreeO have docstrings following the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
* **Formatting commit-messages**: [commitizen](https://commitizen-tools.github.io/commitizen/) is used to make sure that commit-messages follow a common style
* **Pre-commit checks**: [pre-commit](https://pre-commit.com/) is used to ensure that the code changes have test-coverage, are formatted correctly etc. It runs black, flake8, unittests and a lot of other checks prior to accepting a commit.

### Setting Up A Local TreeO Developing Environment
1. Install [Python](https://www.python.org/downloads/) and [Git](https://git-scm.com/)
2. Checkout the repository: `git checkout https://github.com/treeorg/TreeO.git; cd TreeO`
3. Instructions how to install poetry can be found [here](https://python-poetry.org/docs/)
   * you might have to reopen your terminal after installing poetry (or run `source ~/.bashrc` on Linux)
4. Run `poetry shell` to open a terminal that is set up with the development tools for TreeO.
    * check if you can now run this command without getting errors: `poetry shell`
    * if the `poetry`-command is not found, you might have to add `eval "$(pyenv init --path)"` to your `.bashrc` (on Linux)
    * if you have problems setting this up, just ask a [question](https://github. com/treeorg/TreeO/discussions/categories/q-a), we can later include the problem and the solution we found into this guide
5. Install the project and developing dependencies: `poetry install`
6. If you use an IDE, you can now open your project there. If it has a poetry mode, use that mode - `poetry shell` will then be executed automatically in the terminal of your IDE.

### Submitting Pull Requests for TreeO
If it hasn't run in your console yet, run `poetry shell` to get all the development dependencies and some new commands available in your console.

#### Tests
You can run `python3 -m unittest discover` to run all the tests in `./tests`. If you add new functionality in your pull-request, make sure that the tests still work, or update them if necessary. As this is a generic library, it's very important that all the functions have test coverage for as many edge cases as possible.

#### Committing using pre-commit and commitizen
1. Make sure all your changes are staged for commit: `git add -A` includes all of your changes
2. Dry-run the pre-commit-checks: `pre-commit`
   * Some errors like missing trailing whitespace or wrong formatting are automatically corrected.
   * If there are errors in the tests, or flake8 observes problems, you'll have to go back in the code and fix the problems.
3. Repeat Step 1 and 2 until all the tests are green.
4. Use `git cz c` to commit using commitizen.
   * If the pre-commit-checks fail, your commit is rejected and after fixing the issues you'd have to retype the commit-message. To not have that problem, do step 3 beforehand :wink:.

#### Releasing A New TreeO Package on PyPi
1. Run `poetry version <major, minor or patch>`to increment the version number in poetry.
    * **Major**: For backwards incompatible changes (e.g. removing support for Python 3.6)
    * **Minor**: Adds functionality in a backwards compatible way
    * **Patch**: Fixes bugs in a backwards compatible way
3. Run `sed -i "s/__version__ = .*\$/__version__ = \"$(poetry version -s)\"/" treeo/__init__.py` (only works on Linux / MacOS) to update the version number in the treeo-package. If you know the command to do this replacement in a windows shell, feel free to add it here.
