from copy import deepcopy
import re
from abc import ABCMeta
from collections.abc import (
    Collection,
    Mapping,
    Sequence,
    MutableMapping,
    MutableSequence,
    Reversible,
    Iterable,
    MutableSet,
)
from datetime import date, datetime, time
from typing import Union


class TFunc:
    def __init__(self, function_pointer: callable, old_value_position: Union[int, str] = 1, *args, **kwargs):
        self.function_pointer = function_pointer
        self.old_value_pos = old_value_position
        self.args = args
        self.kwargs = kwargs

    def __call__(self, old_value):
        if isinstance(self.old_value_pos, str):
            return self.function_pointer(*self.args, **self.kwargs, **{self.old_value_pos: old_value})
        args = list(self.args)
        if self.old_value_pos != 0:
            args.insert(self.old_value_pos if self.old_value_pos < 0 else self.old_value_pos - 1, old_value)
        return self.function_pointer(*args, **self.kwargs)


class TFilter:
    def __init__(self, *args, **kwargs):
        self.inexclude = kwargs.pop("inexclude", "")
        if not isinstance(self.inexclude, str) or not bool(re.fullmatch("[+-]*", self.inexclude)):
            raise ValueError(
                f"{self.inexclude} is invalid for inexclude. It must be a str consisting of only + (to include) and "
                f"- (to exclude). If nothing has been specified all filteres will be treated as include (+)-filters."
            )
        self.type = kwargs.pop("type", "")
        if not isinstance(self.type, str) and not self.type[0:1] in ("", "c", "v"):
            raise ValueError('type must be a str, either starting with "c"(heck) or "v"(alue). "" means default filter')
        self.type = {"c": "check", "v": "value", "": ""}[self.type[0:1]]
        if kwargs:
            raise TypeError(
                f"Unsupported keyword argument{'s' if len(kwargs) > 1 else ''} in TFilter(): {' '.join(kwargs)}"
            )
        self.args = list(args)
        if self.type == "value" and (
            len(args) != 1 or not all(callable(e) for e in (args[0] if TreeO.__is__(args[0], Sequence) else args))
        ):
            raise TypeError("A value-filter must have exactly one argument. Either a lambda, or a list of lambdas")
        else:
            for i, arg in enumerate(self.args):
                if isinstance(arg, str) and arg != re.escape(arg):
                    self[i] = re.compile(arg)
                elif not isinstance(arg, Mapping) and TreeO.__is__(arg, Collection):
                    if not isinstance(arg, MutableSequence):
                        self[i] = list(arg)
                    for j, e in enumerate(arg):
                        if isinstance(arg, str) and arg != re.escape(arg):
                            self[i] = re.compile(arg)
                        elif isinstance(e, TFilter):
                            self[i] = list(arg)
                            if not hasattr(self, "extra_filters"):
                                self.extra_filters = {}
                            if i not in self.extra_filters:
                                self.extra_filters[i] = []
                            if not isinstance(self.args[i], MutableSequence):
                                self[i] = list(self[i])
                            self.extra_filters[i].append(self.args[i].pop(j))
                elif isinstance(arg, TFilter):
                    raise ValueError(
                        "Detected subfilter as standalone arg, which makes no sense. "
                        "Put subfilters into lists of alternative values / filters."
                    )

    def __getitem__(self, index: int):
        try:
            return self.args[index]
        except IndexError:
            return True

    def __setitem__(self, key, value):
        try:
            self.args[key] = value
        except IndexError:
            pass

    def match(self, value, index):
        filter_arg, included = self[index], self.included(index)
        for e in filter_arg if TreeO.__is__(filter_arg, Collection) else (filter_arg,):
            if e is True:
                return True, self, index + 1
            elif isinstance(e, TFilter):
                match, filter_, index_ = e.match(value, 0)
                if match:
                    return included == match, filter_, index_
            elif callable(e):
                return included == e(value), self, index + 1
            elif isinstance(e, re.Pattern):
                return included == bool(filter_arg.fullmatch(value)), self, index + 1
            elif included == (e == value):
                return True, self, index + 1
        return False, self, index + 1

    def match_list(self, value, index, node_length):
        if not isinstance(value, int) or not (-node_length <= value < node_length):
            return False, self, index + 1
        filter_arg, included = self[index], self.included(index)
        for e in filter_arg if TreeO.__is__(filter_arg, Collection) else (filter_arg,):
            if e is True:
                return True, self, index + 1
            elif isinstance(e, TFilter):
                match, filter_, index_ = e.match_list(value, 0, node_length)
                if match:
                    return included == match, filter_, index_
            elif callable(e):
                return included == e(value), self, index + 1
            elif included == (e == value):
                return True, self, index + 1
        return False, self, index + 1

    def match_extra_filters(self, node, index):
        if hasattr(self, "extra_filters") and index in self.extra_filters:
            for filter_ in self.extra_filters[index]:
                if filter_.type == "check":
                    match = filter_.__match_check_filter_r(node)
                    if not match:
                        return False
                else:  # value filter
                    for test in (filter_[0],) if callable(filter_[0]) else filter_[0]:
                        match = test[node]
                        if not match:
                            return False
        return True

    def __match_check_filter_r(self, node, index: int = 0):
        for k, v in node.items() if isinstance(node, Mapping) else enumerate(node):
            if isinstance(node, Mapping):
                match_k = self.match(k, index)
            elif TreeO.__is__(node, Sequence):
                match_k = self.match_list(k, index, len(node))
            else:
                match_k = True, self, index
            if match_k[0]:
                if TreeO.__is__(v, Collection):
                    match_v = match_k[1].__match_check_filter_r(v, match_k[2])
                else:
                    match_v, *_ = match_k[1].match(v, match_k[2])
                if match_v:
                    return True
        return False

    def included(self, index):
        return self.inexclude[index : index + 1] != "-"


