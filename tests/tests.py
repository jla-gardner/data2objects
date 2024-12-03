import helpers
import pytest

from data2objects import from_dict, index_into


def test_basics():
    data = {"a": 1}
    assert from_dict(data) == data, "data should be unchanged"

    data = {"a": "+tuple"}
    assert from_dict(data) == {"a": tuple}, "data should be transformed"


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

    with pytest.raises(KeyError, match="does not exist"):
        index_into(data, "d", [])

    with pytest.raises(KeyError, match="does not exist"):
        index_into(data, "../d", ["a"])

    with pytest.raises(KeyError, match="mal-formed"):
        index_into(data, "../..", ["a"])


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
