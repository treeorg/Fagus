from copy import deepcopy
import re
from abc import ABCMeta
from collections.abc import Collection, Mapping, Sequence, MutableMapping, MutableSequence, Reversible, Iterable,\
    MutableSet
from datetime import date, datetime, time
from typing import Union


class TreeOMeta(ABCMeta):
    class __Empty__:
        pass

    @staticmethod
    def __verify_option__(option_name, value):
        if option_name in TreeOMeta.__default_options__:
            opt_cls = TreeOMeta.__default_options__[option_name]
            if len(opt_cls) > 1 and value.__class__ != opt_cls[1]:
                raise TypeError(
                    f"Can't apply {option_name} because {option_name} needs to be a {opt_cls[1].__name__}, "
                    f"and you provided a {value.__class__.__name__}.")
            if len(opt_cls) > 3 and not opt_cls[2](value):
                raise ValueError(opt_cls[3])
            return value
        else:
            raise ValueError(f"The option named {option_name} is not defined in TreeO.")

    @staticmethod
    def __try_else__(value, mod_function, default):
        if not callable(mod_function):
            raise ValueError("mod_function must be a callable function pointer.")
        try:
            return mod_function(value)
        except:
            return default

    __default_options__ = dict(
        default_node_type=("d", str, lambda x: x in ("d", "l"), "Default_node_type must be either \"d\" for dict "
                                                                "or \"l\" for list."),
        default_value=(None,),
        list_insert=(0, int, lambda x: x >= 0, "List-insert must be a positive int. By default (list_insert == 0), "
                                               "all existing list-indices will be traversed. If list-insert > 0, a "
                                               "new node will be inserted in the n'th list that is traversed."),
        node_types=("", str, lambda x: bool(re.fullmatch("[dl]*", x)), "The only allowed characters in node_types are "
                                                                       "d (for dict) and l (for list)."),
        mod_functions=({datetime: lambda x: x.isoformat(), date: lambda x: x.isoformat(),
                        time: lambda x: x.isoformat(), "default": lambda x: str(x)}, MutableMapping,
                       lambda x: all((k in ("default", "tuple_keys") or all(isinstance(y, type) for y in (k if
                                     isinstance(k, Iterable) else (k,)))) and callable(v) for k, v in x.items()),
                       "mod_functions must be a dict with types (or tuples of types) as keys and functions as values."),
        value_split=(" ", str),
        return_node=(False, bool)
    )

    def __new__(mcs, name, bases, dct):
        obj = super().__new__(mcs, name, bases, dct)
        for option_name, option in TreeOMeta.__default_options__.items():
            setattr(mcs, option_name, option[0])
        return obj

    def __setattr__(cls, attr, value):
        super(TreeOMeta, cls).__setattr__(attr, value if hasattr(TreeOMeta, attr) or attr in
            ("__abstractmethods__", "_abc_impl") else TreeOMeta.__verify_option__(attr, value))


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
    def get(self: Union[Mapping, Sequence], path="", default=..., **kwargs):
        """Retrieves value from path. If the value doesn't exist, default is returned."""
        TreeO.__verify_kwargs__(kwargs, "get", "return_node", "value_split", "mod")
        node = self.obj if isinstance(self, TreeO) else self
        t_path = path.split(TreeO.__opt__(self, "value_split", **kwargs)) if isinstance(path, str) else tuple(path)
        if path:
            for node_name in t_path:
                try:
                    if isinstance(node, (Mapping, Sequence)):
                        node = node[node_name if isinstance(node, Mapping) else int(node_name)]
                    else:
                        node = TreeO.__opt__(self, "default_value", default_value=default)
                        break
                except (IndexError, ValueError, KeyError):
                    node = TreeO.__opt__(self, "default_value", default_value=default)
                    break
        if not kwargs.get("mod", True):
            node = deepcopy(node)
        return TreeO(node) if isinstance(node, (Mapping, Sequence)) and TreeO.__opt__(self, "return_node", **kwargs) \
            else node

    def __get_parent__(self: Union[MutableMapping, MutableSequence], t_path: tuple, **kwargs):
        """Internal function giving the parent_node"""
        node = self.obj if isinstance(self, TreeO) else self
        list_insert = TreeO.__opt__(self, "list_insert", **kwargs)
        for node_name in t_path[:-1]:
            try:
                if isinstance(node, (Mapping, Sequence)):
                    node = node[node_name if isinstance(node, Mapping) else int(node_name)]
                    if isinstance(node, Sequence):
                        if list_insert == 1:
                            return ...
                        list_insert -= 1
                else:
                    return ...
            except (IndexError, ValueError, KeyError):
                return ...
        return node

    def iter(self: Union[Mapping, Sequence], path="", mod=True):
        """Iterate over all sub-nodes at path

        Returns a list with one tuple for each leaf-node. The tuples contain one value for each node until the leaf."""
        node = TreeO.get(self, path, return_node=False)
        if not mod:
            node = deepcopy(node)
        if isinstance(node, (Mapping, Sequence)):
            return TreeO.__iter_r__(node)
        else:
            return []

    @staticmethod
    def __iter_r__(node):
        iter_list = []
        for k, v in node.items() if isinstance(node, Mapping) else enumerate(node):
            if not isinstance(v, str):
                if isinstance(v, (Mapping, Sequence)):
                    for e in TreeO.__iter_r__(v):
                        iter_list.append((k, *e))
                    continue
                elif isinstance(v, Collection):
                    iter_list.extend(((k, e) for e in v))
                    continue
            iter_list.append((k, v))
        return iter_list

    def set(self: Union[MutableMapping, MutableSequence], value, path, node_types: str = ..., **kwargs):
        """Create (if they don't already exist) all sub-nodes in path, and finally set value at leaf-node

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO.__build_node__(self, value, path, "set", node_types, **kwargs)

    def append(self: Union[MutableMapping, MutableSequence], value, path="", node_types: str = ..., **kwargs):
        """Create (if they don't already exist) all sub-nodes in path, and finally append value to list at leaf-node

        If the leaf-node is a set, tuple or other value it is converted to a list. Then the new value is appended.

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO.__build_node__(self, value, path, "append", node_types, **kwargs)

    def extend(self: Union[MutableMapping, MutableSequence], values: Iterable, path="", node_types: str = ...,
               **kwargs):
        """Create (if they don't already exist) all sub-nodes in path. Then extend list at leaf-node with the new values

        If the leaf-node is a set, tuple or other value it is converted to a list. Then the new values are appended.

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO.__build_node__(self, values, path, "extend", node_types, **kwargs)

    def insert(self: Union[MutableMapping, MutableSequence], index: int, value, path="", node_types: str = ...,
               **kwargs):
        """Create (if they don't already exist) all sub-nodes in path. Insert new value at index in list at leaf-node

        If the leaf-node is a set, tuple or other value it is converted to a list. Then insert new value at index

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO.__build_node__(self, value, path, "insert", node_types, **kwargs, index=index)

    def add(self: Union[MutableMapping, MutableSequence], value, path, node_types: str = ..., **kwargs):
        """Create (if they don't already exist) all sub-nodes in path, and finally add new value to set at leaf-node

        If the leaf-node is a list, tuple or other value it is converted to a list. Then the new values are added.

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO.__build_node__(self, value, path, "add", node_types, **kwargs)

    def update(self: Union[MutableMapping, MutableSequence], values:Iterable, path="", node_types=..., **kwargs):
        """Create (if they don't already exist) all sub-nodes in path, then update set at leaf-node with new values

        If the leaf-node is a list, tuple or other value it is converted to a set. That set is then updated with the new
        values. If the node at path is a dict, and values also is a dict, the node-dict is updated with the new values.

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO.__build_node__(self, values, path, "update", **kwargs)

    def __build_node__(self: Union[MutableMapping, MutableSequence], value, path, action: str, node_types: str = ...,
                       **kwargs):
        if not isinstance(self, (MutableMapping, MutableSequence)):
            raise ValueError(f"Can't modify base object self having the immutable type {type(self).__name__}.")
        TreeO.__verify_kwargs__(kwargs, action, "default_node_type", "list_insert", "value_split", "return_node", "mod",
                                *(("index",) if action == "insert" else ()))
        node_types = TreeO.__opt__(self, "node_types", node_types=node_types)
        obj = self.obj if isinstance(self, TreeO) else self
        if not kwargs.get("mod", True):
            obj = deepcopy(obj)
        if path:
            t_path = path.split(TreeO.__opt__(self, "value_split", **kwargs)) if isinstance(path, str) else tuple(path)
            next_index = TreeO.__try_else__(t_path[0], lambda x: int(x), ...)
            list_insert = TreeO.__opt__(self, "list_insert", **kwargs)
            node = obj
            if isinstance(obj, MutableMapping) and node_types[0:1] == "l" or \
                    isinstance(obj, MutableSequence) and (node_types[0:1] == "d" or next_index is ...):
                raise ValueError(f"Your base object is a {type(obj).__name__}. Due to limitations in how references "
                                 f"work in Python, TreeO can't convert that base-object to a "
                                 f"{'list' if node_types[0:1] == 'l' else 'dict'}, which was requested %s." % (
                                     f"because {t_path[0]} is no numeric list-index"
                                     if isinstance(obj, MutableSequence) and not t_path[0].lstrip("-").isdigit() else
                                     f"by the first character in node_types being {node_types[0:1]}"))
            for i in range(len(t_path)):
                node_key = next_index if isinstance(node, MutableSequence) else t_path[i]
                next_index = TreeO.__try_else__(t_path[i + 1], lambda x: int(x), ...) if i < len(t_path) - 1 else ...
                next_node = list if node_types[i + 1:i + 2] == "l" or not node_types[i + 1:i + 2] and \
                                    TreeO.__opt__(self, "default_node_type", **kwargs) == "l" and \
                                    next_index is not ... else dict
                if isinstance(node, MutableSequence):
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
                            node.insert(node_key, TreeO.__put_value__(..., value, action, **kwargs))
                        else:
                            node[node_key] = TreeO.__put_value__(node[node_key], value, action, **kwargs)
                    else:
                        if list_insert == 1:
                            node.insert(node_key, next_node())
                        else:
                            if not isinstance(node[node_key], (MutableMapping, MutableSequence)) and \
                                    isinstance(node[node_key], Iterable):
                                node[node_key] = dict(node[node_key].items()) if isinstance(node[node_key], Mapping) \
                                    else list(node[node_key])
                            if next_node != node[node_key].__class__ if node_types[i + 1:i + 2] else \
                                    isinstance(node[node_key], MutableSequence) and next_index is ...:
                                node[node_key] = next_node()
                        list_insert -= 1
                        node = node[node_key]
                else:  # isinstance(node, dict)
                    if i == len(t_path) - 1:
                        node[node_key] = TreeO.__put_value__(node.get(node_key, ...), value, action, **kwargs)
                    else:
                        if not isinstance(node.get(node_key), (MutableMapping, MutableSequence)) and \
                                isinstance(node.get(node_key), Iterable):
                            node[node_key] = dict(node[node_key].items()) if isinstance(node[node_key], Mapping) else \
                                list(node[node_key])
                        elif node.get(node_key, TreeOMeta.__Empty__) is TreeOMeta.__Empty__:
                            node[node_key] = next_node()
                        if next_node != node[node_key].__class__ if node_types[i + 1:i + 2] else \
                                isinstance(node[node_key], MutableSequence) and next_index is ...:
                            node[node_key] = next_node()
                        node = node[node_key]
        else:
            if isinstance(obj, MutableMapping) and action == "update" and isinstance(value, Mapping):
                obj.update(value)
            elif isinstance(obj, MutableSequence) and action in ("append", "extend", "insert"):
                if action == "insert":
                    obj.insert(kwargs["index"], value)
                else:
                    getattr(obj, action)(value)
            else:
                raise ValueError(f"Can't {action} value {'to' if action == 'add' else 'in'} base-{type(obj).__name__}.")
        return TreeO(obj) if TreeO.__opt__(self, "return_node", **kwargs) else obj

    @staticmethod
    def __put_value__(node, value, action, **kwargs):
        if action == "set":
            return value
        elif action in ("append", "extend", "insert"):
            if not isinstance(node, MutableSequence):
                if isinstance(node, Iterable):
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
                return dict(value) if isinstance(value, Mapping) else \
                    set(value) if isinstance(value, Iterable) else {value}
            else:
                if not isinstance(node, (MutableSet, MutableMapping)):
                    if isinstance(node, Iterable):
                        node = set(node)
                    else:
                        node = {node}
                elif isinstance(node, MutableMapping) and not isinstance(value, Mapping):
                    raise ValueError(f"Can't update dict with value of type {type(value).__name__} not being a Mapping")
                getattr(node, action)(value)
        return node

    def setdefault(self: Union[MutableMapping, MutableSequence], default=..., path="", node_types=..., **kwargs):
        """Get value at path and return it. If there is no value at path, set default at path, and return default."""
        TreeO.__verify_kwargs__(kwargs, "setdefault", "default_node_type", "list_insert", "value_split")
        t_path = path.split(TreeO.__opt__(self, "value_split", **kwargs)) if isinstance(path, str) else tuple(path)
        parent_node = TreeO.__get_parent__(self, t_path, **kwargs)
        if isinstance(parent_node, (Mapping, Sequence)):
            original_value = TreeO.get(parent_node, t_path[-1], TreeOMeta.__Empty__, return_node=False)
            if original_value is not TreeOMeta.__Empty__:
                return original_value
        default_value = TreeO.__opt__(self, "default_value", default_value=default)
        TreeO.set(self, path, default_value, node_types, **kwargs)
        return default_value

    def mod(self: Union[MutableMapping, MutableSequence], mod_function, path, default=..., node_types: str = ...,
            **kwargs):
        """Modifies the value at path using the function-pointer mod_function

        mod can be used like this TreeO.mod(obj, "kitchen spoon", lambda x: x+1, 1) to count the number of spoons in
        the kitchen. If there is no value to modify, the default value (here 1) will be set at the node.

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        obj = self.obj if isinstance(self, TreeO) else self
        if not kwargs.get("mod", True):
            obj = deepcopy(obj)
        t_path = path.split(TreeO.__opt__(self, "value_split", **kwargs)) if isinstance(path, str) else tuple(path)
        parent_node = TreeO.__get_parent__(self, t_path, **kwargs)
        if isinstance(parent_node, (MutableMapping, MutableSequence)):
            old_value = TreeO.get(parent_node, t_path[-1], TreeOMeta.__Empty__, return_node=False)
            if old_value is not TreeOMeta.__Empty__:
                new_value = mod_function(old_value)
                TreeO.set(parent_node, new_value, t_path[-1], **kwargs)
                return new_value
        default_value = TreeO.__opt__(self, "default_value") if default is ... else default
        TreeO.set(obj, default_value, path, node_types, **kwargs)
        return default_value

    def pop(self: Union[MutableMapping, MutableSequence], path, **kwargs):
        """Deletes the value at path and returns it"""
        TreeO.__verify_kwargs__(kwargs, "pop", "value_split")
        t_path = path.split(TreeO.__opt__(self, "value_split", **kwargs)) if isinstance(path, str) else tuple(path)
        node = self.obj if isinstance(self, TreeO) else self
        for node_name in t_path[:-1]:
            try:
                node = node[node_name if isinstance(node, dict) else int(node_name)]
            except (IndexError, ValueError, KeyError):
                return
        return node.pop(t_path[-1])

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
        if not isinstance(self, (dict, list)):
            raise ValueError(f"Can't modify base object self having the immutable type {type(self).__name__}.")
        TreeO.__verify_kwargs__(kwargs, "ensure_json", "mod_functions", "mod", "value_split")
        node = TreeO.get(self.obj if isinstance(self, TreeO) else self, path, return_node=False, **kwargs)
        if not kwargs.get("mod", True):
            node = deepcopy(node)
        return TreeO.__serialize_r__(node, {**TreeO.__opt__(self, "mod_functions"),
                                            **(TreeOMeta.__verify_option__("mod_functions", mod_functions) if
                                            mod_functions is ... else {})})

    @staticmethod
    def __serialize_r__(node, mod_functions: MutableMapping):
        for k, v in list(node.items() if isinstance(node, MutableMapping) else enumerate(node)):
            ny_k, ny_v = ..., ...
            if not isinstance(k, (bool, float, int, str)) and k is not None:
                if isinstance(k, tuple):
                    if "tuple_keys" in mod_functions:
                        ny_k = mod_functions["tuple_keys"](k)
                    else:
                        raise ValueError('Dicts with composite keys (tuples) are not supported in serialized objects. '
                                         'Use "tuple_keys" to define a specific mod_function for these dict-keys.')
                else:
                    ny_k = TreeO.__serializable_value__(k, mod_functions)
            if isinstance(v, Iterable):
                if isinstance(v, (dict, list)):
                    TreeO.__serialize_r__(v, mod_functions)
                else:
                    ny_v = dict(v.items()) if isinstance(v, Mapping) else list(v)
                    TreeO.__serialize_r__(ny_v, mod_functions)
            elif not isinstance(v, (bool, float, int, str)) and v is not None:
                ny_v = TreeO.__serializable_value__(v, mod_functions)
            if ny_k is not ...:
                node.pop(k)
                node[ny_k] = v if ny_v is ... else ny_v
            elif ny_v is not ...:
                node[k] = ny_v
        return node

    @staticmethod
    def __serializable_value__(value, mod_functions):
        for types, mod_function in mod_functions.items():
            if type(types) is str:
                continue
            if type(value) == types or isinstance(Collection, types) and type(value) in types:
                return mod_function(value)
        return mod_functions["default"](value)

    def __opt__(self: Union[Mapping, Sequence], option_name: str, **kwargs):
        if kwargs.get(option_name, ...) is not ...:
            return TreeO.__verify_option__(option_name, kwargs[option_name])
        return self.__options__[option_name] if isinstance(self, TreeO) and option_name in self.__options__ else \
            getattr(TreeO, option_name)

    @staticmethod
    def __verify_kwargs__(kwargs: dict, function_name, *allowed_kwargs):
        wrong_kwargs = tuple(filter(lambda x: x not in allowed_kwargs, kwargs))
        if wrong_kwargs:
            raise TypeError(f"Unsupported keyword argument{'s' if len(wrong_kwargs) > 1 else ''} in "
                            f"TreeO.{function_name}(): {' '.join(wrong_kwargs)}")

    def keys(self: Union[Mapping, Sequence], path=""):
        """Returns keys for node at path

        If node is iterable but not a dict, the indices are returned. If node is a single value, [0] is returned."""
        obj = TreeO.get(self, path, return_node=False)
        if isinstance(obj, MutableMapping):
            return obj.keys()
        elif isinstance(obj, Collection):
            return [x[0] for x in enumerate(obj)]
        else:
            return

    def values(self: Union[Mapping, Sequence], path=""):
        """Returns values for node at path"""
        obj = TreeO.get(self, path, return_node=False)
        if isinstance(obj, MutableMapping):
            return obj.values()
        else:
            return list(obj)

    def items(self: Union[Mapping, Sequence], path="", mod=True):
        """Returns a list with one tuple for each leaf-node. The tuples have one value for each node until the leaf."""
        return TreeO.iter(self, path, mod)

    def clear(self: Union[Mapping, Sequence], path=""):
        """Removes all elements from node at path."""
        return TreeO.get(self, path, return_node=False).clear()

    def contains(self: Union[Mapping, Sequence], value, path=""):
        """Check if value is present in the node at path. Returns value == node if the node isn't iterable."""
        node = TreeO.get(self, path, return_node=False)
        return value in node if isinstance(node, Collection) else value == node

    def count(self: Union[Mapping, Sequence], path=""):
        """Get the number of child-nodes at path"""
        node = TreeO.get(self, path)
        return len(node) if isinstance(node, Collection) else 1

    def reversed(self: Union[Mapping, Sequence], path=""):
        """Get reversed child-node at path if that node is a list"""
        node = TreeO.get(self, path, return_node=False)
        if isinstance(node, Reversible):
            return reversed(node)
        else:
            raise ValueError(f"Cannot reverse node of type {type(node).__name__}.")

    def reverse(self: Union[MutableMapping, MutableSequence], path="", **kwargs):
        """Reverse child-node at path if that node is a list"""
        TreeO.__verify_kwargs__(kwargs, "reverse", "mod", "return_node")
        obj = self.obj if isinstance(self, TreeO) else self
        if kwargs.get("mod", True):
            obj = deepcopy(obj)
        node = TreeO.get(self, path, **kwargs, return_node=False)
        if isinstance(node, MutableSequence):
            node.reverse()
            return TreeO(obj) if TreeO.__opt__(self, "return_node", **kwargs) else obj
        else:
            raise ValueError(f"Cannot reverse node of type {type(node).__name__}.")

    def popitem(self):
        """This function is not implemented in TreeO"""
        raise NotImplementedError("popitem() is not implemented in TreeO")

    def __init__(self, obj: Union[Mapping, Sequence] = None, mod=True):
        if obj is None:
            obj = [] if TreeO.default_node_type == "l" else {}
        if not mod:
            obj = deepcopy(obj)
        self.obj = obj() if isinstance(obj, TreeO) else obj
        self.__options__ = {}

    def __call__(self):
        return self.obj

    def __getattr__(self, attr):  # Enable dot-notation for getting dict-keys at the top-level
        if attr == "obj":
            return self.obj
        elif hasattr(TreeO, attr):
            return self.__options__.get(attr, getattr(TreeO, attr))
        else:
            return self.get(attr.lstrip(TreeO.__opt__(self, "value_split") if isinstance(attr, str) else attr))

    def __getitem__(self, item):  # Enable [] access for dict-keys at the top-level
        return self.get(item)

    def __setattr__(self, attr, value):  # Enable dot-notation for setting items for dict-keys at the top-level
        if attr in ("obj", "__options__"):
            super(TreeO, self).__setattr__(attr, value)
        elif attr in TreeO.__default_options__:
            self.__options__[attr] = TreeO.__verify_option__(attr, value)
        else:
            self.set(value, attr.lstrip(TreeO.__opt__(self, "value_split") if isinstance(attr, str) else attr))

    def __setitem__(self, path, value):  # Enable [] for setting items for dict-keys at the top-level
        self.set(value, path)

    def __delattr__(self, path):  # Enable dot-notation for deleting items for dict-keys at the top-level
        if hasattr(TreeO, path):
            if path in self.__options__:
                del self.__options__[path]
        else:
            self.pop(path.lstrip(TreeO.__opt__(self, "value_split") if isinstance(path, str) else path))

    def __delitem__(self, path):  # Enable [] for deleting items at dict-keys at the top-level
        self.pop(path)

    def __iter__(self):
        return iter(TreeO.iter(self))

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
        elif isinstance(a, Iterable):
            res = [*a, *(b if isinstance(b, Iterable) else (b,))]
        else:
            raise TypeError(f"Unsupported operand types for +: {type(a).__name__} and {type(b).__name__}")
        return TreeO(res) if TreeO.__opt__(self if isinstance(self, TreeO) else other, "return_node") else res

    def __radd__(self, other):
        return TreeO.__add__(other, self)

    def __sub__(self, other):
        obj = self() if isinstance(self, TreeO) else self
        other = set(other() if isinstance(other, TreeO) else other) if isinstance(other, Iterable) else (other,)
        if isinstance(obj, Mapping):
            res = {k: v for k, v in obj.items() if k in other}
        else:  # isinstance(self(), Sequence):
            res = list(filter(lambda x: x not in other, obj))
        return TreeO(res) if TreeO.__opt__(self if isinstance(self, TreeO) else other, "return_node") else res

    def __rsub__(self, other):
        return TreeO.__sub__(other, self)

    def __mul__(self, times: int):
        if not isinstance(times, int):
            raise TypeError("To use the * (times)-operator, times must be an int")
        if not isinstance(self(), Sequence):
            raise TypeError("Your base-object must a tuple or list to get multiplied.")
        return TreeO(self() * times) if TreeO.__opt__(self, "return_node") else self() * times

    def __rmul__(self, other):
        return TreeO.__mul__(self, other)

    def __reversed__(self: Union[MutableMapping, MutableSequence]):
        return TreeO.reversed(self)
