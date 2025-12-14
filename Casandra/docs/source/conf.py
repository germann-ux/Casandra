# Configuration file for the Sphinx documentation builder.

import os
import sys

# Añade la raíz del proyecto a sys.path para que autodoc encuentre tus módulos
sys.path.insert(0, os.path.abspath("../.."))

# -- Project information -----------------------------------------------------
project = "Casandra"
author = "Germán Uriel Evangelista Martinez"
release = "0.1.0"

# -- General configuration ---------------------------------------------------
extensions = [
    "myst_parser",            # Soporte para Markdown
    "sphinx.ext.autodoc",     # Extraer docstrings automáticamente
    "sphinx.ext.napoleon",    # Google / NumPy style docstrings
    "sphinx.ext.viewcode",    # Enlazar al código fuente
]

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_preprocess_types = True
napoleon_type_aliases = None
napoleon_attr_annotations = True

# Plantilla y tema
templates_path = ["_templates"]
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

# -- Autodoc settings --------------------------------------------------------
autodoc_member_order = "bysource"  # Ordena los miembros tal como aparecen en el código
autodoc_typehints = "description"  # Muestra hints en la descripción
