from __future__ import annotations

import builtins
import collections.abc
import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any, Callable, TypeVar

__version__ = "0.0.1"
__all__ = ["from_dict"]

IMPORT_PREFIX = "+"

IS_REFERENCE_PREFIX = "!"
DELIMITER = "/"
ROOT_PREFIX = "~"


def _import(thing: str, modules: list[object] | None = None) -> Any:
    """
    Try to import thing, falling back to the python standard library or the
    provided modules.

    Parameters
    ----------
    thing: str
        The fully qualified name of the thing to import.
    modules: list[object] | None
        A list of modules to import from.

    Returns
    -------
    Any
        The imported thing.

    Examples
    --------
    >>> _import("torch.nn.Tanh")
    <class 'torch.nn.modules.activation.Tanh'>

    >>> _import("+my_module.MyClass")
    <class 'my_module.MyClass'>

    >>> _import("+tuple")
    <class 'tuple'>
    """

    if "." not in thing:
        try:
            # try to import from python standard library
            return getattr(builtins, thing)
        except AttributeError:
            # if that fails, try to import from the provided modules
            modules = modules or []
            for module in modules:
                if hasattr(module, thing):
                    return getattr(module, thing)

            # failed! provide a useful error message and exit
            names = ["builtins"] + [module.__name__ for module in modules]  # type: ignore
            raise ImportError(
                f'Could not find "{thing}" in any of {names}'
            ) from None

    module_name, obj_name = thing.rsplit(".", 1)

    dir_command_was_run_from = str(Path(os.getcwd()).resolve())
    if dir_command_was_run_from not in sys.path:
        sys.path.append(dir_command_was_run_from)

    try:
        module = importlib.import_module(module_name)
    except ImportError:
        assumed_file = Path(module_name.replace(".", "/")).with_suffix(".py")
        if not assumed_file.exists():
            raise ImportError(
                f"While attempting to import {obj_name} from {module_name}, "
                "we could not find the module or the file "
                f"belonging to {module_name}."
            ) from None

        spec = importlib.util.spec_from_file_location(
            name=module_name, location=assumed_file
        )
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)

    return getattr(module, obj_name)


def process_data(data: Any, modules: list[object] | None = None) -> Any:
    if isinstance(data, collections.abc.Mapping):
        return process_data_mapping(data, modules)
    if isinstance(data, str):
        return process_data_str(data, modules)
    if isinstance(data, collections.abc.Sequence):
        return process_data_sequence(data, modules)
    return data


def process_data_sequence(
    data: collections.abc.Sequence[Any], modules: list[object] | None = None
) -> list[Any]:
    return [process_data(item, modules) for item in data]


def process_data_str(
    data: str | Any, modules: list[object] | None = None
) -> str | Any:
    if not isinstance(data, str) or not data.startswith(IMPORT_PREFIX):
        return data

    actual_data = data.replace(IMPORT_PREFIX, "", 1)
    if actual_data.endswith("()"):
        call = True
        actual_data = actual_data[:-2]
    else:
        call = False

    imported_data = _import(actual_data, modules)
    if call:
        return imported_data()
    else:
        return imported_data


def process_data_mapping(
    data: collections.abc.Mapping, modules: list[object] | None = None
) -> dict | Any:
    if len(data) != 1:
        return {
            process_data(key, modules): process_data(value, modules)
            for key, value in data.items()
        }

    # single item mapping: this could be a class instantiation/function call
    ((key, value),) = data.items()

    if not key.startswith(IMPORT_PREFIX):
        return {key: process_data(value, modules)}

    imported_key: Callable = _import(key.replace(IMPORT_PREFIX, "", 1), modules)
    if not callable(imported_key):
        raise ValueError(f"We imported {key}, but this is not callable.")

    arguments = process_data(value, modules)
    if isinstance(arguments, collections.abc.Mapping):
        return imported_key(**arguments)
    else:
        return imported_key(arguments)


def fill_referenced_parts(
    data: collections.abc.Mapping,
) -> collections.abc.Mapping:
    """
    Fill in references to other parts of the data structure.
    """

    return _fill_referenced_parts_recursive(data, data, [])


def _fill_referenced_parts_recursive(
    data: collections.abc.Mapping,
    global_data: collections.abc.Mapping,
    current_path: list[str],
) -> collections.abc.Mapping:
    new_data = {}
    for key, value in data.items():
        if isinstance(value, str) and value.startswith(IS_REFERENCE_PREFIX):
            new_data[key] = index_into(global_data, value, current_path)
        elif isinstance(value, collections.abc.Mapping):
            new_data[key] = _fill_referenced_parts_recursive(
                value, global_data, current_path + [key]
            )
        else:
            new_data[key] = value
    return new_data


