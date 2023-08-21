# Fagus
These days most data is converted to and from `json` and `yaml` while it is sent back and forth to and from API's. Often this data is deeply nested. `Fagus` is a Python-library that makes it easier to work with nested dicts and lists. It allows you to traverse and edit these tree-objects with simple function calls that handle the most common errors and exceptions internally. The name fagus is actually the latin name for the genus of beech-trees.

#### Code and tests ready, documentation still WORK IN PROGRESS
This documentation is still Work in Progress. I have some more ideas for features, but most of the coding is done. The code is tested as good as possible, but of course there still might be bugs as this library has just been released. Just report them so we get them away ;). Even though this README is not done yet, you should be able to use most of the functions based on the docstrings and some trial and error. Just ask questions [here](https://github.com/treeorg/Fagus/discussions/categories/q-a) if sth is unclear. The documentation will be filled in and completed as soon as possible.

**HAVE FUN!**

## Table of contents
<!--TOC-->

- [Table of contents](#table-of-contents)
- [Basic principles](#basic-principles)
  - [Introduction -- What it solves](#introduction----what-it-solves)
  - [The path-parameter](#the-path-parameter)
  - [Static and instance usage](#static-and-instance-usage)
  - [Fagus options](#fagus-options)
- [Modifying the tree](#modifying-the-tree)
  - [Basic principles for modifying the tree](#basic-principles-for-modifying-the-tree)
  - [set() -- adding and overwriting elements](#set----adding-and-overwriting-elements)
  - [append() -- adding a new element to a `list`](#append----adding-a-new-element-to-a-list)
  - [extend() -- extending a `list` with multiple elements](#extend----extending-a-list-with-multiple-elements)
  - [insert() -- insert an element at a given index in a `list`](#insert----insert-an-element-at-a-given-index-in-a-list)
  - [add() -- adding a new element to a `set`](#add----adding-a-new-element-to-a-set)
  - [update() -- update multiple elements in a `set` or `dict`](#update----update-multiple-elements-in-a-set-or-dict)
  - [remove(), delete() and pop()](#remove-delete-and-pop)
  - [serialize() -- ensure that a tree is json- or yaml-serializable](#serialize----ensure-that-a-tree-is-json--or-yaml-serializable)
  - [mod() -- modifying elements](#mod----modifying-elements)
- [Iterating over nested objects](#iterating-over-nested-objects)
  - [Skipping nodes in iteration.](#skipping-nodes-in-iteration)
- [Filtering nested objects](#filtering-nested-objects)

<!--TOC-->

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
>>> Fagus.get(a, (1, 6, -1, "c"))
'v1'
>>> Fagus.get(a, "2 -1 fg")
'v2'
```
* **Line 3**: The path-parameter is the tuple in the second argument of the get-function. The first and third element in that tuple are list-indices, whereas the second and fourth element are dict-keys.

* **Line 5**: In many cases, the dict-keys that are traversed are strings. For convenience, it's also possible to provide the whole path-parameter as one string that is split up into the different keys. In the example above, `" "` is used to split the path-string, this can be customized using the [`path_split`](#path_split) [`FagusOption`](#fagus-options).

### Static and instance usage
All functions in `Fagus` can be used statically, or on a `Fagus`-instance, so the following two calls of [`get()`](#the-path-parameter) give the same result:
```python
>>> a = [5, {6: ["b", 4, {"c": "v1"}]}, ["e", {"fg": "v2"}]]
>>> Fagus.get(a, "2 0")
'e'
>>> b = Fagus(a)
>>> b.get("2 0")
'e'
```
The first call of [`get()`](#the-path-parameter) in line 3 is static, as we have seen before. No `Fagus` instance is required, the object `a` is just passed as the first parameter. In line 5, `b` is created as a `Fagus`-instance -- calling [`get()`](#the-path-parameter) on `b` also yields `e`.

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
* **Dot notation**: The dot-notation is activated for setting, getting and deleting items as well (line 4). It can be used to access `str`-keys in `dict`s and `list`-indices, the index must then be preceded with an underscore due to Python naming limitations (`a._4`). This can be further customized using the [`path_split`](#path_split) [`FagusOption`](#fagus-options).

`Fagus` is a wrapper-class around a tree of `dict`- or `list`-nodes. To get back the root-object inside the instance, use `()` to call the object -- this is shown in line 7. Alternatively you can get the root-object through `.root`.


### Fagus options
There are several parameters used across many functions in `Fagus` steering the behaviour of that function. Often, similar behaviour is intended across a whole application or parts of it, and this is where options come in handy allowing to only specify these parameters once instead of each time a function is called.

One example of a `Fagus`-option is [`default`](#default). This option contains the value that is returned e.g. in [`get()`](#the-path-parameter) if a [`path`](#the-path-parameter) doesn't exist, see [Introduction](#introduction----what-it-solves), code block two for an example of [`default`](#default).

There are four levels at which an option can be set, where the higher levels take precedence over the lower levels:

**The four levels of `Fagus`-options**:
1. **Default**: If no other level is specified, the hardcoded default for that option is used.
2. **Class**: If an option is set at class level (i.e. `Fagus.option`), it applies to all function calls and all instances where level one and two of that option aren't defined. Options at this level apply for the whole file `Fagus` has been imported in.
3. **Instance**: If an option is set for an instance, it will apply to all function calls at that instance where the option wasn't overriden by an argument.
4. **Argument**: The highest level - if an option is specified directly as an argument to a function, that value takes precedence over all other levels.

Below is an example of how the different levels take precedence over one another:
```python
>>> a = Fagus({"a": 1})
>>> print(a.get("b"))  # b does not exist in a - default is None by default
None
>>> Fagus.default = "class"  # Overriding default at class level (level 2)
>>> a.get("b")  # now 'class' is returned, as None was overridden
'class'
>>> a.default = 'instance'  # setting the default option at instance level (level 3)
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

All `Fagus`-options at level three can be set in the constructor of `Fagus`, so they don't have to be set one by one like in line 8. You can also use `options()` on an instance or on the `Fagus`-class to set several options in one line, or get all the options that apply to an instance.

Some `Fagus`-functions return child-`Fagus`-objects in their result. These child-objects inherit the options at level three from their parent.

The remaining part of this section explains the `FagusOption`s one by one.

#### default
* **Default**: `None`
* **Type**: `Any`

This value is returned if the requested [`path`](#the-path-parameter) does not exist, for example in [`get()`](#the-path-parameter).

```python
>>> from fagus import Fagus
>>> a = {"b": 3}
>>> Fagus.get(a, "b", default=8)  # return 3, as "b" exists
3
>>> Fagus.get(a, "q", default=8)  # return default 8, as "q" does not exist
8
>>> print(Fagus.get(a, "q"))  # "q" does not exist -- return None being default if it hasn't been specified as arg
None
```

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
>>> c = Fagus([])
>>> c()  # the root node of c is now also a list
[]
```

More information about how `default_node_type` is used when new nodes need to be generated can be found in [Basic principles for modifying the tree](#basic-principles-for-modifying-the-tree) and the documentation of the `FagusOption` [`node_types`](#node_types).


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

By default, `list`-nodes are traversed in Fagus when new items are inserted. New `list`-nodes are only created if necessary. Consider the following example:

```python
>>> a = Fagus([0, [3, 4, [5, 6], 2]])
>>> a.set("insert_1", (1, 2))
[0, [3, 4, 'insert_1', 2]]
```

The list `[5, 6]` is overridden with the new value `"insert_1"`. In some cases it is desirable to insert a new value into one of the lists rather than just overwriting the existing value. This is where `list_insert` comes into the picture. For some background of how `list`-indices work in `Fagus`, you can check out [this section](#correctly-handling-list-indices).

```python
>>> a = Fagus([0, [3, 4, [5, 6], 2]], default_node_type="l")
>>> a.set("insert_2", (1, 2), list_insert=1)  # [5, 6] was not overridden here, insert_2 is inserted before
[0, [3, 4, 'insert_2', [5, 6], 2]]
>>> a.set("insert_3", (1, 2), list_insert=0)  # here, insert_3 is inserted at the base level 0, again without overriding
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

This parameter is used to precisely specify which types the new nodes to create when inserting a value at [`path`](#the-path-parameter) shall have. There are defined in three possible ways: `"l"` for `list`, `"d"` for `dict` or `" "` for "don't care". Don't care means that if the node exists, its type will be preserved if possible, however if a new node needs to be created because it doesn't exist, [`default_node_type`](#default_node_type) will be used if possible. The examples below will make it more clear how this works. For an overview, also check the [basic principles for modifying the tree](#basic-principles-for-modifying-the-tree).

**Example one: creating new nodes inside an empty object**:
```python
>>> a = Fagus()
>>> a()  # a is a dict, as default_node_type by default generates a dict
{}
>>> a.set(False, ("a", 0, 0), node_types="dl")
{'a': {0: [False]}}
```

The root node, in the case above a `dict`, can't be changed, so `node_types` only affects the nodes that resign within the root node. Therefore, `node_types` is only defined for the second until last key in [`path`](#the-path-parameter). For the second key in `path`, here 0, it is defined in `node_types` that it should be a `dict`, therefore a `dict` is created. In that `dict`, a `list` is inserted at key 0 as the second letter in `node_types` is `"l"`, and finally `False` is inserted into that `list.

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
The first example in line two shows what happens if `node_types` is has not been defined. In that case, all the new nodes that are to be created are interpreted as "don't care", which means that if possible, new nodes of the type `default_node_type` are created. Here, `default_node_type` is `"l"` (`list`). There is no meaningful easy way to create an `int`-`list`-index from `"a"`, therefore a `dict` is inserted at `"a"`. However, it is possible to create a list index from `"6"` by using `str()`, therefore a `list` is created at key `"a"`, in which `True` finally is inserted.

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
## Modifying the tree
`Fagus` does not only allow to easily retrieve elements deeply inside a tree of nested `dict`- and `list`-nodes using [`get()`](#the-path-parameter). The tree can also be modified using the different functions shown below. Make sure to read [set()](#set----adding-and-overwriting-elements) first as its basic principles apply to all the other modifying functions.

### Basic principles for modifying the tree
The following subsections show the logic behind the creation of new nodes in `Fagus`. It is implemented in such a way that the tree is always modified as little as possible to perform the requested change.

#### Correctly handling list indices
As demonstrated in the examples for the [`path`](#the-path-parameter)-parameter, `list` indices can be positive and negative `int`-nodes to access specific values in the list:

```python
>>> a = Fagus([[[0, 1], 2], [3, 4, [5, [6, 7]], 8]])  # some nested lists to demonstrate indices
>>> a["-1 2 1 1"]  # positive and negative indices can be used to get a value
7
>>> a["0 -1"] = "two"  # the value at index -1 is replaced with the new string
>>> a()
[[[0, 1], 'two'], [3, 4, [5, [6, 7]], 8]]
```

When lists are modified, in many cases it might be desirable to append or prepend a value to the `list` instead of overriding it as shown above. This can be done as shown below:

```python
>>> a.set(9, (1, 10000))  # 9 is appended as 10000 is bigger than len([3, 4, [5, [6, 7]], 8])
[[[0, 1], 'two'], [3, 4, [5, [6, 7]], 8, 9]]
>>> a.set(2.5, "1 -6")  # 2.5 is prepended before 3 as -6 is smaller than -len([3, 4, [5, [6, 7]], 8, 9])
[[[0, 1], 'two'], [2.5, 3, 4, [5, [6, 7]], 8, 9]]
```
This shows how elements easily can be appended and prepended just by specifying an index which is bigger than the length of the list to append, or smaller than minus the length of the list to prepend. In order to make sure that a value is always appended / prepended without knowing the length of the list, `INF` can be imported from the `fagus`-module, it is just a reference to `sys.maxsize`. The `FagusOption` [`list_insert`](#list_insert) can be used to insert a new value at an index in the middle of the `list`.

#### Create the correct type of node
`Fagus` is built around the concept of values being assigned to keys to build nested trees of `dict`- and `list`-nodes. The only supported operation in `set`-nodes is checking whether it `contains` a certain value, therefore `set`-nodes cannot be traversed by [`get()`](#the-path-parameter) and are thus treated as leaf-nodes. Consequently, the only available nodes to create in the tree are `dict` `"d"` and `list` `"l"`.

The `FagusOption` [`node_types`](#node_types) can be used to clearly specify which types the nodes at each level of the tree should have, see [`node_types`](#node_types) example one. If `node_types` is not specified clearly or set to `" "` (don't care), [`default_node_type`](#default_node_type) determines which type of node will be created:

```python
>>> a = Fagus()
>>> a.set(True, "0 0 0", default_node_type="l")  # only lists are created, as default_node_type="l"
{'0': [[True]]}
>>> a.clear()
{}
>>> a.set(True, "0 a 0", default_node_type="l")  # a dict is created at level 1 --> can't convert "a" to a list-index
{'0': {'a': [True]}}
>>> a = Fagus()
>>> a.set(True, "0 0 0")  # only create dicts, as default_node_type is "d" by default
{'0': {'0': {'0': True}}}
```

From the example above, we can see the following two rules on how new nodes are created:
1. `list` nodes are created when `default_node_type` is `"l"` and the key can be converted to an `int` --> create `list` for keys like `8` or `"-10"`
2. `dict` nodes are always created when `default_node_type` is `d`, even if the key could be converted to an `int` --> create `dict` also for keys like `8` or `"-10"`

But what happens if there already are existing nodes?
```python
>>> a = Fagus([{"a": [True]}])
>>> a.set(False, (0, "a", 1))  # the new value False is appended to the list
[{'a': [True, False]}]
>>> a.set(7, "0 a b")  # could not convert "b" to list index, so [True, False] was replaced with {"b": 7}
[{'a': {'b': 7}}]
>>> a.set(3, "0 a 2", default_node_type="l")  # did not convert {"b": 7} to list --> if possible always try to keep node
[{'a': {'b': 7, '2': 3}}]
```

This shows that as far as possible, `Fagus` will keep the existing node and not change it like in line 6. An existing node is only overridden and changed if it is not possible to convert the provided key to a list-index.

It is possible to manually override this behaviour by clearly specifying if each node should be a `dict` `"d"` or a `list` `"l"`, check out the section about [`node_types`](#node_types) for examples on this.

#### Ensure that the required node can be modified
In a nested structure of `dict`- and `list`-nodes, there can also be unmodifyable `list`-nodes called `tuple`. As values can't be changed in a `tuple`, it has to be converted into a `list`. The following example shows how this is done in case of nested `tuple`-nodes:

```python
>>> a = Fagus((((1, 0), 2), [3, 4, (5, (6, 7)), 8]))
>>> a.set("seven", "1 2 1 1")  # replacing the value 7 with the string "seven"
(((1, 0), 2), [3, 4, [5, [6, 'seven']], 8])
```

In order to replace the 7 with `"seven"` in the `tuple` `(6, 7)`, it has to be converted into a modifyable `list` first. `(6, 7)` however resides in another `tuple` `(5, (6, 7))`, so that outer `tuple` also has to be converted into a `list`. As `(5, (6, 7))` already lies in a `list`, it can be  replaced with `[5, [6, "seven"]]`. The key point is that `tuple`-nodes are converted to `list`-nodes as deeply as necessary. The outermost `tuple` containing the whole tree `(((1, 0), 2), [3, 4, (5, (6, 7)), 8])` is not touched, and thus remains a `tuple`

### set() -- adding and overwriting elements
The `set()` function can be used to add or replace a value anywhere in the tree. This function is also used internally in `Fagus` whereever new nodes need to be created. See [Basic principles for modifying the tree](#basic-principles-for-modifying-the-tree) and [`node_types`](#node_types) for examples of how `set()` can be fine-tuned. In case no further fine-tuning is used, the `set()`-operation can also be done as shown below:

```python
>>> a = Fagus([], path_split="_")
>>> a.set("hello", "0_good_morning")
[{'good': {'morning': 'hello'}}]
>>> a._1_ciao = "byebye"  # the dot-notation for set() is available when path_split is set to "_" or "__"
>>> a()  # note that the first index 1 above was prefixed with _, as variable names can't start with a digit in Python
[{'good': {'morning': 'hello'}}, {'ciao': 'byebye'}]
>>> a["0_good_evening"] = "night"  # the []-notation is always available for set(), a[(0, "evening")] would do the same
>>> a()
[{'good': {'morning': 'hello', 'evening': 'night'}}, {'ciao': 'byebye'}]
```

### append() -- adding a new element to a `list`
There might be cases where it is desirable to collect all elements of a certain type in a `list`. This can be done in only one step using `append()`:

```python
>>> plants = Fagus()
>>> plants.append("daffodil", "flowers")  # a new list is created in the node flowers
{'flowers': ['daffodil']}
>>> plants.append("pine", "trees softwood")  # another list is created in the category trees softwood
{'flowers': ['daffodil'], 'trees': {'softwood': ['pine']}}
>>> plants.append("rose", "flowers")  # rose is added to the existing flowers list
{'flowers': ['daffodil', 'rose'], 'trees': {'softwood': ['pine']}}
>>> plants.append("oak", "trees hardwood")  # a new list is created for hardwood trees
{'flowers': ['daffodil', 'rose'], 'trees': {'softwood': ['pine'], 'hardwood': ['oak']}}
>>> plants.append("beech", "trees hardwood")  # beech is appended to the hardwood trees list
{'flowers': ['daffodil', 'rose'], 'trees': {'softwood': ['pine'], 'hardwood': ['oak', 'beech']}}
```
As you can see, this function makes it easy to combine elements belonging to the same category in a `list` inside the tree. The pratical thing here is that it isn't necessary to worry about creating the `list` initially -- if there already is a `list`, the new element is appended and if there is no `list`, a new one is created.

```python
>>> plants.set("pine", ("trees", "softwood"))  # removing pine from list to put it as a single element (for next step)
{'flowers': ['daffodil', 'rose'], 'trees': {'softwood': 'pine', 'hardwood': ['oak', 'beech']}}
>>> plants.append("fir", ("trees", "softwood"))  # pine is in this position already -> put pine in list, then append fir
{'flowers': ['daffodil', 'rose'], 'trees': {'softwood': ['pine', 'fir'], 'hardwood': ['oak', 'beech']}}
>>> plants.append("forest", "trees")  # node trees already present at path -> convert node to list -> append element
{'flowers': ['daffodil', 'rose'], 'trees': ['softwood', 'hardwood', 'forest']}
>>> plants = Fagus({"flowers": {"rose", "daffodil", "tulip"}})  # preparing the next step - flowers are now in a set
>>> # below another type of node is already at path (here a set) -> convert it to a list and then append the element
>>> plants.append("sunflower", "flowers")["flowers"].sort()  # sort list of flowers for doctest, irrelevant for example
>>> plants()  # as you can see, {"rose", "daffodil", "tulip"} was converted to a list, then sunflower was added
{'flowers': ['daffodil', 'rose', 'sunflower', 'tulip']}
```

The examples above show that `append()` is agile and makes the best out of any situation in the tree where it is called. If there is a single element already present at the node, that element is put in a `list` before the new element is added. If there already is another type of node or another `Collection` at the requested `path`, convert that node into a `list` and then append the new element.

```python
>>> plants.set("lily", "flowers 4")  # set() with an index bigger than the length of the list can also be used to append
{'flowers': ['daffodil', 'rose', 'sunflower', 'tulip', 'lily']}
```
The example above shows that `set()` can also be used to append an element to a `list`. However, note that `set()` in this case won't create a new list if the node doesn't exist yet. It won't convert another node already present at `path` into a `list` neither.

### extend() -- extending a `list` with multiple elements
The `extend()` function works very similar to [`append()`](#append----adding-a-new-element-to-a-list), the main difference here is that instead of appending one additional element, the list is extended with a collection of elements.

```python
>>> plants.extend(("lavender", "daisy", "orchid"), "flowers")  # extend() works like append(), just adding more elements
{'flowers': ['daffodil', 'rose', 'sunflower', 'tulip', 'lily', 'lavender', 'daisy', 'orchid']}
```

For further reading about when and how new `list`-nodes are created, refer to the documentation of [`append()`](#append----adding-a-new-element-to-a-list) as `extend()` works similar except from the fact that several new elements are added instead of one.

### insert() -- insert an element at a given index in a `list`
The `insert()` function works similar to [`append()`](#append----adding-a-new-element-to-a-list), the main difference is just that instead of appending the new element to the end of the `list`, it can be inserted at any position. For an overview of how and when new `list`-nodes are created before insertion, check out [`append()`](#append----adding-a-new-element-to-a-list).

```python
>>> plants = Fagus({'flowers': ['daffodil', 'rose', 'sunflower']})
>>> plants.insert(1, "tulip", "flowers")  # index parameter comes first, so the order if args is like in list().insert()
{'flowers': ['daffodil', 'tulip', 'rose', 'sunflower']}
```

The normal indexation of `list`-nodes in `Fagus` only allows appending or prepending elements if it is necessary to do so anywhere in [`path`](#the-path-parameter), this is documented [`here`](#correctly-handling-list-indices). Check out the [`list_insert`](#list_insert) `FagusOption` for examples on how to insert new nodes at any index in the list anywhere in `path`.

### add() -- adding a new element to a `set`
The `add()` function works similar to [`append()`](#append----adding-a-new-element-to-a-list), the main difference is just that instead of creating and appending to `list`-nodes, `set`-nodes are used. For detailed examples of the rules when and how new `set`-nodes are created by this function, check out [`append()`](#append----adding-a-new-element-to-a-list) just replacing occurrences of `list` with `set`.

```python
>>> from tests.test_fagus import sorted_set  # function needed for doctests to work with sets -> print the set sorted
>>> sorted_set(plants.add("daisy", "flowers"))  # list is converted into a set, and then "daisy" is added to that set
{'flowers': {'daffodil', 'daisy', 'rose', 'sunflower', 'tulip'}}
>>> sorted_set(plants.add("oak", "trees"))  # node does not exist yet - create new empty set and add the new value to it
{'flowers': {'daffodil', 'daisy', 'rose', 'sunflower', 'tulip'}, 'trees': {'oak'}}
```

### update() -- update multiple elements in a `set` or `dict`
This function works similar to [`extend()`](#extend----extending-a-list-with-multiple-elements) explained above, however the difference here is that the new elements now are added to a `set` or `dict`. As the function has the same name for `set` and `dict`-nodes, it has to determine what kind of node to create. Consider the following examples:

```python
>>> plants = Fagus()  # sorted_set() is used to always print sets deterministic, this is needed internally for doctests
>>> sorted_set(plants.update(dict(softwood="pine", hardwood="oak"), "trees"))  # creating and updating dict
{'trees': {'softwood': 'pine', 'hardwood': 'oak'}}
>>> sorted_set(plants.update(("tulip", "daisy", "daffodil"), "flowers"))  # create set from tuple
{'trees': {'softwood': 'pine', 'hardwood': 'oak'}, 'flowers': {'daffodil', 'daisy', 'tulip'}}
>>> plants.clear("flowers")  # emptying this set to keep the example easily readable
{'trees': {'softwood': 'pine', 'hardwood': 'oak'}, 'flowers': set()}
>>> sorted_set(plants.update({"garden flowers": "sunflower", "flower trees": "apple tree"}, "flowers"))  # comment below
{'trees': {'softwood': 'pine', 'hardwood': 'oak'}, 'flowers': {'flower trees', 'garden flowers'}}
>>> # as you can see, even though a dict was sent in as a parameter, the flowers node stayed a set, so only "flower
>>> # trees" and "garden flowers" were added, but not "apple tree" and "sunflower"
```

The examples above illustrate first two of the principles `update()` operates after:
1. If there already is a `dict`- or `set` object at [`path`](#the-path-parameter), keep that node if possible.
2. If there already exists a `set`, and a `dict` is passed to `update()`, the `set` is updated with the keys from the dict only (line 8).

```python
>>> sorted_set(plants.set({"fruit trees": ["apple tree", "lemon tree"]}, "trees"))  # prepare the next example
{'trees': {'fruit trees': ['apple tree', 'lemon tree']}, 'flowers': {'flower trees', 'garden flowers'}}
>>> sorted_set(plants.update((("hardwood", "oak"), ("softwood", "fir")), "trees"))  # comment below
{'trees': {('hardwood', 'oak'), ('softwood', 'fir')}, 'flowers': {'flower trees', 'garden flowers'}}
>>> # it is not possible to update a dict from these tuples -> replace the previous dict with a new set with the tuples
>>> plants = Fagus({"trees": {"hardwood": "beech", "softwood": "fir"}})  # making "trees" a dict again for next example
>>> sorted_set(plants.update(dict((("hardwood", "oak"), ("softwood", "pine"))), "trees"))  # comment below
{'trees': {'hardwood': 'oak', 'softwood': 'pine'}}
>>> # Here it is shown how a dict can be updated based on a list of tuples with two elements, or e.g. the iterator
>>> # dict.items() returns. By passing the list of tuples to the dict() function first, Fagus detects your intention
>>> # to update a dict instead of overwriting it with a set
```

The third principle `update()` operates after is the following:
3. If you would like to update a `dict`, you must pass a `Mapping` (the type of key-value containers like `dict`). If you just pass e.g. a `tuple` of `tuple`-nodes with two elements or `dict.items()`, the `dict` will be overwritten with a `set`. To update the dict, just pass e.g. the `tuple` of `tuple`-nodes through `dict()` before passing it to `update()`. For any `Iterable` that is not a `Mapping`, the `Mapping` will be removed and a `set` will be created.

Especially this last principle may seem tedious, however it was chosen to implement it that way to prevent ambiguity, and the main reason for that is the `update()` function being used in `set`-nodes as well as `dict`-nodes.

### remove(), delete() and pop()

### serialize() -- ensure that a tree is json- or yaml-serializable

### mod() -- modifying elements

## Iterating over nested objects

### Skipping nodes in iteration.

## Filtering nested objects
