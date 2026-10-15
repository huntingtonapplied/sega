"""
SEGA Protection Module

Code protection tools for compiling and obfuscating source code:
- Nuitka: Python to standalone binary
- Bytenode: Node.js to V8 bytecode
- JavaScript Obfuscator: JS code obfuscation
"""

from .nuitka import NuitkaCompiler
from .bytenode import BytenodeCompiler
from .jsobfuscator import JSObfuscator

__all__ = [
    "NuitkaCompiler",
    "BytenodeCompiler",
    "JSObfuscator",
]
