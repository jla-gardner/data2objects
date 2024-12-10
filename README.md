<div align="center">

# `data2objects`

Transform nested data structures into Python objects.

[![PyPI](https://img.shields.io/pypi/v/data2objects)](https://pypi.org/project/data2objects/)
[![Tests](https://github.com/jla-gardner/data2objects/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jla-gardner/data2objects/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/jla-gardner/data2objects/branch/main/graph/badge.svg)](https://codecov.io/gh/jla-gardner/data2objects)

</div>



## Installation

```
pip install data2objects
```

or just copy `data2objects.py` into your project.

## Usage

`data2objects` is intended to be used alongside config files, e.g. `.yaml`s:

```yaml
backbone:
    activation: +torch.nn.SiLU()
    hidden_size: 1024
readout:
    +torch.nn.Linear:
        in_features: '!~/backbone/hidden_size'
        out_features: 1
```

Hand off the `dict`-like structure returned by `yaml.safe_load` to `data2objects.from_dict` to:
- resolve references prefixed by `"!"` (using both global `"!~/a/b/c"` and relative `"!../../d/e"` paths)
- import any objects/classes/functions prefixed by `"+"`
- call any functions/classes as appropriate:
    - using no arguments for any `str` prefixed by `"+"` ending with `"()"`
    - using keyword arguments for any `str` prefixed by `"+"` found as a key in a mapping with exactly one key-value pair
    - using a single positional argument for any `str` prefixed by `"+"` found as a key in a mapping with exactly one key-value pair

(see documentation below for more details)

```python
import yaml  # pip install pyyaml if necessary
from data2objects import from_dict

with open("config.yaml") as f:
    data = yaml.safe_load(f)

config = from_dict(data)
print(config)
```

```
{'backbone': {'activation': SiLU(), 'hidden_size': 1024}, 
 'readout': Linear(in_features=1024, out_features=1, bias=True)}
```

Combine with the fantastic [dacite](https://github.com/konradhalas/dacite) library to instantiate nested dataclasses as config objects:

```python
from dataclasses import dataclass
import dacite
import torch

@dataclass
class Backbone:
    activation: torch.nn.Module
    hidden_size: int

@dataclass
class Config:
    backbone: Backbone
    readout: torch.nn.Module


final_config = dacite.from_dict(Config, config)
print(final_config)
```

```
Config(
    backbone=Backbone(activation=SiLU(), hidden_size=1024), 
    readout=Linear(in_features=1024, out_features=1, bias=True)
)
```


## Documentation

`data2objects` exposes a single function, `from_dict`, which can be used to transform a nested data structure into a set of instantiated Python objects:

```python
def from_dict(
    data: dict[K, V], modules: list[object] | None = None
) -> dict[K, V | Any]:
```


> Transform a nested `data` structure into instantiated Python objects.
> 
> This function recursively processes the input data, and applies the
> following special handling to any `str` objects:
> 
> **Reference handling**:
> 
> Any leaf-nodes within `data` that are strings and start with `"!"` are
> interpreted as references to other parts of `data`. The following syntax is
> supported:
> 
> * `"~path"`: resolve `path` relative to the root of the `data` structure.
> * `"path"`: resolve `path` relative to the current location.
> * `"../path"`: resolve `path` relative to the parent of the current location.
> * and so on like normal unix paths
> 
> **Object instantiation**:
> 
> The following handling applied to any `str` objects found within `data` (
> either as a key or value) that start with `"+"`:
> 
> 1. attempt to import the python object specified by the string:
>     e.g. the string `"+torch.nn.Tanh"` will be converted to the `Tanh`
>     **class** (not an instance) from the `torch.nn` module. If the string is
>     not an absolute path (i.e. does not contain any dots), we attempt to
>     import it from the python standard library, or any of the provided
>     modules:
>     - `"+Path"` with `modules=[pathlib]` will be converted to the `Path`
>         **class** from the `pathlib` module.
>     - `"+tuple"` will be converted to the `tuple` **type**.
> 2. if the string ends with a `"()"`, the resulting object is called with
>     no arguments e.g. `"+my_module.MyClass()"` will be converted to an
>     **instance** of `MyClass` from `my_module`.
> 3. if the string is found as key in a mapping with exactly one key-value
>     pair, then:
>     - if the value is itself a mapping, the single-item mapping is replaced
>         with the result of calling the imported object with the recursively
>         instantiated values as **keyword arguments**
>     - otherwise, the single-item mapping is replaced with the result of
>         calling the imported object with the instantiated value as a single
>         **positional argument**
> 
> ### Parameters
> 
> `data`
>     The data to transform.
> 
> `modules`
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
>     >>> from_dict({"activation": "+torch.nn.Tanh()"})
>     {'activation': Tanh()}
> 
> Note the importance of trailing parentheses:
> 
>     >>> from_dict({"activation": "+torch.nn.Tanh"})
>     {'activation': <class 'torch.nn.modules.activation.Tanh'>}
> 
> Alternatively, point `from_dict` to automatically import
> from `torch.nn`:
> 
>     >>> from_dict({"activation": "+Tanh()"}, modules=[torch.nn])
>     {'activation': Tanh()}
> 
> Use single-item mappings to instantiate classes/call functions with
> arguments. The following syntax will internally import `MyClass` from
> `my_module`, and call it as `MyClass(x=1, y=2)` with explicit keyword
> arguments:
> 
>     >>> from_dict({
>     ...     "activation": "+torch.nn.ReLU()",
>     ...     "model": {
>     ...         "+MyClass": {"x": 1, "y": 2}
>     ...     }
>     ... })
>     {'activation': ReLU(), 'model': MyClass(x=1, y=2)}
> 
> In contrast, the following syntax call the imported objects with a single
> positional argument:
> 
>     >>> from_dict({"+len": [1, 2, 3]})
>     3  # i.e. len([1, 2, 3])
> 
> Mappings with multiple keys are still processed, but are never used to
> instantiate classes/call functions:
> 
>     >>> from_dict({"+len": [1, 2, 3], "+print": "hello"})
>     {<built-in function len>: [1, 2, 3], <built-in function print>: 'hello'}
> 
> `from_dict` also works with arbitrary nesting:
> 
>     >>> from_dict({"model": {"activation": "+torch.nn.Tanh()"}})
>     {'model': {'activation': Tanh()}}
> 
> **Caution**: `from_dict` can lead to side-effects!
> 
>     >>> from_dict({"+print": "hello"})
>     hello
> 
> References are resolved before object instantiation, so all of the following
> will resolve the `"length"` field to `3`:
> 
>     >>> from_dict({"args": [1, 2, 3], "length": {"+len": "!../args"}})
>     3
>     >>> from_dict({"args": [1, 2, 3], "length": {"+len": "!~args"}})
>     3