class TreeOMeta(ABCMeta):
    class __Empty__:
        pass

    @staticmethod
    def __is__(value, *args):
        if not all([isinstance(arg, type) for arg in args]):
            raise TypeError("All args must be of the type type.")
        return not isinstance(value, (str, bytes, bytearray)) and isinstance(value, args)

    @staticmethod
    def __verify_option__(option_name, value):
        if option_name in TreeOMeta.__default_options__:
            opt_cls = TreeOMeta.__default_options__[option_name]
            if len(opt_cls) > 1 and not isinstance(value, opt_cls[1]):
                raise TypeError(
                    f"Can't apply {option_name} because {option_name} needs to be a {opt_cls[1].__name__}, "
                    f"and you provided a {value.__class__.__name__}."
                )
            if len(opt_cls) > 3 and not opt_cls[2](value):
                raise ValueError(opt_cls[3])
            return value
        else:
            raise ValueError(f"The option named {option_name} is not defined in TreeO.")

    __default_options__ = dict(
        default_node_type=(
            "d",
            str,
            lambda x: x in ("d", "l"),
            'Default_node_type must be either "d" for dict ' 'or "l" for list.',
        ),
        default_value=(None,),
        list_insert=(
            0,
            int,
            lambda x: x >= 0,
            "List-insert must be a positive int. By default (list_insert == 0), "
            "all existing list-indices will be traversed. If list-insert > 0, a "
            "new node will be inserted in the n'th list that is traversed.",
        ),
        node_types=(
            "",
            str,
            lambda x: bool(re.fullmatch("[dl]*", x)),
            "The only allowed characters in node_types are d (for dict) and l (for list).",
        ),
        mod_functions=(
            {
                datetime: lambda x: x.isoformat(" ", "seconds"),
                date: lambda x: x.isoformat(),
                time: lambda x: x.isoformat("seconds"),
                "default": lambda x: str(x),
            },
            MutableMapping,
            lambda x: all(
                k in ("default", "tuple_keys")
                or all(isinstance(y, type) for y in (k if TreeO.__is__(k, Iterable) else (k,)))
                and callable(v)
                for k, v in x.items()
            ),
            "mod_functions must be a dict with types (or tuples of types) as keys and function pointers "
            "(either lambda or wrapped in Funk-objects) as values.",
        ),
        iter_fill=(..., object),
        value_split=(" ", str),
        return_node=(False, bool),
    )

    def __new__(mcs, name, bases, dct):
        obj = super().__new__(mcs, name, bases, dct)
        for option_name, option in TreeOMeta.__default_options__.items():
            setattr(mcs, option_name, option[0])
        return obj

    def __setattr__(cls, attr, value):
        super(TreeOMeta, cls).__setattr__(
            attr,
            value
            if hasattr(TreeOMeta, attr) or attr in ("__abstractmethods__", "_abc_impl")
            else TreeOMeta.__verify_option__(attr, value),
        )


