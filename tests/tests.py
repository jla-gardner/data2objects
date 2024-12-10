from typing import cast

import helpers
import pytest

from data2objects import from_dict, index_into, process_data_str


def test_basics():
    data = {"a": 1}
    assert from_dict(data) == data, "data should be unchanged"

    data = {"a": "+tuple"}
    assert from_dict(data) == {"a": tuple}, "data should be transformed"


def test_errors():
    # can't find "unknown" in builtins
    data = {"a": "+unknown"}
    with pytest.raises(ImportError, match="unknown"):
        from_dict(data)

    # can't find "ZZ" in helpers
    data = {"+ZZZ": {"x": 1, "y": 2}}
    with pytest.raises(ImportError, match="Could not find"):
        from_dict(data, modules=[helpers])

    # can find CONSTANT, but it isn't callable
    data = {"+helpers.CONSTANT": {"x": 1, "y": 2}}
    with pytest.raises(ValueError, match="is not callable"):
        from_dict(data)


def test_single_positional_arg(capsys):
    data = {"+len": [1, 2, 3]}
    assert from_dict(data) == 3, "len([1, 2, 3]) == 3"

    data = {"+print": "hello"}
    from_dict(data)
    captured = capsys.readouterr()
    assert captured.out == "hello\n"

    # multi-item dictionary: no processing
    data = {"+print": "hello", "+len": [1, 2, 3]}
    assert from_dict(data) == {print: "hello", len: [1, 2, 3]}


def test_custom_import():
    data = {"+helpers.MyClass": {"x": 1, "y": 2}}
    obj = from_dict(data)
    assert isinstance(obj, helpers.MyClass)
    assert obj.x == 1
    assert obj.y == 2

    data = {"+MyClass": {"x": 1, "y": 2}}
    obj = from_dict(data, modules=[helpers])
    assert isinstance(obj, helpers.MyClass)
    assert obj.x == 1
    assert obj.y == 2


def test_index_into():
    data = {"a": {"b": {"c": 1}}}
    assert index_into(data, "a/b/c", []) == 1

    data = {
        "a": {"b": 1},
        "c": 2,
    }
    assert index_into(data, "../c", ["a"]) == 2
    assert index_into(data, ".././c", ["a"]) == 2

    with pytest.raises(KeyError, match="does not exist"):
        index_into(data, "d", [])

    with pytest.raises(KeyError, match="does not exist"):
        index_into(data, "../d", ["a"])

    with pytest.raises(KeyError, match="mal-formed"):
        index_into(data, "../..", ["a"])

    with pytest.raises(ValueError, match="is empty"):
        index_into(data, "", [])

    with pytest.raises(ValueError, match="is empty"):
        from_dict({"a": "!~"})


def test_referencing():
    data = {
        "a": {"b": "!~c"},  # refer to c absolutely
        "c": 2,
    }
    obj = from_dict(data)
    assert obj["a"]["b"] == 2

    data = {
        "a": {"b": "!../c"},  # refer to c relative to a
        "c": 2,
    }
    obj = from_dict(data)
    assert obj["a"]["b"] == 2


def test_process_data_str():
    assert process_data_str("+list") is list
    assert process_data_str("+list()") == list()


def test_import_from_file():
    data = {"+tests.helpers.MyClass": {"x": 1, "y": 2}}
    obj = cast(helpers.MyClass, from_dict(data))
    assert obj.x == 1
    assert obj.y == 2

    # non existing file
    data = {"+non.existing.file.Class": {"x": 1, "y": 2}}
    with pytest.raises(
        ImportError, match="could not find the module or the file"
    ):
        from_dict(data)
