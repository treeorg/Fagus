# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys

sys.path.insert(0, os.path.abspath(".."))
from fagus import __version__  # noqa: E402

# -- Project information -----------------------------------------------------

project = "Fagus"
copyright = "2022, Lukas Neuenschwander"
author = "Lukas Neuenschwander"

# The full version, including alpha/beta/rc tags
release = __version__

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "myst_parser",
]


# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]
html_css_files = ["wider_page.css"]

suppress_warnings = ["myst.header"]


# Latex
if any("pdf" in arg or "latex" in arg for arg in sys.argv) and "readthedocs.org" in os.getcwd():
    import json

    if os.path.exists("../orig_files.json"):
        with open("../orig_files.json") as f:
            orig_files = json.load(f)
    else:
        orig_files = {}
    from package import sphinx_hacks

    orig_files.update(sphinx_hacks("pdf"))
    with open("../orig_files.json", "w") as f:
        json.dump(orig_files, f)
latex_elements = {"papersize": "a4paper", "fontpkg": r"\usepackage{lmodern}"}

# -- Extension configuration -------------------------------------------------
strip_signature_backslash = True
# autoclass_content = "both"
myst_heading_anchors = 6
myst_number_code_blocks = ["python"]
autodoc_member_order = "bysource"
autodoc_type_aliases = {"OptStr": "OptStr", "OptBool": "OptBool", "OptInt": "OptInt", "OptAny": "OptAny"}
autodoc_default_options = {
    "special-members": True,
}
