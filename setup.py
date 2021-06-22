#!/usr/bin/env python

import setuptools
import toml

"""
Minimal version of setup.py to allow pip editable installs 
(pip -e /git/repo/nuvo-serial) during development.

pyproject.toml is slowly being adopted by python (PEP517/8) for packaging
Poetry uses pyproject.toml so doesn't require a setup.py.
pip: 
 * is PEP517 compliant 
 * detects and reads pyproject.toml
 * works for non-editable installs
 * as of 21.1.2 does not work for editable installs and still requires a setup.py:

 pip._internal.exceptions.InstallationError: File "setup.py" or "setup.cfg" not found. 
 Directory cannot be installed in editable mode
 (A "pyproject.toml" file was found, but editable mode currently requires a 
 setuptools-based build.)

"""

if __name__ == "__main__":
    with open('pyproject.toml', 'r') as f:
        pyproject = toml.load(f)

    poetry = pyproject['tool']['poetry']
    name = poetry['name']
    version = poetry['version']
    packages = ['nuvo_serial']

    setuptools.setup(name=name, packages=packages, version=version)