class TreeO(MutableMapping, MutableSequence, metaclass=TreeOMeta):
    """TreeO (TreeObject) is a wrapper-class for complex, nested objects of dicts and lists in Python. The base-object
    is always modified directly. If you don't want to modify an object TreeO(obj.copy) to modify a copy instead.

    To get "hello" from a = TreeO([["good", "morning"], ["hello, "world"]], you can use a[(0, 1)]. The tuple (0, 1)
    is the path-parameter that is used to traverse a. At first, index 0 is picked in the top-most list, and then the 2nd
    element is picked from the inner list. The path-parameter can be any Collection data structure. The keys must be
    either integers for lists, or any hashable object for dicts. For convenience, the keys can also be put in a single
    string separated by spaces, so a["0 1"] also returns "hello".

    TreeO can be used as an object by instantiating it, but it's also possible to use all methods statically without
    even an object, so that a = {}; TreeO.set(a, "top med", 1) and a = TreeO({}); a.set("top med", 1) do the same."""

    def get(self: Union[Mapping, Sequence], path: Iterable = "", default=..., **kwargs):
        """Retrieves value from path. If the value doesn't exist, default is returned."""
        TreeO._verify_kwargs(kwargs, "get", "return_node", "value_split", "cp")
        node = self.obj if isinstance(self, TreeO) else self
        t_path = path.split(TreeO._opt(self, "value_split", **kwargs)) if isinstance(path, str) else tuple(path)
        if path:
            for node_name in t_path:
                try:
                    if TreeO.__is__(node, Mapping, Sequence):
                        node = node[node_name if isinstance(node, Mapping) else int(node_name)]
                    else:
                        node = TreeO._opt(self, "default_value", default_value=default)
                        break
                except (IndexError, ValueError, KeyError):
                    node = TreeO._opt(self, "default_value", default_value=default)
                    break
        if kwargs.get("cp", False):
            node = TreeO.__copy__(node) if kwargs.get("cp").startswith("s") else deepcopy(node)
        return (
            TreeO._child(self, node)
            if TreeO.__is__(node, Mapping, Sequence) and TreeO._opt(self, "return_node", **kwargs)
            else node
        )

    def _parent(self: Union[MutableMapping, MutableSequence], t_path: tuple, **kwargs):
        """Internal function giving the parent_node"""
        node = self.obj if isinstance(self, TreeO) else self
        list_insert = TreeO._opt(self, "list_insert", **kwargs)
        for node_name in t_path[:-1]:
            try:
                if TreeO.__is__(node, Mapping, Sequence):
                    node = node[node_name if isinstance(node, Mapping) else int(node_name)]
                    if TreeO.__is__(node, Sequence):
                        if list_insert == 1:
                            return ...
                        list_insert -= 1
                else:
                    return ...
            except (IndexError, ValueError, KeyError):
                return ...
        return node

    def iter(self: Union[Mapping, Sequence], max_items: int = -1, path="", filter_: TFilter = None, **kwargs):
        """Iterate over all sub-nodes at path

        Returns a list with one tuple for each leaf-node, containing the keys of the parent-nodes until the leaf

        max_items defines the max amount of keys to have in a tuple. E. g. if max_items is four, it means that the keys
            of the three topmost nodes will be put in the tuple. The last element in the tuple contains the remaining
            part of the tree at that path as a dict / list. Note that if at some point there are fewer than four levels,
            the tuple can contain fewer than four items. max_items can be set to -1 to no matter what iterate over all
            nodes until the leaves.

        path can be used to start iterating at some point inside the TreeO-tree
        """
        TreeO._verify_kwargs(kwargs, "iter", "return_node", "value_split", "cp", "iter_fill", "reduce")
        iter_fill = kwargs.pop("iter_fill", ...)
        reduce = kwargs.pop("reduce", None)
        node = TreeO.get(self, path, **{**kwargs, "return_node": False})
        if 0 <= max_items <= 1 or max_items < -1:
            return ValueError(
                "max_items must be either -1 to always iter to the leaf, or >= 2 to have up to that "
                "number of items in the tuples."
            )
        if TreeO.__is__(node, Mapping, Sequence):
            iter_list = TreeO._iter_r(
                self,
                node,
                max_items,
                TreeO._opt(self, "return_node", **kwargs),
                TreeO._opt(self, "iter_fill", iter_fill=iter_fill),
                filter_,
            )
            if reduce is not None:
                if isinstance(reduce, Collection) and all(isinstance(e, int) for e in reduce):
                    return [tuple(e[i] for i in reduce if -len(e) <= i < len(e)) for e in iter_list]
                elif isinstance(reduce, int):
                    return [e[reduce] for e in iter_list if -len(e) <= reduce < len(e)]
                else:
                    raise TypeError(
                        f"Invalid type {type(reduce).__name__} for reduce parameter. Must be int or list of ints."
                    )
            else:
                return iter_list
        else:
            return []

    def _iter_r(
        self: Union[Mapping, Sequence],
        node,
        max_items,
        return_node: bool,
        iter_fill,
        filter_: TFilter = None,
        index: int = 0,
    ):
        iter_list = []
        for k, v in node.items() if isinstance(node, Mapping) else enumerate(node):
            filter__, index_ = filter_, index + 1
            if isinstance(filter_, TFilter):
                if isinstance(node, Mapping):
                    match_k, filter__, index_ = filter_.match(k, index)
                elif isinstance(node, Sequence):
                    match_k, filter__, index_ = filter_.match_list(k, index, len(node))
                else:
                    match_k = True
                if match_k:
                    if not TreeO.__is__(v, Mapping, Sequence):
                        if TreeO.__is__(v, Collection):
                            v = set(e for e in v if filter__.match(e, index_))
                        else:
                            match_v, filter__, index_ = filter__.match(v, index_)
                            if not match_v:
                                continue
                else:
                    continue
            if max_items != 2:
                if TreeO.__is__(v, Mapping, Sequence):
                    new_v = TreeO._iter_r(self, v, max_items - 1, return_node, iter_fill, filter__, index_)
                    if filter__.match_extra_filters(v, index_) if isinstance(filter__, TFilter) else True:
                        for e in new_v:
                            iter_list.append((k, *e))
                    continue
                elif TreeO.__is__(v, Collection):
                    iter_list.extend(
                        (k, *e, *(() if iter_fill is ... else (iter_fill,) * (max_items - 3))) for e in enumerate(v)
                    )
                    continue
            if filter__.match_extra_filters(v, index_) if isinstance(filter__, TFilter) else True:
                iter_list.append(
                    (
                        k,
                        TreeO._child(self, v) if return_node and TreeO.__is__(v, Mapping, Sequence) else v,
                        *(() if iter_fill is ... else (iter_fill,) * (max_items - 2)),
                    )
                )
        return iter_list

    def filter(self: Union[MutableMapping, MutableSequence], filter_: TFilter, path="", **kwargs):
        TreeO._verify_kwargs(kwargs, "iter", "value_split", "cp", "return_node")
        obj = self.obj if isinstance(self, TreeO) else self
        if kwargs.get("cp", False):
            obj = TreeO.__copy__(obj) if kwargs.get("cp").startswith("s") else deepcopy(obj)
        if path:
            filtered = TreeO._filter_r(TreeO.get(obj, path, [], **{**kwargs, "return_node": False}), filter_)
            if not filter_.match_extra_filters(filtered, 0):
                filtered.clear()
            TreeO.set(self, filtered, path)
        else:
            filtered = TreeO._filter_r(obj, filter_)
            obj.clear()
            if filter_.match_extra_filters(filtered, 0):
                getattr(obj, "update" if isinstance(obj, MutableMapping) else "extend")(filtered)
        return TreeO._child(self, obj) if TreeO._opt(self, "return_node", **kwargs) else obj

    @staticmethod
    def _filter_r(node: Union[Mapping, Sequence], filter_: TFilter, index: int = 0):
        if isinstance(node, Mapping):
            new_node, action = {}, None
        elif isinstance(node, Sequence):
            new_node, action = [], "append"
        else:
            new_node, action = set(), "add"
        for k, v in node.items() if isinstance(node, Mapping) else enumerate(node):
            if action == "add":
                match_k = True, filter_, index + 1
            elif isinstance(node, Mapping):
                match_k = filter_.match(k, index)
            else:
                match_k = filter_.match_list(k, index, len(node))
            if match_k[0]:
                if TreeO.__is__(v, Collection):
                    new_v = TreeO._filter_r(v, *match_k[1:])
                    if bool(new_v):
                        match_v = match_k[1].match_extra_filters(v, match_k[2])
                    else:
                        match_v = bool(v) == bool(new_v)
                    v = new_v
                else:
                    match_v, *_ = match_k[1].match(v, match_k[2])
                if match_v:
                    if action:
                        getattr(new_node, action)(v)
                    else:
                        new_node[k] = v
        return new_node

    def set(self: Union[MutableMapping, MutableSequence], value, path, node_types: str = ..., **kwargs):
        """Create (if they don't already exist) all sub-nodes in path, and finally set value at leaf-node

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO._build_node(self, value, path, "set", node_types, **kwargs)

    def append(self: Union[MutableMapping, MutableSequence], value, path="", node_types: str = ..., **kwargs):
        """Create (if they don't already exist) all sub-nodes in path, and finally append value to list at leaf-node

        If the leaf-node is a set, tuple or other value it is converted to a list. Then the new value is appended.

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO._build_node(self, value, path, "append", node_types, **kwargs)

    def extend(
        self: Union[MutableMapping, MutableSequence], values: Iterable, path="", node_types: str = ..., **kwargs
    ):
        """Create (if they don't already exist) all sub-nodes in path. Then extend list at leaf-node with the new values

        If the leaf-node is a set, tuple or other value it is converted to a list. Then the new values are appended.

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO._build_node(self, values, path, "extend", node_types, **kwargs)

    def insert(
        self: Union[MutableMapping, MutableSequence], index: int, value, path="", node_types: str = ..., **kwargs
    ):
        """Create (if they don't already exist) all sub-nodes in path. Insert new value at index in list at leaf-node

        If the leaf-node is a set, tuple or other value it is converted to a list. Then insert new value at index

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO._build_node(self, value, path, "insert", node_types, **kwargs, index=index)

    def add(self: Union[MutableMapping, MutableSequence], value, path, node_types: str = ..., **kwargs):
        """Create (if they don't already exist) all sub-nodes in path, and finally add new value to set at leaf-node

        If the leaf-node is a list, tuple or other value it is converted to a list. Then the new values are added.

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO._build_node(self, value, path, "add", node_types, **kwargs)

    def update(self: Union[MutableMapping, MutableSequence], values: Iterable, path="", node_types=..., **kwargs):
        """Create (if they don't already exist) all sub-nodes in path, then update set at leaf-node with new values

        If the leaf-node is a list, tuple or other value it is converted to a set. That set is then updated with the new
        values. If the node at path is a dict, and values also is a dict, the node-dict is updated with the new values.

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO._build_node(self, values, path, "update", **kwargs)

    def _build_node(
        self: Union[MutableMapping, MutableSequence], value, path, action: str, node_types: str = ..., **kwargs
    ):
        if not TreeO.__is__(self, MutableMapping, MutableSequence):
            raise TypeError(f"Can't modify base object self having the immutable type {type(self).__name__}.")
        TreeO._verify_kwargs(
            kwargs,
            action,
            "default_node_type",
            "list_insert",
            "value_split",
            "return_node",
            "cp",
            *(("index",) if action == "insert" else ()),
        )
        node_types = TreeO._opt(self, "node_types", node_types=node_types)
        obj = self.obj if isinstance(self, TreeO) else self
        if kwargs.get("cp", False):
            obj = TreeO.__copy__(obj) if kwargs.get("cp").startswith("s") else deepcopy(obj)
        if path:
            t_path = path.split(TreeO._opt(self, "value_split", **kwargs)) if isinstance(path, str) else tuple(path)
            next_index = TreeO._index(t_path[0], ...)
            list_insert = TreeO._opt(self, "list_insert", **kwargs)
            node = obj
            if (
                isinstance(obj, MutableMapping)
                and node_types[0:1] == "l"
                or TreeO.__is__(obj, MutableSequence)
                and (node_types[0:1] == "d" or next_index is ...)
            ):
                raise TypeError(
                    f"Your base object is a {type(obj).__name__}. Due to limitations in how references "
                    f"work in Python, TreeO can't convert that base-object to a "
                    f"{'list' if node_types[0:1] == 'l' else 'dict'}, which was requested %s."
                    % (
                        f"because {t_path[0]} is no numeric list-index"
                        if TreeO.__is__(obj, MutableSequence) and not t_path[0].lstrip("-").isdigit()
                        else f"by the first character in node_types being {node_types[0:1]}"
                    )
                )
            for i in range(len(t_path)):
                node_key = next_index if TreeO.__is__(node, MutableSequence) else t_path[i]
                next_index = TreeO._index(t_path[i + 1], ...) if i < len(t_path) - 1 else ...
                next_node = (
                    list
                    if node_types[i + 1 : i + 2] == "l"
                    or not node_types[i + 1 : i + 2]
                    and TreeO._opt(self, "default_node_type", **kwargs) == "l"
                    and next_index is not ...
                    else dict
                )
                if TreeO.__is__(node, MutableSequence):
                    if node_key is ...:
                        raise ValueError(f"Can't parse numeric list-index from {node_key}.")
                    elif node_key >= len(node):
                        node.append(next_node())
                        node_key = -1
                    elif node_key < -len(node):
                        node.insert(0, next_node())
                        node_key = 0
                    if i == len(t_path) - 1:
                        if list_insert == 1:
                            node.insert(node_key, TreeO._put_value(..., value, action, **kwargs))
                        else:
                            node[node_key] = TreeO._put_value(node[node_key], value, action, **kwargs)
                    else:
                        if list_insert == 1:
                            node.insert(node_key, next_node())
                        else:
                            if not TreeO.__is__(node[node_key], MutableMapping, MutableSequence) and TreeO.__is__(
                                node[node_key], Iterable
                            ):
                                node[node_key] = (
                                    dict(node[node_key].items())
                                    if isinstance(node[node_key], Mapping)
                                    else list(node[node_key])
                                )
                            if (
                                next_node != node[node_key].__class__
                                if node_types[i + 1 : i + 2]
                                else TreeO.__is__(node[node_key], MutableSequence) and next_index is ...
                            ):
                                node[node_key] = next_node()
                        list_insert -= 1
                        node = node[node_key]
                else:  # isinstance(node, dict)
                    if i == len(t_path) - 1:
                        node[node_key] = TreeO._put_value(node.get(node_key, ...), value, action, **kwargs)
                    else:
                        if not TreeO.__is__(node.get(node_key), MutableMapping, MutableSequence) and TreeO.__is__(
                            node.get(node_key), Iterable
                        ):
                            node[node_key] = (
                                dict(node[node_key].items())
                                if isinstance(node[node_key], Mapping)
                                else list(node[node_key])
                            )
                        elif node.get(node_key, TreeOMeta.__Empty__) is TreeOMeta.__Empty__:
                            node[node_key] = next_node()
                        if (
                            next_node != node[node_key].__class__
                            if node_types[i + 1 : i + 2]
                            else TreeO.__is__(node[node_key], MutableSequence) and next_index is ...
                        ):
                            node[node_key] = next_node()
                        node = node[node_key]
        else:
            if isinstance(obj, MutableMapping) and action == "update" and isinstance(value, Mapping):
                obj.update(value)
            elif TreeO.__is__(obj, MutableSequence) and action in ("append", "extend", "insert"):
                if action == "insert":
                    obj.insert(kwargs["index"], value)
                else:
                    getattr(obj, action)(value)
            else:
                raise ValueError(f"Can't {action} value {'to' if action == 'add' else 'in'} base-{type(obj).__name__}.")
        return TreeO._child(self, obj) if TreeO._opt(self, "return_node", **kwargs) else obj

    @staticmethod
    def _index(value, default):
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _put_value(node, value, action, **kwargs):
        if action == "set":
            return value
        elif action in ("append", "extend", "insert"):
            if not TreeO.__is__(node, MutableSequence):
                if TreeO.__is__(node, Iterable):
                    node = list(node)
                elif node is ...:
                    node = []
                else:
                    node = [node]
            if action == "insert":
                node.insert(kwargs["index"], value)
            else:
                getattr(node, action)(value)
        elif action in ("add", "update"):
            if node is ...:
                return (
                    dict(value)
                    if isinstance(value, Mapping)
                    else set(value)
                    if TreeO.__is__(value, Iterable)
                    else {value}
                )
            else:
                if not isinstance(node, (MutableSet, MutableMapping)):
                    if TreeO.__is__(node, Iterable):
                        node = set(node)
                    else:
                        node = {node}
                elif isinstance(node, MutableMapping) and not isinstance(value, Mapping):
                    raise ValueError(f"Can't update dict with value of type {type(value).__name__} not being a Mapping")
                getattr(node, action)(value)
        return node

    def setdefault(self: Union[MutableMapping, MutableSequence], default=..., path="", node_types=..., **kwargs):
        """Get value at path and return it. If there is no value at path, set default at path, and return default."""
        TreeO._verify_kwargs(kwargs, "setdefault", "default_node_type", "list_insert", "value_split")
        t_path = path.split(TreeO._opt(self, "value_split", **kwargs)) if isinstance(path, str) else tuple(path)
        parent_node = TreeO._parent(self, t_path, **kwargs)
        if TreeO.__is__(parent_node, Mapping, Sequence):
            original_value = TreeO.get(parent_node, t_path[-1], TreeOMeta.__Empty__, return_node=False)
            if original_value is not TreeOMeta.__Empty__:
                return original_value
        default_value = TreeO._opt(self, "default_value", default_value=default)
        TreeO.set(self, default_value, path, node_types, **kwargs)
        return default_value

    def mod(
        self: Union[MutableMapping, MutableSequence],
        mod_function: Union[TFunc, callable],
        path,
        default=...,
        node_types: str = ...,
        replace_value=True,
        **kwargs,
    ):
        """Modifies the value at path using the function-pointer mod_function

        mod can be used like this TreeO.mod(obj, "kitchen spoon", lambda x: x+1, 1) to count the number of spoons in
        the kitchen. If there is no value to modify, the default value (here 1) will be set at the node.

        mod_function can be a lambda or a function-pointer pointing to a function that takes one argument
            for usage with more complicated functions, pass a tuple formatted like this to mod_function:
            (function_pointer, (arg1, arg2, ...), {keyword1: kwarg1, keyword2: kwarg2, keyword3: ...})
            Explained in words: the first element in the tuple must be the function pointer. Depending on what arguments
            you need, add a tuple with normal arguments, and a dict with keyword-arguments. The first argument that is
            passed to the function is always the old value, followed by the args from the tuple and the kwargs from the
            dict. It's not necessary to define an empty dict / empty list if you don't need args / kwargs.

        replace_value replace the old value with what the lambda returns, or just use the lambda to modify the old
            value without replacing it.

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
            empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        TreeO._verify_kwargs(kwargs, "mod", "default_node_type", "list_insert", "value_split", "cp")
        obj = self.obj if isinstance(self, TreeO) else self
        if kwargs.get("cp", False):
            obj = TreeO.__copy__(obj) if kwargs.get("cp").startswith("s") else deepcopy(obj)
        t_path = path.split(TreeO._opt(self, "value_split", **kwargs)) if isinstance(path, str) else tuple(path)
        parent_node = TreeO._parent(self, t_path, **kwargs)
        if TreeO.__is__(parent_node, MutableMapping, MutableSequence):
            old_value = TreeO.get(parent_node, t_path[-1], TreeOMeta.__Empty__, **{**kwargs, "return_node": False})
            if old_value is not TreeOMeta.__Empty__:
                if callable(mod_function):
                    new_value = mod_function(old_value)
                elif (
                    TreeO.__is__(mod_function, Sequence)
                    and len(mod_function) > 0
                    and callable(mod_function[0])
                    and all((TreeO.__is__(x, Mapping, Sequence) for x in mod_function[1:]))
                ):
                    new_value = mod_function[0](
                        old_value,
                        *(a for al in mod_function[1:] if TreeO.__is__(al, Sequence) for a in al),
                        **{k: v for d in mod_function[1:] if isinstance(d, Mapping) for k, v in d.items()},
                    )
                else:
                    raise TypeError(
                        "Valid types for mod_function: lambda, function_pointer_taking_one_arg or"
                        "(function_pointer, (arg1, arg2, ...), {keyword1: kwarg1, keyword2: kwarg2, ...})"
                    )
                if replace_value:
                    TreeO.set(parent_node, new_value, t_path[-1], **kwargs)
                return new_value
        default_value = TreeO._opt(self, "default_value") if default is ... else default
        TreeO.set(obj, default_value, path, node_types, **kwargs)
        return default_value

    def pop(self: Union[MutableMapping, MutableSequence], path, **kwargs):
        """Deletes the value at path and returns it"""
        TreeO._verify_kwargs(kwargs, "pop", "value_split")
        t_path = path.split(TreeO._opt(self, "value_split", **kwargs)) if isinstance(path, str) else tuple(path)
        node = self.obj if isinstance(self, TreeO) else self
        for node_name in t_path[:-1]:
            try:
                node = node[node_name if isinstance(node, dict) else int(node_name)]
            except (IndexError, ValueError, KeyError):
                return
        return node.pop(int(t_path[-1]) if TreeO.__is__(node, Sequence) else t_path[-1])

    def serialize(self: Union[dict, list], mod_functions: MutableMapping = ..., path="", **kwargs):
        """Makes sure the object can be serialized so that it can be converted to JSON, YAML etc.

        The only allowed data-types for serialization are: dict, list, bool, float, int, str, None

        Sets and tuples are converted to lists. Other objects whose types are not allowed in serialized objects are
        modified to a type that is allowed using the mod_functions-parameter. mod_functions is a dict, with the type
        of object (or a tuple of types of objects) as key, and a function pointer that can be a lambda as value.

        The default mod_functions are: {datetime: lambda x: x.isoformat(), date: lambda x: x.isoformat(), time:
        lambda x: x.isoformat(), "default": lambda x: str(x)}

        By default, date, datetime and time-objects are replaced by their isoformat-string. All other objects whose
        types don't appear in mod_functions are modified by the function behind the key "default". By default, this
        function is lambda x: str(x) that replaces the object with its string-representation."""
        if not isinstance(self.obj if isinstance(self, TreeO) else self, (dict, list)):
            raise TypeError(f"Can't modify base-object self having the immutable type {type(self).__name__}.")
        TreeO._verify_kwargs(kwargs, "serialize", "cp", "value_split")
        node = TreeO.get(self, path, return_node=False, **kwargs)
        if kwargs.get("cp", False):
            node = TreeO.__copy__(node) if kwargs.get("cp").startswith("s") else deepcopy(node)
        return TreeO._serialize_r(
            node,
            {
                **TreeO._opt(self, "mod_functions"),
                **(TreeOMeta.__verify_option__("mod_functions", {} if mod_functions is ... else mod_functions)),
            },
        )

    @staticmethod
    def _serialize_r(node, mod_functions: MutableMapping):
        for k, v in list(node.items() if isinstance(node, MutableMapping) else enumerate(node)):
            ny_k, ny_v = ..., ...
            if not isinstance(k, (bool, float, int, str)) and k is not None:
                if isinstance(k, tuple):
                    if "tuple_keys" in mod_functions:
                        ny_k = mod_functions["tuple_keys"](k)
                    else:
                        raise ValueError(
                            "Dicts with composite keys (tuples) are not supported in serialized objects. "
                            'Use "tuple_keys" to define a specific mod_function for these dict-keys.'
                        )
                else:
                    ny_k = TreeO._serializable_value(k, mod_functions)
            if TreeO.__is__(v, Collection):
                if isinstance(v, (dict, list)):
                    TreeO._serialize_r(v, mod_functions)
                else:
                    ny_v = dict(v.items()) if isinstance(v, Mapping) else list(v)
                    TreeO._serialize_r(ny_v, mod_functions)
            elif not isinstance(v, (bool, float, int, str)) and v is not None:
                ny_v = TreeO._serializable_value(v, mod_functions)
            if ny_k is not ...:
                node.pop(k)
                node[ny_k] = v if ny_v is ... else ny_v
            elif ny_v is not ...:
                node[k] = ny_v
        return node

    @staticmethod
    def _serializable_value(value, mod_functions):
        for types, mod_function in mod_functions.items():
            if type(value) == types or (TreeO.__is__(types, Collection) and type(value) in types):
                return mod_function(value)
        return mod_functions["default"](value)

    def _opt(self: Union[Mapping, Sequence], option_name: str, **kwargs):
        if kwargs.get(option_name, ...) is not ...:
            return TreeO.__verify_option__(option_name, kwargs[option_name])
        return (
            self._options[option_name]
            if isinstance(self, TreeO) and isinstance(self._options, dict) and option_name in self._options
            else getattr(TreeO, option_name)
        )

    @staticmethod
    def _verify_kwargs(kwargs: dict, function_name, *allowed_kwargs):
        if "cp" in kwargs and "cp" in allowed_kwargs:
            cp = kwargs.get("cp")
            if cp[0:1] not in ("d", "s") if isinstance(cp, str) else cp is not False:
                raise ValueError('The cp kwarg must be either False for no copy, or "d"(eep) or "s"(hallow).')
        wrong_kwargs = tuple(filter(lambda x: x not in allowed_kwargs, kwargs))
        if wrong_kwargs:
            raise TypeError(
                f"Unsupported keyword argument{'s' if len(wrong_kwargs) > 1 else ''} in "
                f"TreeO.{function_name}(): {' '.join(wrong_kwargs)}"
            )

    def keys(self: Union[Mapping, Sequence], path="", **kwargs):
        """Returns keys for node at path

        If node is iterable but not a dict, the indices are returned. If node is a single value, [0] is returned."""
        TreeO._verify_kwargs(kwargs, "keys", "value_split", "cp")
        obj = TreeO.get(self, path, **{**kwargs, "return_node": False})
        if isinstance(obj, MutableMapping):
            return obj.keys()
        elif TreeO.__is__(obj, Collection):
            return [x[0] for x in enumerate(obj)]
        else:
            return

    def values(self: Union[Mapping, Sequence], path="", **kwargs):
        """Returns values for node at path"""
        TreeO._verify_kwargs(kwargs, "values", "return_node", "value_split", "cp")
        obj = TreeO.get(self, path, **{**kwargs, "return_node": False})
        return_node = TreeO._opt(self, "return_node", **kwargs)
        if isinstance(obj, MutableMapping):
            return [TreeO._child(self, x) for x in obj.values()] if return_node else obj.values()
        else:
            return [TreeO._child(self, x) for x in obj] if return_node else list(obj)

    def items(self: Union[Mapping, Sequence], path="", **kwargs):
        """Returns a list with one tuple for each leaf - the first value is the key, the second is the child-dict."""
        TreeO._verify_kwargs(kwargs, "items", "return_node", "value_split", "cp")
        return TreeO.iter(self, 2, path, **kwargs)

    def clear(self: Union[Mapping, Sequence], path="", **kwargs):
        """Removes all elements from node at path."""
        TreeO._verify_kwargs(kwargs, "clear", "return_node", "value_split", "cp")
        TreeO.get(self, path, **{**kwargs, "return_node": False}).clear()
        return TreeO(self) if not isinstance(self, TreeO) and TreeO._opt(self, "return_node", **kwargs) else self

    def contains(self: Union[Mapping, Sequence], value, path="", **kwargs):
        """Check if value is present in the node at path. Returns value == node if the node isn't iterable."""
        TreeO._verify_kwargs(kwargs, "contains", "value_split")
        node = TreeO.get(self, path, return_node=False, **kwargs)
        return value in node if TreeO.__is__(node, Collection) else value == node

    def count(self: Union[Mapping, Sequence], path="", **kwargs):
        """Get the number of child-nodes at path"""
        TreeO._verify_kwargs(kwargs, "count", "value_split")
        node = TreeO.get(self, path, TreeO.__Empty__, return_node=False, **kwargs)
        return len(node) if TreeO.__is__(node, Collection) else 0 if node is TreeO.__Empty__ else 1

    def reversed(self: Union[Mapping, Sequence], path="", **kwargs):
        """Get reversed child-node at path if that node is a list"""
        TreeO._verify_kwargs(kwargs, "reversed", "value_split", "return_node")
        node = TreeO.get(self, path, **{**kwargs, "return_node": False})
        if TreeO.__is__(node, Reversible):
            return (
                TreeO._child(self, list(reversed(node)))
                if TreeO._opt(self, "return_node", **kwargs)
                else reversed(node)
            )
        else:
            raise TypeError(f"Cannot reverse node of type {type(node).__name__}.")

    def reverse(self: Union[MutableMapping, MutableSequence], path="", **kwargs):
        """Reverse child-node at path if that node is a list"""
        TreeO._verify_kwargs(kwargs, "reverse", "cp", "value_split", "return_node")
        obj = self.obj if isinstance(self, TreeO) else self
        if kwargs.get("cp", True):
            obj = TreeO.__copy__(obj) if kwargs.get("cp").startswith("s") else deepcopy(obj)
        node = TreeO.get(self, path, **{**kwargs, "return_node": False})
        if TreeO.__is__(node, MutableSequence):
            node.reverse()
            return TreeO._child(self, obj) if TreeO._opt(self, "return_node", **kwargs) else obj
        else:
            raise TypeError(f"Cannot reverse node of type {type(node).__name__}.")

    def popitem(self):
        """This function is not implemented in TreeO"""
        pass

    def __init__(self, obj: Union[Mapping, Sequence] = None, **kwargs):
        if obj is None:
            obj = [] if TreeO.default_node_type == "l" else {}
        TreeO._verify_kwargs(kwargs, "init", "cp", *TreeO.__default_options__)
        if kwargs.get("cp", False):
            obj = TreeO.__copy__(obj) if kwargs.get("cp").startswith("s") else deepcopy(obj)
        if isinstance(obj, TreeO):
            self.obj = obj()
            self._options = None if self._options is None else self._options.copy()
        else:
            self.obj = obj
            self._options = None
        for kw, value in kwargs.items():
            if kw != "cp":
                setattr(self, kw, value)

    def _child(self: Union[Mapping, Sequence], obj: Union[Mapping, Sequence] = None, **kwargs) -> "TreeO":
        new_obj = TreeO(obj, **kwargs)
        if isinstance(self, TreeO):
            new_obj._options = None if self._options is None else self._options.copy()
        return new_obj

    def __copy__(self: Union[Mapping, Sequence]):
        obj = self.obj if isinstance(self, TreeO) else self
        new_node = obj.copy()
        for k, v in obj.items() if isinstance(obj, Mapping) else enumerate(obj):
            if hasattr(v, "copy"):
                new_node[k] = TreeO.__copy__(v) if TreeO.__is__(v, Mapping, Sequence) else v.copy()
        return new_node

    def __call__(self):
        return self.obj

    def __getattr__(self, attr):  # Enable dot-notation for getting dict-keys at the top-level
        if attr == "obj":
            return self.obj
        elif hasattr(TreeO, attr):
            return (self._options if isinstance(self._options, dict) else {}).get(attr, getattr(TreeO, attr))
        else:
            return self.get(attr.lstrip(TreeO._opt(self, "value_split") if isinstance(attr, str) else attr))

    def __getitem__(self, item):  # Enable [] access for dict-keys at the top-level
        return self.get(item)

    def __setattr__(self, attr, value):  # Enable dot-notation for setting items for dict-keys at the top-level
        if attr in ("obj", "_options"):
            super(TreeO, self).__setattr__(attr, value)
        elif attr in TreeO.__default_options__:
            if self._options is None:
                super(TreeO, self).__setattr__("_options", {})
            self._options[attr] = TreeO.__verify_option__(attr, value)
        else:
            self.set(value, attr.lstrip(TreeO._opt(self, "value_split") if isinstance(attr, str) else attr))

    def __setitem__(self, path, value):  # Enable [] for setting items for dict-keys at the top-level
        self.set(value, path)

    def __delattr__(self, path):  # Enable dot-notation for deleting items for dict-keys at the top-level
        if hasattr(TreeO, path):
            if path in self._options:
                del self._options[path]
                if not self._options:
                    self._options = None
        else:
            self.pop(path.lstrip(TreeO._opt(self, "value_split") if isinstance(path, str) else path))

    def __delitem__(self, path):  # Enable [] for deleting items at dict-keys at the top-level
        self.pop(path)

    def __iter__(self):
        return iter(self.values())

    def __eq__(self, other):
        return self.obj == (other.obj if isinstance(other, TreeO) else other)

    def __ne__(self, other):
        return self.obj != (other.obj if isinstance(other, TreeO) else other)

    def __lt__(self, other):
        return self.obj < (other.obj if isinstance(other, TreeO) else other)

    def __le__(self, other):
        return self.obj <= (other.obj if isinstance(other, TreeO) else other)

    def __gt__(self, other):
        return self.obj > (other.obj if isinstance(other, TreeO) else other)

    def __ge__(self, other):
        return self.obj >= (other.obj if isinstance(other, TreeO) else other)

    def __contains__(self, value):
        return value in self.obj

    def __len__(self):
        return len(self.obj)

    def __bool__(self):
        return bool(self.obj)

    def __repr__(self):
        return self.obj.__repr__()

    def __str__(self):
        return self.obj.__repr__()

    def __iadd__(self, value):
        if isinstance(self(), MutableMapping):
            if isinstance(value, MutableMapping):
                self().update(value)
            else:
                raise TypeError(f"Unsopported operand types for +=: {type(self()).__name__} and {type(value).__name__}")
        else:
            self.obj += value
        return self

    def __add__(self, other):
        a, b = (x() if isinstance(x, TreeO) else x for x in (self, other))
        if isinstance(a, Mapping) and isinstance(b, Mapping):
            res = {**a, **b}
        elif TreeO.__is__(a, Iterable):
            res = [*a, *(b if TreeO.__is__(b, Iterable) else (b,))]
        else:
            raise TypeError(f"Unsupported operand types for +: {type(a).__name__} and {type(b).__name__}")
        return self._child(res) if TreeO._opt(self if isinstance(self, TreeO) else other, "return_node") else res

    def __radd__(self, other):
        return TreeO.__add__(other, self)

    def __sub__(self, other):
        obj = self() if isinstance(self, TreeO) else self
        other = set(other() if isinstance(other, TreeO) else other) if TreeO.__is__(other, Iterable) else (other,)
        if isinstance(obj, Mapping):
            res = {k: v for k, v in obj.items() if k in other}
        else:  # isinstance(self(), Sequence):
            res = list(filter(lambda x: x not in other, obj))
        return self._child(res) if TreeO._opt(self if isinstance(self, TreeO) else other, "return_node") else res

    def __rsub__(self, other):
        return TreeO.__sub__(other, self)

    def __mul__(self, times: int):
        if not isinstance(times, int):
            raise TypeError("To use the * (times)-operator, times must be an int")
        if not TreeO.__is__(self(), Sequence):
            raise TypeError("Your base-object must a tuple or list to get multiplied.")
        return self._child(self() * times) if TreeO._opt(self, "return_node") else self() * times

    def __rmul__(self, other):
        return TreeO.__mul__(self, other)

    def __reversed__(self: Union[MutableMapping, MutableSequence]):
        return TreeO.reversed(self)