def index_into(
    data: collections.abc.Mapping, path: str, current_path: list[str]
) -> Any:
    path = path.replace(IS_REFERENCE_PREFIX, "", 1)
    if path.startswith(ROOT_PREFIX):
        path = path[1:]
        paths = path.split(DELIMITER)
    else:
        paths = current_path + path.split(DELIMITER)

    # remove "."
    final_paths = []
    for p in paths:
        if p in " .":
            continue
        elif p == "..":
            try:
                final_paths.pop()
            except IndexError:
                raise KeyError(
                    f"This reference ({path}) appears to be mal-formed, and "
                    "contains too many `..` components."
                ) from None
        else:
            final_paths.append(p)

    og_data = data
    if len(final_paths) == 0:
        raise ValueError()

    p = final_paths[0]

    try:
        for p in final_paths:
            data = data[p]
    except KeyError:
        raise KeyError(
            f"The path we parsed ({final_paths}) does not exist in the data "
            f"({og_data}). In particular, we could not find {p} in {data}."
        ) from None

    return data


K = TypeVar("K")
V = TypeVar("V")


def from_dict(
    data: dict[K, V], modules: list[object] | None = None
) -> dict[K, V | Any]:
    """
    Transform a nested `data` structure into instantiated Python objects.

    This function recursively processes the input data, and applies the
    following special handling to any `str` objects:

    **Reference handling**:

    Any leaf-nodes within `data` that are strings and start with `"!"` are
    interpreted as references to other parts of `data`. The following syntax is
    supported:

    * `"~path"`: resolve `path` relative to the root of the `data` structure.
    * `"path"`: resolve `path` relative to the current working directory.
    * `"../path"`: resolve `path` relative to the parent of the current working
      directory.

    **Object instantiation**:

    The following handling applied to any `str` objects found within `data` (
    either as a key or value) that start with `"+"`:

    1. attempt to import the python object specified by the string:
       e.g. the string `"+torch.nn.Tanh"` will be converted to the `Tanh`
       **class** (not an instance) from the `torch.nn` module. If the string is
       not an absolute path (i.e. does not contain any dots), we attempt to
       import it from the python standard library, or any of the provided
       modules:
       - `"+Path"` with `modules=[pathlib]` will be converted to the `Path`
         **class** from the `pathlib` module.
       - `"+tuple"` will be converted to the `tuple` **type**.
    2. if the string ends with a `"()"`, the resulting object is called with
       no arguments e.g. `"+my_module.MyClass()"` will be converted to an
       **instance** of `MyClass` from `my_module`.
    3. if the string is found as key in a mapping with exactly one key-value
       pair, then:
       - if the value is itself a mapping, the single-item mapping is replaced
         with the result of calling the imported object with the recursively
         instantiated values as **keyword arguments**
       - otherwise, the single-item mapping is replaced with the result of
         calling the imported object with the instantiated value as a single
         **positional argument**

    Parameters
    ----------
    data
        The data to transform.
    modules
        A list of modules to look up non-fully qualified names in.

    Returns
    -------
    dict
        The transformed data.

    Examples
    --------

    A basic example:

    >>> instantiate_from_data({"activation": "+torch.nn.Tanh()"})
    {'activation': Tanh()}

    Note the importance of trailing parentheses:

    >>> instantiate_from_data({"activation": "+torch.nn.Tanh"})
    {'activation': <class 'torch.nn.modules.activation.Tanh'>}

    Alternatively, point `instantiate_from_data` to automatically import
    from `torch.nn`:

    >>> instantiate_from_data({"activation": "+Tanh()"}, modules=[torch.nn])
    {'activation': Tanh()}

    Use single-item mappings to instantiate classes/call functions with
    arguments. The following syntax will internally import `MyClass` from
    `my_module`, and call it as `MyClass(x=1, y=2)` with explicit keyword
    arguments:

    >>> instantiate_from_data({
    ...     "activation": "+torch.nn.ReLU()",
    ...     "model": {
    ...         "+MyClass": {"x": 1, "y": 2}
    ...     }
    ... })
    {'activation': ReLU(), 'model': MyClass(x=1, y=2)}

    In contrast, the following syntax call the imported objects with a single
    positional argument:

    >>> instantiate_from_data({"+len": [1, 2, 3]})
    3  # i.e. len([1, 2, 3])

    Mapping with multiple keys are still processed, but are never used to
    instantiate classes/call functions:

    >>> instantiate_from_data({"+len": [1, 2, 3], "+print": "hello"})
    {<built-in function len>: [1, 2, 3], <built-in function print>: 'hello'}

    `instantiate_from_data` also works with arbitrary nesting:

    >>> instantiate_from_data({"model": {"activation": "+torch.nn.Tanh()"}})
    {'model': {'activation': Tanh()}}

    **Caution**: `instantiate_from_data` can lead to side-effects!

    >>> instantiate_from_data({"+print": "hello"})
    hello

    References are resolved before object instantiation, so all of the following
    will resolve the `"length"` field to `3`:

    >>> instantiate_from_data({"args": [1, 2, 3], "length": {"+len": "!../args"}})
    3
    >>> instantiate_from_data({"args": [1, 2, 3], "length": {"+len": "!~args"}})
    3
    """  # noqa: E501

    filled = fill_referenced_parts(data)
    return process_data(filled, modules)
