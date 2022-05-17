import subprocess
import platform
import os
import sys
from typing import Optional

import click
import packaging.version


@click.group()
def main():
    if not os.getcwd().endswith("Fagus"):
        raise EnvironmentError(
            f"{sys.argv[0]} must be run from the project directory (Fagus, where this script is placed)"
        )


@main.command(help="version number, documentation, package")
@click.option(
    "-v",
    "--version",
    default=None,
    help="Bumps version number to the next patch, minor or major release. See poetry version command",
)
@click.option("-b", "--build", is_flag=True, help="Builds the package wheel into dist")
@click.option("-d", "--documentation", is_flag=True, help="Updates the sphinx documentation")
@click.option("-l", "--latex-pdf", is_flag=True, help="Builds documentation pdf using latex. ")
@click.option(
    "-p",
    "--pre-commit",
    is_flag=True,
    help="Runs pre-commit to make sure everything is formatted correctly",
)
def update(version: str, build: bool, documentation: bool, latex_pdf: bool, pre_commit: bool):
    if version:
        new_version = subprocess.run(f"poetry version {version}", shell=True, capture_output=True, text=True)
        if new_version.returncode:
            print(new_version.stderr, file=sys.stderr)
            exit(new_version.returncode)
        print(new_version.stdout.strip())
        with open("fagus/__init__.py") as init_py:
            lines = init_py.read().splitlines() + [""]
        for i, l in filter(lambda e: e[1].startswith("__version__"), enumerate(lines)):
            lines[i] = f'__version__ = "{new_version.stdout.split()[-1]}"'
            break
        with open("fagus/__init__.py", "w") as init_py:
            init_py.write("\n".join(lines))
    if build:
        subprocess.run("poetry build", shell=True)
    if documentation or latex_pdf:
        subprocess.run(
            f"sphinx-apidoc -f --module-first --separate -o docs . tests {sys.argv[0]}",
            shell=True,
        )
        original_files = sphinx_hacks("general")
        subprocess.run("make clean", shell=True, **({} if os.getcwd().endswith("docs") else {"cwd": "docs"}))
        if documentation:
            if packaging.version.parse(platform.python_version()) < packaging.version.parse("3.7"):
                raise EnvironmentError(
                    "Sphinx-documentation can't be built on Python < 3.7 (required by the RTD theme)"
                )
            subprocess.run("make html", shell=True, **({} if os.getcwd().endswith("docs") else {"cwd": "docs"}))
        if latex_pdf:
            original_files.update(sphinx_hacks("pdf", original_files))
            subprocess.run("make latexpdf", shell=True, **({} if os.getcwd().endswith("docs") else {"cwd": "docs"}))
        sphinx_hacks(restore=original_files)
    if pre_commit:
        subprocess.run("git add -A; pre-commit run; git add -A", shell=True)


def sphinx_hacks(hack: str = "", restore: dict = None) -> Optional[dict]:
    """Change some files before building, or restore them if restore has been specified

    Args:
        hack: general always has to be applied, pdf has to be applied when pdf's are generated
        restore: dict with filepath as key and the original content of the file before the hack as value

    Returns:
        None dict with filepath as key and the original content of the file before the hack as value
    """
    files = {}
    try:
        if hack == "general":
            filepath = f"{'..' if os.getcwd().endswith('docs') else '.'}/fagus/fagus.py"
            with open(filepath, "r+") as f:
                files[filepath] = f.read()  # __options has to be renamed to options to get the doc right (at runtime
                f.seek(0)  # exactly the same rename is done in __init__)
                f.write(files[filepath].replace("def __options(", "def options(  "))  # add spaces to have same length
                f.seek(0)
            filepath = f"{'..' if os.getcwd().endswith('docs') else '.'}/LICENSE.md"
            with open(filepath, "r+") as f:
                files[filepath] = f.read()
                f.seek(0)
                f.write("# " + files[filepath])  # make ISC-License a heading
                f.seek(0)
            filepath = f"{'.' if os.getcwd().endswith('docs') else 'docs'}/modules.rst"
            if os.path.exists(filepath):
                os.remove(filepath)
        elif hack == "pdf":
            filepath = f"{'..' if os.getcwd().endswith('docs') else '.'}/README.md"
            with open(filepath, "r+") as f:
                files[filepath] = f.read()
                f.seek(0)
                lines = files[filepath].splitlines()
                f.write("\n".join(["# README" + (len(lines[0]) - len("README") - 2) * " "] + lines[1:]))
                f.seek(0)
            filepath = f"{'.' if os.getcwd().endswith('docs') else 'docs'}/index.rst"
            with open(filepath, "r+") as f:
                files[filepath] = f.read()
                pos = files[filepath].index("Indices and tables")
                f.seek(pos)
                f.write(" " * (len(files[filepath]) - pos))
                f.seek(0)
        elif restore:
            for file, content in restore.items():
                with open(file, "w") as f:
                    f.write(content)
            return
    except (FileNotFoundError, ValueError, KeyError) as e:
        for file, content in {**files, **(restore if restore else {})}.items():
            with open(file, "w") as f:
                f.write(content)
        print("Restored all changed files before aborting")
        raise e
    return files


if __name__ == "__main__":
    main()
