<div align="center">

# `data2objects`

Transform self-documenting config files and data structures into Python objects.

[![PyPI](https://img.shields.io/pypi/v/data2objects)](https://pypi.org/project/data2objects/)
[![Tests](https://github.com/jla-gardner/data2objects/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jla-gardner/data2objects/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/jla-gardner/data2objects/branch/main/graph/badge.svg)](https://codecov.io/gh/jla-gardner/data2objects)

</div>



## Installation

`pip install data2objects` or just copy `data2objects.py` into your project.

## Examples

The best way to explain the use of `data2objects` is via an example. Consider the following `config.yaml` file:

```yaml
backbone:
    activation: +torch.nn.SiLU()
    hidden_size: 1024
readout:
    +torch.nn.Linear:
        in_features: =/backbone/hidden_size
        out_features: 1
```

Parsing this file using `data2objects.from_yaml` returns the following:

```python
>>> import data2objects
>>> config = data2objects.from_yaml("config.yaml")
>>> print(config)
{'backbone': {'activation': SiLU(), 'hidden_size': 1024}, 
 'readout': Linear(in_features=1024, out_features=1, bias=True)}
```

Under-the-hood, `data2objects` has done the following:

- identified any "reference strings" prefixed by `"="` and replaced them with the corresponding values in the nested data structure
   - hence `=/backbone/hidden_size` was replaced with `1024`.
- identified any "object instantiation strings" prefixed by `"+"`, imported the corresponding objects from the provided modules and:
   - called the object if the instantiation string ends with `"()"`, i.e. `"+torch.nn.SiLU()"` created a `SiLU` object.
   - called the object with keyword arguments if the instantiation string ends with a mapping, i.e. `"+torch.nn.Linear: {in_features: =/backbone/hidden_size, out_features: 1}"` created a `Linear` object with `in_features=1024` and `out_features=1`.


## Documentation

`data2objects` exposes two functions, `from_dict` and `from_yaml`, which can be used to transform a nested data structure into a set of instantiated Python objects.


### `from_yaml`

```python
def from_yaml(thing: str | Path, modules: list[object] | None = None) -> dict:
```

> Load a nested dictionary from a yaml file or string, 
> and parse it using `data2objects.from_dict`.
>
> If `thing` points to an existing file, the data in the file is loaded.
> Otherwise, the string is treated as containing the raw yaml data.
> 
> ### Parameters
> 
> thing: `str | Path`
>     The yaml file or string to load.
> 
> modules: `list[object] | None`
>     A list of modules to look up non-fully qualified names in.

> ### Returns
> 
> `dict`
>     The transformed data.


---

### `from_dict`

```python
def from_dict(
    data: dict[K, V], modules: list[object] | None = None
) -> dict[K, V | Any]:
```

> Transform a nested `data` structure into instantiated Python objects.
> This function recursively processes the input data, and applies the
> following special handling to any `str` objects:
> 
> **Reference handling**:
> 
> Any leaf-nodes within `data` that are strings and start with `"="` are
> interpreted as references to other parts of `data`. The syntax for these
> references follows the same rules as unix paths:
> * `"=/path"`: resolve `path` relative to the root of the `data` structure.
> * `"=./path"`: resolve `path` relative to the current working directory.
> * `"=../path"`: resolve `path` relative to the parent of the current working
>   directory.
> 
> **Object instantiation**:
> 
> The following handling applied to any `str` objects found within `data` (
> either as a key or value) that start with `"+"`:
> 1. attempt to import the python object specified by the string:
>    e.g. the string `"+torch.nn.Tanh"` will be converted to the `Tanh`
>    **class** (not an instance) from the `torch.nn` module. If the string is
>    not an absolute path (i.e. does not contain any dots), we attempt to
>    import it from the python standard library, or any of the provided
>    modules:
>    - `"+Path"` with `modules=[pathlib]` will be converted to the `Path`
>      **class** from the `pathlib` module.
>    - `"+tuple"` will be converted to the `tuple` **type**.
> 2. if the string ends with a `"()"`, the resulting object is called with
>    no arguments e.g. `"+my_module.MyClass()"` will be converted to an
>    **instance** of `MyClass` from `my_module`. This is equivalent to
>    `+my_module.MyClass: {}` (see below).
> 3. if the string is found as key in a mapping with exactly one key-value
>    pair, then:
>    - if the value is itself a mapping, the single-item mapping is replaced
>      with the result of calling the imported object with the recursively
>      instantiated values as **keyword arguments**
>    - otherwise, the single-item mapping is replaced with the result of
>      calling the imported object with the instantiated value as a single
>      **positional argument**
> 
> ### Parameters
> 
> data: `dict[K, V]`
>     The data to transform.
> 
> modules: `list[object] | None`
>     A list of modules to look up non-fully qualified names in.
> 
> ### Returns
> 
> `dict`
>     The transformed data.
> 
> ### Examples
> 
> A basic example:
> 
> ```python
> >>> instantiate_from_data({"activation": "+torch.nn.Tanh()"})
> {'activation': Tanh()}
> ```
> 
> Note the importance of trailing parentheses:
> 
> ```python
> >>> instantiate_from_data({"activation": "+torch.nn.Tanh"})
> {'activation': <class 'torch.nn.modules.activation.Tanh'>}
> ```
> 
> Alternatively, point `instantiate_from_data` to automatically import
> from `torch.nn`:
> 
> ```python
> >>> instantiate_from_data({"activation": "+Tanh()"}, modules=[torch.nn])
> {'activation': Tanh()}
> ```
> 
> Use single-item mappings to instantiate classes/call functions with
> arguments. The following syntax will internally import `MyClass` from
> `my_module`, and call it as `MyClass(x=1, y=2)` with explicit keyword
> arguments:
> 
> ```python
> >>> instantiate_from_data({
> ...     "activation": "+torch.nn.ReLU()",
> ...     "model": {
> ...         "+MyClass": {"x": 1, "y": 2}
> ...     }
> ... })
> {'activation': ReLU(), 'model': MyClass(x=1, y=2)}
> ```
> 
> In contrast, the following syntax call the imported objects with a single
> positional argument:
> 
> ```python
> >>> instantiate_from_data({"+len": [1, 2, 3]})
> 3  # i.e. len([1, 2, 3])
> ```
> 
> Mapping with multiple keys are still processed, but are never used to
> instantiate classes/call functions:
> 
> ```python
> >>> instantiate_from_data({"+len": [1, 2, 3], "+print": "hello"})
> {<built-in function len>: [1, 2, 3], <built-in function print>: 'hello'}
> ```
> 
> `instantiate_from_data` also works with arbitrary nesting:
> 
> ```python
> >>> instantiate_from_data({"model": {"activation": "+torch.nn.Tanh()"}})
> {'model': {'activation': Tanh()}}
> ```
> 
> **Caution**: `instantiate_from_data` can lead to side-effects!    
> 
> ```python
> >>> instantiate_from_data({"+print": "hello"})
> hello
> ```
> 
> References are resolved before object instantiation, so all of the following
> will resolve the `"length"` field to `3`:
> 
> ```python
> >>> instantiate_from_data({"args": [1, 2, 3], "length": {"+len": "!../args"}})
> 3
> >>> instantiate_from_data({"args": [1, 2, 3], "length": {"+len": "!~args"}})
> 3
> ```
