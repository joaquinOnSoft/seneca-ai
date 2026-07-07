"""
Workaround for a detection bug in passlib (1.7.4, unmaintained since 2020) affecting modern versions of the `bcrypt` package.

`passlib` attempts to distinguish the modern, actively maintained `bcrypt` package from the old, abandoned `py-bcrypt` package by checking for the existence of the `bcrypt._bcrypt.__version__` attribute. This attribute was only supposed to exist in `py-bcrypt`, but recent builds of modern `bcrypt` (a Rust/C compiled extension) also expose it. This causes `passlib` to falsely detect it as the old, incompatible package.

**Consequence:** ALL bcrypt backends (`bcrypt` and `pybcrypt`) refuse to load, and any call to `bcrypt.hash()` or `bcrypt.verify()` within `passlib` raises a `passlib.exc.MissingBackendError` or `TypeError`.

**Bug reference within the passlib codebase:**

> `passlib/handlers/bcrypt.py` -> `_detect_pybcrypt()`

This module must be imported **BEFORE** `from passlib.hash import bcrypt` in any file that uses bcrypt via passlib.
"""

import passlib.handlers.bcrypt as _passlib_bcrypt_module

# Forzamos el resultado correcto: sabemos con certeza que el paquete
# instalado es el `bcrypt` moderno (vía pip), nunca el `py-bcrypt` abandonado.
_passlib_bcrypt_module._detect_pybcrypt = lambda: False