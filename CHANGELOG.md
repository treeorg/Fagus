# Changelog
**2023-08-20 1.1.2 Fixed some errors in the documentation introduced in 1.1.0**
- Removed caret dependency for Python 3.6, so now it is compatible with any future Python version.
- Ensure that `TypeAlias` also works in readthedocs
- Added automatically updated TOC to README and CONTRIBUTING

**2023-08-19 1.1.0 Fixed strong typing and added more documentation**

- Added mypy as a build-dependency to ensure correct and strong typing in the whole library. Consequences:
  - `TypeAlias` was added to make Fagus Options more clear.
  - Now, `OptStr`, `OptBool`, `OptInt` and `OptAny` clearly declare what the ... means, and make it strongly typed.
- Added external dependency `type_extensions >= 3.74` for Python < 3.10
  - This was necessary to support `TypeAlias`. However, with `>= 3.74` which was released in June 2019, this dependency is kept as open and forgiving as possible.
  - For Python >= 3.10, `Fagus` still has no external dependencies.
- Renamed the `FagusOption` `value_split` to `path_split` which is more descriptive of what it is doing.
- More documentation in README: now all the different `FagusOption`s are documented properly, as well as the basic `set()`, `get()`, `update()`, `add()`, `insert()` and `extend()`-functions.

**2022-05-13 1.0.1 Release of Fagus on GitHub and ReadTheDocs**

Now. Finally. The documentation is still not completely ready but it's time to get some feedback from the community.

**2022-04-05 1.0.0 Renaming to Fagus**

Checking GitHub I found that there already were several other libraries and programs having TreeO as a name which I had chosen originally. I then found another (much cooler) name which wasn't in use yet.

**2022-04 0.9.0 Release getting closer**

Development has been ongoing for almost a year. Documentation and testing takes time, but it is absolutely necessary for a library like this. Finally moving away from two Python-files (one for tests and one for the lib) to a proper `poetry`-project, starting to implement sphinx to parse the docstrings that had been written earlier.

**2021-06 0.1.0 First idea for TreeO**

Development starts, the idea to this was born writing my Bachelor's thesis where I felt that constantly writing `.get("a", {}).get("b", {}).get("c", {})` was too annoying to go on with.
