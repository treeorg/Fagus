import subprocess
import platform
import os
import sys
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
@click.option(
    "-p",
    "--pre-commit",
    is_flag=True,
    help="Runs pre-commit to make sure everything is formatted correctly",
)
def update(version: str, build: bool, documentation: bool, pre_commit: bool):
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
    if documentation:
        if packaging.version.parse(platform.python_version()) < packaging.version.parse("3.7"):
            raise EnvironmentError("Sphinx-documentation can't be built on Python < 3.7 (required by the RTD theme)")
        else:
            with open("fagus/fagus.py", "r+") as f:
                fagus_py = f.read()  # __options has to be renamed to options to get the doc right (at runtime this
                f.seek(0)  # same rename is done in __init__)
                f.write(fagus_py.replace("def __options(", "def options(  "))  # two fewer chars - add spaces to end
                subprocess.run(
                    f"sphinx-apidoc -f --module-first --separate -o docs/source . tests {sys.argv[0]}",
                    shell=True,
                )
                subprocess.run("make clean html", shell=True, cwd="docs")
                f.seek(0)
                f.write(fagus_py)  # put the unchanged file back
    if pre_commit:
        subprocess.run("git add -A; pre-commit run; git add -A", shell=True)


if __name__ == "__main__":
    main()
