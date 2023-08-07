# Fagus
These days most data is converted to and from `json` and `yaml` while it is sent back and forth to and from API's. Often this data is deeply nested. `Fagus` is a Python-library that makes it easier to work with nested dicts and lists. It allows you to traverse and edit these tree-objects with simple function calls that handle the most common errors and exceptions internally. The name fagus is actually the latin name for the genus of beech-trees.

### Code and tests ready, documentation still WORK IN PROGRESS
This documentation is still Work in Progress. I have some more ideas for features, but most of the coding is done. The code is tested as good as possible, but of course there still might be bugs as this library has just been released. Just report them so we get them away ;). Even though this README is not done yet, you should be able to use most of the functions based on the docstrings and some trial and error. Just ask questions [here](https://github.com/treeorg/Fagus/discussions/categories/q-a) if sth is unclear. The documentation will be filled in and completed as soon as possible.

**HAVE FUN!**

## Basic principles

### Introduction -- What it solves
Imagine you want to fetch values from a nested dict as shown below:

```python
>>> a = {"a1": {"b1": {"c1": 2}, "b2": 4}, "a2": {"d1": 6}}
>>> a["a1"]["b1"]["c1"]  # prints 2, so far so good
2
>>> a["a1"]["b3"]["c2"]  # fails, because b3 doesn't exist
Traceback (most recent call last):
 ...
KeyError: 'b3'
```
The problem is that the consecutive square brackets fail if one of the nodes doesn't exist. There are ways around, like writing `a.get("a1", {}).get("b3", {}).get("c2")` or surrounding each of these statements with `try-except`, but both are hard to maintain and verbose. Below you can see how `Fagus` can help to resolve this:
```python
>>> from fagus import Fagus
>>> print(Fagus.get(a, ("a1", "b3", "c2")))  # None, as this key doesn't exist in a
None
```
As you can see, now only one function call is needed to fetch the value from `a`. If one of the keys doesn't exist, a default value is returned. In this case no default value was specified, so `None` is returned.

The whole `Fagus` library is built around these principles. It provides:
* **Simple functions**: replacing tedious code that is hard to maintain and error prone
* **Few exceptions**: Rather than raising a lot of exceptions, `Fagus` does what is most likely the programmer's intention.

### The path-parameter
`Fagus` is built around the concept of a Mapping or dict, where there are keys that are used to refer to values. For lists, the indices are used as keys. In opposition to a simple dict, in `Fagus` the key can consist of multiple values -- one for each layer.
```python
>>> a = [5, {6: ["b", 4, {"c": "v1"}]}, ["e", {"fg": "v2"}]]
>>> Fagus.get(a, (1, 6, 2, "c"))
'v1'
>>> Fagus.get(a, "2 1 fg")
'v2'
```
* **Line 3**: The path-parameter is the tuple in the second argument of the get-function. The first and third element in that tuple are list-indices, whereas the second and fourth element are dict-keys.

* **Line 5**: In many cases, the dict-keys that are traversed are strings. For convenience, it's also possible to provide the whole path-parameter as one string that is split up into the different keys. In the example above, `" "` is used to split the path-string, this can be customized using the [`path_split`](#path_split) `FagusOption`.

### Static and instance usage
All functions in `Fagus` can be used statically, or on a `Fagus`-instance, so the following two calls of `get()` give the same result:
```python
>>> a = [5, {6: ["b", 4, {"c": "v1"}]}, ["e", {"fg": "v2"}]]
>>> Fagus.get(a, "2 0")
'e'
>>> b = Fagus(a)
>>> b.get("2 0")
'e'
```
The first call of `get()` in line 3 is static, as we have seen before. No `Fagus` instance is required, the object `a` is just passed as the first parameter. In line 5, `b` is created as a `Fagus`-instance -- calling `get()` on `b` also yields `e`.

While it's not necessary to instantiate `Fagus`, there are some neat shortcuts that are only available to `Fagus`-instances:
```python
>>> a = Fagus()
>>> a["x y z"] = 6  # a = {"x": {"y": {"z": 6}}}
>>> a.x  # returns the whole subnode at a["x"]
{'y': {'z': 6}}
>>> del a[("x", "y", "z")]  # Delete the z-subnode in a["x y z"]
>>> a()
{'x': {'y': {}}}
```
* **Square bracket notation**: On `Fagus`-instances, the square-bracket notation can be used for easier access of data if no further customization is needed. Line 3 is equivalent to `a.set(6, "x y z")`. It can be used for getting, setting and deleting items (line 6).
* **Dot notation**: The dot-notation is activated for setting, getting and deleting items as well (line 4). It can be used to access `str`-keys in `dict`s and `list`-indices, the index must then be preceded with an underscore due to Python naming limitations (`a._4`). This can be further customized using [`path_split`](#path_split)

`Fagus` is a wrapper-class around a tree of `dict`- or `list`-objects. To get back the root-object inside the instance, use `()` to call the object -- this is shown in line 7.

### Fagus options
There are several parameters used across many functions in `Fagus` steering the behaviour of that function. Often, similar behaviour is intended across a whole application or parts of it, and this is where options come in handy allowing to only specify these parameters once.

One example of a `Fagus`-option is [`default`](#default). This option contains the value that is returned e.g. in `get()` if a [`path`](#the-path-parameter) doesn't exist, see [Introduction](#introduction----what-it-solves), code block two for an example. 






**The four levels of `Fagus`-options**:
1. **Argument**: The highest level - if an option is specified directly as an argument to a function, that value takes precedence over all other levels.
2. **Instance**: If an option is set for an instance, it will apply to all function calls at that instance where level one has not been specified.
3. **Class**: If an option is set at class level (i.e. `Fagus.option`), it applies to all function calls and all instances where level one and two of that option aren't defined. Options at this level apply for the whole file `Fagus` has been imported in.
4. **Default**: If no other level is specified, the hardcoded default for that option is used.

Below is an example of how the different levels take precedence over one another:
```python
>>> a = Fagus({"a": 1})
>>> print(a.get("b"))  # b does not exist in a - default is None by default
None
>>> Fagus.default = "class"  # Overriding default at class level
>>> a.get("b")  # now 'class' is returned, as None was overridden
'class'
>>> a.default = 'instance'  # setting the default option at instance level
>>> a.get("b")  # for a default is set to 'instance' -- return 'instance'
'instance'
>>> b = Fagus({"a": 1})
>>> b.get("b")  # for b, line 7 doesn't apply -- line 5 still applies
'class'
>>> del Fagus.default  # deleting an option resets it to its default
>>> print(b.get("b"))  # for default, the default is None
None
>>> a.get("b", default='arg')  # passing an option as a parameter always wins
'arg'
```
All `Fagus`-options at level two can be set in the constructor of `Fagus`, so they don't have to be set one by one like in line 8. You can also use `options()` on an instance or on the `Fagus`-class to set several options in one line, or get all the options that apply to an instance.

Some `Fagus`-functions return child-`Fagus`-objects in their result. These child-objects inherit the options at level two from their parent.

The remaining part of this section explains the options one by one.

#### default
* **Default**: `None`
* **Type**: `Any`

This value is returned if the requested [`path`](#the-path-parameter) does not exist. Example in [Introduction](#introduction----what-it-solves), code block two.

#### default_node_type
* **Default**: `"d"`
* **Type**: `str`
* **Allowed values**: `"d"` and `"l"`

Can be either `"d"` for `dict` or `"l"` for `list`. A new node of this type is created if it's not specified clearly what other type that node shall have. It is used e.g. when Fagus is instanciated with an empty constructor:
```python
>>> Fagus.default_node_type = "l"
>>> a = Fagus()
>>> a()  # the root node of a is an empty list as this was set in line 2
[]
>>> del Fagus.default_node_type
>>> b = Fagus()
>>> b()  # the root node of b is a dict (default for default_node_type)
{}
```

#### if_
* **Default**: `_None`, meaning that the value is not checked
* **Type**: Any

This option can be used to verify values before they're inserted into the `Fagus`-object. Generating configuration-files, default values can often be omitted whereas special settings shall be included, `if_` can be used to do this without an extra if-statement.
```python
>>> a = Fagus(if_=True)  # the only allowed value for set is now True
>>> a.v1 = True
>>> a()  # v1 was set, because it was True (as requested in line 1)
{'v1': True}
>>> a.v2 = None
>>> a()  # note that v2 has not been set as it was not True
{'v1': True}
>>> a.set(6, "v2", if_=(4, 5, 6))  # 6 was set as it was in (4, 5, 6)
{'v1': True, 'v2': 6}
>>> a.set("", "v3", if_=bool)  # v3 is not set because bool("") is False
{'v1': True, 'v2': 6}
```
Possible ways to specify `if_`:
* **Single value**: This is shown in line 1 -- the only values that can now be set is `True`, anything else is not accepted.
* **List of values**: You can also specify any `Iterable` (e.g. a `list`) with multiple values -- the values that can be set must be one of the values in the `list` (line 8).
* **Callable**: You can also pass a callable object or a function (lambda) -- the result of that call determines whether the value is set (line 10).

#### iter_fill
* **Default**: `_None`, meaning that `iter_fill` is inactive
* **Type**: Any

This option is used to get a constant number of items in the iterator while iterating over a `Fagus`-object, see [here](#iterating-over-nested-objects) for more about iteration in `Fagus`. The example below shows what happens by default when iterating over a `Fagus`-object where the leaf-nodes are at different depths:
```python
>>> a = list(Fagus.iter({"a": {"b": 2}, "c": 4}, 1))
>>> a
[('a', 'b', 2), ('c', 4)]
>>> for x, y, z in a:
...     print(x, y, z)
Traceback (most recent call last):
...
ValueError: not enough values to unpack (expected 3, got 2)
>>> a = list(Fagus.iter({"a": {"b": 2}, "c": 4}, 1, iter_fill=None))
>>> a
[('a', 'b', 2), ('c', 4, None)]
>>> for x, y, z in a:
...     print(x, y, z)
a b 2
c 4 None
```
In line 3, we see that the first tuple has three items, and the second only two. When this is run in a loop that always expects three values to unpack, it fails (line 4-8). That problem is solved in line 9 by using `iter_fill`, which fills up the shorter tuples with the value that was specified for `iter_fill`, here `None`. With that in place, the loop in line 12-15 runs through without raising an error. Note that `max_depth` has to be specified for `Fagus` to know how many items to fill up to.

#### iter_nodes
* **Default**: `False`
* **Type**: `bool`

This option is used to get references to the traversed nodes while iterating on a `Fagus`-object, see [here](#iterating-over-nested-objects) for more about iteration in `Fagus`. Below is an example of what this means:
```python
>>> list(Fagus.iter({"a": {"b": 2}, "c": 4}, 1))
[('a', 'b', 2), ('c', 4)]
>>> list(Fagus.iter({"a": {"b": 2}, "c": 4}, iter_nodes=True))
[({'a': {'b': 2}, 'c': 4}, 'a', {'b': 2}, 'b', 2), ({'a': {'b': 2}, 'c': 4}, 'c', 4)]
```
As you can see, the node itself is included as the first element in both tuples. In the first tuple, we also find the subnode `{"b": 2}` as the third element. In line 2, the tuples are filled after this scheme: `key1, key2, key3, ..., value`. In line 4, we additionally get the nodes, so it is `root-node, key1, node, key2, node2, key3, ..., value`.

Sometimes in loops it can be helpful to actually have access to the whole node containing other relevant information. This can be especially useful combined with [`skip()`](#skipping-nodes-in-iteration).

#### list_insert
* **Default**: `INF` (infinity, defined as `sys.maxsize`, the max value of an `int` in Python)
* **Type**: `int`

By default, lists are traversed in Fagus when new items are inserted. New lists are only created if necessary. Consider the following example: 

```python
>>> a = Fagus([0, [3, 4, [5, 6], 2]])
>>> a.set("insert_1", (1, 2))
[0, [3, 4, 'insert_1', 2]]
```

The list `[5, 6]` is overridden with the new value `"insert_1"`. In some cases it is desirable to insert a new value into one of the lists rather than just overwriting the existing value. This is where `list_insert` comes into the picture.

```python
>>> a = Fagus([0, [3, 4, [5, 6], 2]], default_node_type="l")
>>> a.set("insert_2", (1, 2), list_insert=1)
[0, [3, 4, 'insert_2', [5, 6], 2]]
>>> a.set("insert_3", (1, 2), list_insert=0)
[0, ['insert_3'], [3, 4, 'insert_2', [5, 6], 2]]
```

The parameter `list_insert` defines at which depth a new element should be inserted into the list. In line 2, `list_insert` is set to one, so `"insert_2"` is inserted in position two in the list at index 1 in the `Fagus`-object. In line 4, the new element is inserted in the base-list at depth zero in the `Fagus`-object. As another index is defined in `path` (2), another list is created before `"insert_3` is inserted.

```python
>>> a = Fagus({2: {1: 4, 3: [4, 6]}, "a": "b"})
>>> a.set("insert_4", (2, 3, 1), list_insert=1)
{2: {1: 4, 3: [4, 'insert_4', 6]}, 'a': 'b'}
```

In this last example, there is no list to be traversed at depth one. In that case, the insertion of `insert_4` is performed in the first list that is traversed above the indicated `list_insert`-depth (here one), which is at depth two.

#### node_types
* **Default**: `""`
* **Type**: `str`
* **Allowed values**: Any string only containing the characters `"d"`, `"l"` and `" "`

This parameter is used to precisely specify which types the new nodes to create when inserting a value at `path` shall have. They are defined in three possible ways: `"l"` for `list`, `"d"` for `dict` or `" "` for "don't care". Don't care means that if the node exists, its type will be preserved if possible, however if a new node needs to be created because it doesn't exist, [`default_node_type`](#default-node-type) will be used if possible. The examples below will make it more clear how this works.

**Example one: creating new nodes inside an empty object**:
```python
>>> a = Fagus()
>>> a.set(False, ("a", 0, 0), node_types="dl")
{'a': {0: [False]}}
```

The base node, in the case above a `dict`, can't be changed, so `node_types` only affects the nodes that resign within the base node. Therefore, `node_keys` is only defined for the second until last key in `path`. For the second key in `path`, here 0, it is defined in `node_types` that it should be a `dict`, therefore a `dict` is created. In that `dict`, a `list` is inserted at key 0 as the second letter in `node_types` is `"l"`, and finally `False` is inserted into that `list.

**Example two: clearly defined where to put lists and dicts at each level**
```python
>>> a = Fagus({3: [[4, {5: "c"}], {"a": "q"}]})
>>> a.set(True, (3, 0, 7, 4), node_types="ldl")
{3: [{7: [True]}, {'a': 'q'}]}
```

In this case, there already are nodes at the base of the position `path` is pointing to. The first key in `path`, 3, is traversed. For the second key in `path`, here 0, it is defined in `node_types` that it should be a `list` (`"l"`), and in this case it actually is a list. The third key in `path` is 7, and in `node_types` it is defined that there should be a `dict` at this level. Therefore, the `list` `[4, {5: "c"}]` is overwritten with a new `dict` with the key 7. The forth and last element in `path` is 4, and in `node_types` it is defined that this node shall be a `list` again. The value `True` is then placed inside that `list`.

**Example three: "don't care" and other special cases**:
```python
>>> a = Fagus(default_node_type="l")
>>> a.set(True, (3, "a", "6"))
[{'a': [True]}]
>>> a.set(None, (1, 5), "ddddddddd")
[{'a': [True]}, {5: None}]
>>> a.set(False, (1, 1, 1, 1), node_types=" d")
[{'a': [True]}, {5: None, 1: {1: [False]}}]
```
The first example in line two shows the basic case, this is what happens if `node_types` is has not been defined. If `node_types` is not defined, all the new nodes that are to be created are interpreted as "don't care", which means that if possible, new nodes of the type `default_node_type` are created. Here, `default_node_type` is `"l"` (`list`). There is no meaningful easy way to create an `int`-`list`-index from `"a"`, therefore a `dict` is inserted at `"a"`. However, it is possible to create a list index from `"6"` by using `str()`, therefore a `list` is created at key `"a"`, in which `True` finally is inserted.

The second example in line four shows what happens if `node_types` is defined for more than the length of `path`. It's actually no problem to do that, the remaining part of `node_types` is just ignored. The third example in line six shows what happens if `node_types` only is partly defined, in this case it is only defined to be "don't care" for the second key in `path` and `"d"` for the third key in `path`, but not for the last element. For all the keys in `path` where `node_types` is undefined, it is treated as `"don't care"` when new nodes are created.

#### path_split
* **Default**: `" "`
* **Type**: `str`

The keys needed to traverse a `Fagus`-object for getting or setting a value are passed as a `tuple` or `list` (line 2). `path_split` allows to alternatively specify all the keys in a single string, split by `path_split` (line 4). As shown in line 4, list indices can be specified in the path-string, they are automatically converted back to `int`.

```python
>>> a = Fagus({"a": {"b": [True, "q"]}})
>>> a[("a", "b", 0)]
True
>>> a["a b 0"]
True
```

By default, `path_split` is a single space `" "`, but any other string can be used as a split character. If path string is set to `"_"`, the dot-notation can be used to get or set a node deeply inside a `Fagus`-object.

```python
>>> a = Fagus(path_split="_")
>>> a.a_c_1 = 4  # {"a": {"c": {"1": 4}}}
>>> a = Fagus(path_split="_", default_node_type="l")
>>> a._0_2 = 6  # [[6]], note that the str after . is prefixed with a _ for a list index
>>> a = Fagus(path_split="__")
>>> a.example_index__another_index = "q"  # {"example_index": {"another_index": "q"}}
```


### Iterating over nested objects

#### Skipping nodes in iteration.
