"""
Windows blocked the real `xxhash` package's compiled DLL (Application
Control policy on this machine). LangGraph only uses one function from
it internally, for hashing state -- not security-critical. This is a
pure-Python stand-in using the built-in hashlib, so no DLL is needed.

Because this file sits in the project root, Python finds it here first
(the current folder is checked before installed packages), so LangGraph
imports THIS instead of the real xxhash package. This is called a
"shim" -- a small substitute that satisfies an import without needing
the real dependency. Good interview line: "a native DLL dependency was
blocked by a Windows security policy, so I shimmed the one function my
code path actually needed using the standard library."
"""

import hashlib


def xxh3_128_hexdigest(data, seed=0):
    if isinstance(data, str):
        data = data.encode()
    return hashlib.md5(data).hexdigest()   # md5 = 128 bits = 32 hex chars, same length as xxh3_128


def xxh3_64_hexdigest(data, seed=0):
    if isinstance(data, str):
        data = data.encode()
    return hashlib.md5(data).hexdigest()[:16]
