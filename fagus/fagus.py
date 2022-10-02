"""Base-module that contains the :obj:`~fagus.Fagus`-class"""


import copy as cp
from collections.abc import (
    Collection,
    Mapping,
    Sequence,
    Set,
    MutableMapping,
    MutableSequence,
    Reversible,
    Iterable,
    MutableSet,
    Container,
)
from datetime import datetime, date, time
from typing import Union, Tuple, Any, Optional, List, Callable

from .utils import (
    FagusMeta,
    _None,
    INF,
    _filter_r,
    _copy_node,
    _is,
    _copy_any,
)
from .filters import Fil
from .iterators import FagusIterator


class Fagus(MutableMapping, MutableSequence, MutableSet, metaclass=FagusMeta):
    """Fagus is a wrapper-class for complex, nested objects of dicts and lists in Python

    Fagus can be used as an object by instantiating it, but it's also possible to use all methods statically without
    even an object, so that a = {}; Fagus.set(a, "top med", 1) and a = Fagus({}); a.set(1, "top med") do the same.

    The root node is always modified directly. If you don't want to change the root node, all the functions where it
    makes sense support to rather modify a copy, and return that modified copy using the copy-parameter.

    Several parameters used in functions in Fagus work as options so that you don't have to specify them each time you
    run a function. In the docstrings, these options are marked with a \\*, e.g. the fagus parameter is an option.
    Options can be specified at three levels with increasing precedence: at class-level (Fagus.fagus = True), at
    object-level (a = Fagus(), a.fagus = True) and in each function-call (a.get("b", fagus=True)). If you generally want
    to change an option, change it at class-level - all objects in that file will inherit this option. If you want to
    change the option specifically for one object, change the option at object-level. If you only want to change the
    option for one single run of a function, put it as a function-parameter. More thorough examples of options can be
    found in README.md.
    """

    def __init__(
        self,
        root: Collection = None,
        node_types: str = ...,
        list_insert: int = ...,
        path_split: str = ...,
        fagus: bool = ...,
        default_node_type: str = ...,
        default=...,
        if_=...,
        iter_fill=...,
        mod_functions: Mapping = ...,
        copy: bool = False,
    ):
        """Constructor for Fagus, a wrapper-class for complex, nested objects of dicts and lists in Python

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            root: object (like dict / list) to wrap Fagus around. If this is None, an empty node of the type
                default_node_type will be used. Default None
            node_types: \\* Can be used to manually define if the nodes along path are supposed to be (l)ists or
                (d)icts. E.g. "dll" to create a dict at level 1, and lists at level 2 and 3. " " can also be used -
                space doesn't enforce a node-type like d or l. For " ", existing nodes are traversed if possible,
                otherwise default_node_type is used to create new nodes. Default "", interpreted as " " at each level.
            list_insert: \\* Level at which a new node shall be inserted into the list instead of traversing the
                existing node in the list at that index. See README
            path_split: \\* used to split path into a list if path is a string, default " "
            fagus: \\* this option is used to determine whether nodes in the returned object should be returned as
                Fagus-objects. This can be useful e.g. if you want to use Fagus in an iteration. Check the particular
                function you want to use for a more thorough explanation of what this does in each case
            default_node_type: \\* determines if new nodes by default should be created as (d)ict or (l)ist. Must be
                either "d" or "l", default "d"
            default: \\* ~ is used in get and other functions if a path doesn't exist
            if_: \\* only set value if it meets the condition specified here, otherwise do nothing. The condition can be
                a lambda, any value or a tuple of accepted values. Default _None (don't check value)
            iter_fill: \\* Fill up tuples with iter_fill (can be any object, e.g. None) to ensure that all the tuples
                iter() returns are exactly max_items long. See iter()
            copy: ~ creates a copy of the root node before Fagus is initialized. Makes sure that changes on this Fagus
                won't modify the root node that was passed here itself. Default False
        """
        if root is None:
            root = [] if Fagus.default_node_type == "l" or default_node_type == "l" else {}
        if copy:
            root = Fagus.__copy__(root)
        if isinstance(root, Fagus):
            self.root = root()
            self._options = None if root._options is None else root._options.copy()
        else:
            self.root = root
            self._options = None
        self.options = self.__options  # Renaming __options to options. This is done at runtime to prevent overriding
        del self.__options  # options in FagusMeta, which is still supposed to run if Fagus.options() is called
        for kw, value in locals().copy().items():
            if kw not in ("copy", "self", "root") and value is not ...:
                setattr(self, kw, value)

    def get(
        self: Collection,
        path: Any = "",
        default=...,
        fagus: bool = ...,
        copy: bool = False,
        path_split: str = ...,
    ) -> Any:
        """Retrieves value at path. If the value doesn't exist, default is returned.

        To get "hello" from x = Fagus({"a": ["b", {"c": "d"}], e: ["f", "g"]}), you can use x[("a", 1, "c")]. The tuple
        ("a", 1, "c") is the path-parameter that is used to traverse x. At first, the list at "a" is picked in the
        top-most dict, and then the 2nd element {"c": "d"} is picked from that list. Then, "d" is picked from {"c": "d"}
        and returned. The path-parameter can be a tuple or list, the keys must be either integers for lists, or any
        hashable objects for dicts. For convenience, the keys can also be put in a single string separated by
        path_split (default " "), so a["a 1 c"] also returns "d".

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            path: List/Tuple of key-values to recursively traverse self. Can also be specified as string, that is split
                into a tuple using path_split
            default: \\* returned if path doesn't exist in self
            fagus: \\* returns a Fagus-object if the value at path is a list or dict
            copy: Option to return a copy of the returned value. The default behaviour is that if there are subnodes
                (dicts, lists) in the returned values, and you make changes to these nodes, these changes will also be
                applied in the root node from which values() was called. If you want the returned values to be
                independent, use copy to get a shallow copy of the returned value
            path_split: \\* used to split path into a list if path is a str, default " "

        Returns:
            the value if the path exists, or default if it doesn't exist
        """
        node = self.root if isinstance(self, Fagus) else self
        if isinstance(path, str):
            t_path = path.split(Fagus._opt(self, "path_split", path_split)) if path else ()
        else:
            t_path = tuple(path) if _is(path, Collection) else (path,)
        if t_path:
            for node_name in t_path:
                try:
                    if _is(node, Mapping, Sequence):
                        node = node[node_name if isinstance(node, Mapping) else int(node_name)]
                    else:
                        node = Fagus._opt(self, "default", default)
                        break
                except (IndexError, ValueError, KeyError):
                    node = Fagus._opt(self, "default", default)
                    break
        if copy:
            node = _copy_any(node)
        return Fagus.child(self, node) if _is(node, Collection) and Fagus._opt(self, "fagus", fagus) else node

    def iter(
        self: Collection,
        max_depth: int = INF,
        path: Any = "",
        filter_: Fil = None,
        fagus: bool = ...,
        iter_fill=...,
        select: Union[int, Iterable] = None,
        copy: bool = False,
        iter_nodes: bool = ...,
        filter_ends: bool = False,
        path_split: str = ...,
    ) -> "FagusIterator":
        """Recursively iterate through Fagus-object, starting at path

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            max_depth: Can be used to limit how deep the iteration goes. Example: a = {"a": ["b", ["c", "d"]], "e": "f"}
                If max_depth is sys.max_size, all the nodes are traversed: [("a", "b", "c"), ("a", "b", "d"]),
                ("e", "f")]. If max_depth is 1, iter returns [("a", "b", ["c", "d"]), ("e", "f")], so ["c", "d"] is not
                iterated through but returned as a node. If max_depth is 0, iter returns [("a", ["b", ["c", "d"]]),
                ("e", "f")], effectively the same as dict.items(). Default sys.maxitems (iterate as deeply as possible)
                A negative number (e.g. -1) is treated as sys.maxitems.
            path: Start iterating at path. Internally calls get(path), and iterates on the node get returns. See get()
            filter_: Only iterate over specific nodes defined using TFilter (see README.md and TFilter for more info)
            fagus: \\* If the leaf in the tuple is a dict or list, return it as a Fagus-object. This option has no
                effect if max_items is sys.maxitems.
            iter_fill: \\* Fill up tuples with iter_fill (can be any object, e.g. None) to ensure that all the tuples
                iter() returns are exactly max_items long. This can be useful if you want to unpack the keys / leaves
                from the tuples in a loop, which fails if the count of items in the tuples varies. This option has no
                effect if max_items is -1. The default value is ..., meaning that the tuples are not filled, and the
                length of the tuples can vary. See README.md for a more thorough example.
            select: Extract only some specified values from the tuples. E.g. if ~ is -1, only the leaf-values are
                returned. ~ can also be a list of indices. Default None (don't reduce the tuples)
            copy: Iterate on a shallow-copy to make sure that you can edit root node without disturbing the iteration
            iter_nodes: \\* includes the traversed nodes into the resulting tuples, order is then:
                node1, key1, node2, key2, ..., leaf_value
            filter_ends: Affects the end dict/list that is returned if max_items is used. Normally, filters are not
                applied on that end node. If you would like to get the end node filtered too, set this to True. If this
                is set to True, the last nodes will always be copies (if unfiltered they are references)
            path_split: \\* used to split path into a list if path is a str, default " "

        Returns:
            FagusIterator with one tuple for each leaf-node, containing the keys of the parent-nodes until the leaf
        """
        iter_fill = Fagus._opt(self, "iter_fill", iter_fill)
        node = Fagus.get(self, path, (), True, copy and iter_fill, path_split)
        if not _is(node, Collection) or isinstance(filter_, Fil) and not filter_.match_extra_filters(node):
            node = Fagus.child(self, ())
        return FagusIterator(
            node,
            max_depth,
            filter_,
            Fagus._opt(self, "fagus", fagus),
            iter_fill,
            select,
            Fagus._opt(self, "iter_nodes", iter_nodes),
            copy and not iter_fill,
            filter_ends,
        )

    def filter(
        self: Collection,
        filter_: Fil,
        path: Any = "",
        fagus: bool = ...,
        copy: bool = False,
        default=...,
        path_split: str = ...,
    ) -> Collection:
        """Filters self, only keeping the nodes that pass the filter

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            filter_: TFilter-object in which the filtering-criteria are specified
            path: at this point in self, the filtering will start (apply filter\\_ relatively from this point).
                Default "", meaning that the root node is filtered, see get() and README for examples
            fagus: \\* return the filtered self as Fagus-object (default is just to return the filtered node)
            copy: Create a copy and filter on that copy. Default is to modify the self directly
            default: \\* returned if path doesn't exist in self, or the value at path can't be filtered
            path_split: \\* used to split path into a list if path is a str, default " "

        Returns:
            the filtered object, starting at path

        Raises:
            TypeError: if the root node needs to be modified and isn't modifiable (e.g. tuple or frozenset)
        """
        if isinstance(path, str):
            l_path = path.split(Fagus._opt(self, "path_split", path_split)) if path else []
        else:
            l_path = list(path) if _is(path, Collection) else [path]
        if copy:
            parent_node = Fagus.get(self, l_path[:-1], _None, False, copy, path_split)
        else:
            parent_node = Fagus._get_mutable_node(self, l_path)
        node = _None if parent_node is _None else Fagus.get(parent_node, l_path[-1:], _None, False)
        if node is _None or not _is(node, Collection):
            filtered = Fagus._opt(self, "default", default)
        else:
            filtered = _filter_r(node, copy, filter_)
            if not filter_.match_extra_filters(node):
                filtered.clear()
            if not copy:
                if path:
                    parent_node[int(l_path[-1]) if isinstance(parent_node, Sequence) else l_path[-1]] = filtered
                else:
                    parent_node.clear()
                    getattr(parent_node, "extend" if isinstance(parent_node, MutableSequence) else "update")(filtered)
        return Fagus.child(self, filtered) if Fagus._opt(self, "fagus", fagus) else filtered

    def split(
        self: Collection,
        filter_: Fil,
        path: Any = "",
        fagus: bool = ...,
        copy: bool = False,
        default=...,
        path_split: str = ...,
    ) -> Union[Tuple[Collection, Collection], Tuple[Any, Any]]:
        """Splits self into nodes that pass the filter, and nodes that don't pass the filter

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            filter_: TFilter-object in which the filtering-criteria are specified
            path: at this position in self, the splitting will start (apply filter\\_ relatively from this point).
                Default "", meaning that the root node is split, see get() and README for examples
            fagus: \\* return the filtered self as Fagus-object (default is just to return the filtered node)
            copy: Create a copy and filter on that copy. Default is to modify the object directly
            default: \\* returned if path doesn't exist in self, or the
            path_split: \\* used to split path into a list if path is a str, default " "

        Returns:
            a tuple, where the first element is the nodes that pass the filter, and the second element is the nodes that
            don't pass the filter

        Raises:
            TypeError: if the root node needs to be modified and isn't modifiable (e.g. tuple or frozenset)
        """
        if isinstance(path, str):
            l_path = path.split(Fagus._opt(self, "path_split", path_split)) if path else []
        else:
            l_path = list(path) if _is(path, Collection) else [path]
        if copy:
            parent_node = Fagus.get(self, l_path[:-1], _None, False, copy, path_split)
        else:
            parent_node = Fagus._get_mutable_node(self, l_path)
        node = _None if parent_node is _None else Fagus.get(parent_node, l_path[-1:], _None, False)
        if node is _None or not _is(node, Collection):
            filter_in, filter_out = 2 * (Fagus._opt(self, "default", default),)
        else:
            filter_in, filter_out = Fagus._split_r(node, copy, filter_)
            if not filter_.match_extra_filters(node):
                filter_in.clear()
                filter_out = node
            if not copy:
                if path:
                    parent_node[int(l_path[-1]) if isinstance(parent_node, Sequence) else l_path[-1]] = filter_in
                else:
                    parent_node.clear()
                    getattr(parent_node, "extend" if isinstance(parent_node, MutableSequence) else "update")(filter_in)
        return (
            (Fagus.child(self, filter_in), Fagus.child(self, filter_out))
            if Fagus._opt(self, "fagus", fagus) and _is(filter_in, Collection)
            else (filter_in, filter_out)
        )

    @staticmethod
    def _split_r(
        node: Collection, copy: bool, filter_: Optional[Fil], index: int = 0
    ) -> Tuple[Union[MutableMapping, MutableSequence, MutableSet], Union[MutableMapping, MutableSequence, MutableSet]]:
        """Internal recursive method that facilitates filtering

        Args:
            node: the node to filter
            copy: creates copies instead of directly referencing nodes included in the filter
            filter_: TFilter-object in which the filtering-criteria are specified
            index: index in the current filter-object

        Returns:
            the filtered node
        """
        if isinstance(node, Mapping):
            filter_in, filter_out, action, match_key = {}, {}, None, filter_.match if filter_ else None
        elif isinstance(node, Sequence):
            filter_in, filter_out, action, match_key = [], [], "append", filter_.match_list if filter_ else None
        else:
            filter_in, filter_out, action, match_key = set(), set(), "add", None
        for k, v in node.items() if isinstance(node, Mapping) else enumerate(node):
            v_in, v_out = _None, _None
            match_k = match_key(k, index, len(node)) if callable(match_key) else (True, filter_, index + 1)
            match_v = False
            if match_k[0]:
                if match_k[1] is None:
                    match_v = True
                elif _is(v, Collection):
                    if match_k[1].match_extra_filters(v, match_k[2]):
                        v_in, v_out = Fagus._split_r(v, copy, *match_k[1:])
                        match_v = bool(v) == bool(v_in)
                else:
                    match_v, *_ = match_k[1].match(v, match_k[2])
                if match_v or v_in is not _None:
                    if v_in is _None:
                        v_in = v
                    if action:
                        getattr(filter_in, action)(_copy_any(v_in) if copy else v_in)
                    else:
                        filter_in[k] = _copy_any(v_in) if copy else v_in
            if not match_v or v_out is not _None:
                if v_out is _None:
                    v_out = v
                elif bool(v) != bool(v_out):
                    continue
                if action:
                    getattr(filter_out, action)(_copy_any(v_out) if copy else v_out)
                else:
                    filter_out[k] = _copy_any(v_out) if copy else v_out
        return filter_in, filter_out

    def set(
        self: Collection,
        value,
        path: Iterable,
        node_types: str = ...,
        list_insert: int = ...,
        path_split: str = ...,
        fagus: bool = ...,
        if_: Any = ...,
        default_node_type: str = ...,
        copy: bool = False,
    ) -> Collection:
        """Create (if they don't already exist) all sub-nodes in path, and finally set value at leaf-node

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            value: ~ is placed at path, after creating new nodes if necessary. An existing value at path is overwritten
            path: List/Tuple of key-values that are traversed in self. If no nodes exist at the keys, new nodes are
                created. Can also be specified as a string, that is split into a tuple using path_split. See get()
            node_types: \\* Can be used to manually define if the nodes along path are supposed to be (l)ists or
                (d)icts. E.g. "dll" to create a dict at level 1, and lists at level 2 and 3. " " can also be used -
                space doesn't enforce a node-type like d or l. For " ", existing nodes are traversed if possible,
                otherwise default_node_type is used to create new nodes. Default "", interpreted as " " at each level.
            list_insert: \\* Level at which a new node shall be inserted into the list instead of traversing the
                existing node in the list at that index. See README
            path_split: \\* used to split path into a list if path is a string, default " "
            fagus: \\* return self as a Fagus-object if it is a node (tuple / list / dict), default False
            if_: \\* only set value if it meets the condition specified here, otherwise do nothing. The condition can be
                a lambda, any value or a tuple of accepted values. Default _None (don't check value)
            default_node_type: \\* determines if new nodes by default should be created as (d)ict or (l)ist. Must be
                either "d" or "l", default "d"
            copy: if this is set, a copy of self is modified and then returned (thus self is not modified)

        Returns:
            self as a node if fagus is set, or a modified copy of self if copy is set

        Raises:
            ValueError: if it isn't possible to parse an int-index from the provided key in a position where node-types
                defines that the node shall be a list (if node-types is not l, the node will be replaced with a dict)
            TypeError: if the root node needs to be modified and isn't modifiable (e.g. tuple or frozenset)
        """
        return Fagus._build_node(
            self, value, path, "set", node_types, list_insert, path_split, fagus, if_, default_node_type, copy
        )

    def append(
        self: Collection,
        value,
        path: Any = "",
        node_types: str = ...,
        list_insert: int = ...,
        path_split: str = ...,
        fagus: bool = ...,
        if_: Any = ...,
        default_node_type: str = ...,
        copy: bool = False,
    ) -> Collection:
        """Create (if they don't already exist) all sub-nodes in path, and finally append value to a list at leaf-node

        If the leaf-node is a set, tuple or other value it is converted to a list. Then the new value is appended.

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            value: ~ is appended to list at path, after creating new nodes along path as necessary
            path: List/Tuple of key-values that are traversed in self. If no nodes exist at the keys, new nodes are
                created. Can also be specified as a string, that is split into a tuple using path_split. See get()
            node_types: \\* Can be used to manually define if the nodes along path are supposed to be (l)ists or
                (d)icts. E.g. "dll" to create a dict at level 1, and lists at level 2 and 3. " " can also be used -
                space doesn't enforce a node-type like d or l. For " ", existing nodes are traversed if possible,
                otherwise default_node_type is used to create new nodes. Default "", interpreted as " " at each level.
            list_insert: \\* Level at which a new node shall be inserted into the list instead of traversing the
                existing node in the list at that index. See README
            path_split: \\* used to split path into a list if path is a string, default " "
            fagus: \\* return self as a Fagus-object if it is a node (tuple / list / dict), default False
            if_: \\* only append value if it meets the condition specified here, otherwise do nothing. The condition can
                be a lambda, any value or a tuple of accepted values. Default _None (don't check value)
            default_node_type: \\* determines if new nodes by default should be created as (d)ict or (l)ist. Must be
                either "d" or "l", default "d"
            copy: if this is set, a copy of self is modified and then returned (thus self is not modified)

        Returns:
            self as a node if fagus is set, or a modified copy of self if copy is set

        Raises:
            ValueError: if it isn't possible to parse an int-index from the provided key in a position where node-types
                defines that the node shall be a list (if node-types is not l, the node will be replaced with a dict)
            TypeError: if path is empty and the root node is not a list (can't append to a dict, tuple or set) or the
                root node needs to be modified and isn't modifiable (e.g. tuple or frozenset)
        """
        return Fagus._build_node(
            self, value, path, "append", node_types, list_insert, path_split, fagus, if_, default_node_type, copy
        )

    def extend(
        self: Collection,
        values: Iterable,
        path: Any = "",
        node_types: str = ...,
        list_insert: int = ...,
        path_split: str = ...,
        fagus: bool = ...,
        if_: Any = ...,
        default_node_type: str = ...,
        copy: bool = False,
    ) -> Collection:
        """Create (if they don't already exist) all sub-nodes in path. Then extend list at leaf-node with the new values

        If the leaf-node is a set, tuple or other value it is converted to a list, which is extended with the new values

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            values: the list at path is extended with ~, after creating new nodes along path as necessary
            path: List/Tuple of key-values that are traversed in self. If no nodes exist at the keys, new nodes are
                created. Can also be specified as a string, that is split into a tuple using path_split. See get()

            node_types: \\* Can be used to manually define if the nodes along path are supposed to be (l)ists or
                (d)icts. E.g. "dll" to create a dict at level 1, and lists at level 2 and 3. " " can also be used -
                space doesn't enforce a node-type like d or l. For " ", existing nodes are traversed if possible,
                otherwise default_node_type is used to create new nodes. Default "", interpreted as " " at each level.
            list_insert: \\* Level at which a new node shall be inserted into the list instead of traversing the
                existing node in the list at that index. See README
            path_split: \\* used to split path into a list if path is a string, default " "
            fagus: \\* return self as a Fagus-object if it is a node (tuple / list / dict), default False
            if_: \\* only extend with values if they meet the condition specified here, otherwise do nothing. The
                condition can be a lambda, any value or a tuple of accepted values. Default _None (don't check values)
            default_node_type: \\* determines if new nodes by default should be created as (d)ict or (l)ist. Must be
                either "d" or "l", default "d"
            copy: if this is set, a copy of self is modified and then returned (thus self is not modified)

        Returns:
            self as a node if fagus is set, or a modified copy of self if copy is set

        Raises:
            ValueError: if it isn't possible to parse an int-index from the provided key in a position where node-types
                defines that the node shall be a list (if node-types is not l, the node will be replaced with a dict)
            TypeError: if path is empty and the root node is not a list (can't extend a dict, tuple or set) or the
                root node needs to be modified and isn't modifiable (e.g. tuple or frozenset)
        """
        return Fagus._build_node(
            self, values, path, "extend", node_types, list_insert, path_split, fagus, if_, default_node_type, copy
        )

    def insert(
        self: Collection,
        index: int,
        value,
        path: Any = "",
        node_types: str = ...,
        list_insert: int = ...,
        path_split: str = ...,
        fagus: bool = ...,
        if_: Any = ...,
        default_node_type: str = ...,
        copy: bool = False,
    ) -> Collection:
        """Create (if they don't already exist) all sub-nodes in path. Insert new value at index in list at leaf-node

        If the leaf-node is a set, tuple or other value it is converted to a list, in which the new value is inserted at
        index

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            index: ~ at which the value shall be inserted in the list at path
            value: ~ is inserted at index into list at path, after creating new nodes along path as necessary
            path: List/Tuple of key-values that are traversed in self. If no nodes exist at the keys, new nodes are
                created. Can also be specified as a string, that is split into a tuple using path_split. See get()
            node_types: \\* Can be used to manually define if the nodes along path are supposed to be (l)ists or
                (d)icts. E.g. "dll" to create a dict at level 1, and lists at level 2 and 3. " " can also be used -
                space doesn't enforce a node-type like d or l. For " ", existing nodes are traversed if possible,
                otherwise default_node_type is used to create new nodes. Default "", interpreted as " " at each level.
            list_insert: \\* Level at which a new node shall be inserted into the list instead of traversing the
                existing node in the list at that index. See README
            path_split: \\* used to split path into a list if path is a string, default " "
            fagus: \\* return self as a Fagus-object if it is a node (tuple / list / dict), default False
            if_: \\* only insert value if it meets the condition specified here, otherwise do nothing. The condition can
                be a lambda, any value or a tuple of accepted values. Default _None (don't check value)
            default_node_type: \\* determines if new nodes by default should be created as (d)ict or (l)ist. Must be
                either "d" or "l", default "d"
            copy: if this is set, a copy of self is modified and then returned (thus self is not modified)

        Returns:
            self as a node if fagus is set, or a modified copy of self if copy is set

        Raises:
            ValueError: if it isn't possible to parse an int-index from the provided key in a position where node-types
                defines that the node shall be a list (if node-types is not l, the node will be replaced with a dict)
            TypeError: if path is empty and the root node is not a list (can't insert into dict, tuple or set) or the
                root node needs to be modified and isn't modifiable (e.g. tuple or frozenset)
        """
        return Fagus._build_node(
            self,
            value,
            path,
            "insert",
            node_types,
            list_insert,
            path_split,
            fagus,
            if_,
            default_node_type,
            copy,
            index,
        )

    def add(
        self: Collection,
        value,
        path: Any = "",
        node_types: str = ...,
        list_insert: int = ...,
        path_split: str = ...,
        fagus: bool = ...,
        if_: Any = ...,
        default_node_type: str = ...,
        copy: bool = False,
    ) -> Collection:
        """Create (if they don't already exist) all sub-nodes in path, and finally add new value to set at leaf-node

        If the leaf-node is a list, tuple or other value it is converted to a set, to which the new value is added

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            value: ~ is added to set at path, after creating new nodes along path as necessary
            path: List/Tuple of key-values that are traversed in self. If no nodes exist at the keys, new nodes are
                created. Can also be specified as a string, that is split into a tuple using path_split. See get()
            node_types: \\* Can be used to manually define if the nodes along path are supposed to be (l)ists or
                (d)icts. E.g. "dll" to create a dict at level 1, and lists at level 2 and 3. " " can also be used -
                space doesn't enforce a node-type like d or l. For " ", existing nodes are traversed if possible,
                otherwise default_node_type is used to create new nodes. Default "", interpreted as " " at each level.
            list_insert: \\* Level at which a new node shall be inserted into the list instead of traversing the
                existing node in the list at that index. See README
            path_split: \\* used to split path into a list if path is a string, default " "
            fagus: \\* return self as a Fagus-object if it is a node (tuple / list / dict), default False
            if_: \\* only add value if it meets the condition specified here, otherwise do nothing. The condition can be
                a lambda, any value or a tuple of accepted values. Default _None (don't check value)
            default_node_type: \\* determines if new nodes by default should be created as (d)ict or (l)ist. Must be
                either "d" or "l", default "d"
            copy: if this is set, a copy of self is modified and then returned (thus self is not modified)

        Returns:
            self as a node if fagus is set, or a modified copy of self if copy is set

        Raises:
            ValueError: if it isn't possible to parse an int-index from the provided key in a position where node-types
                defines that the node shall be a list (if node-types is not l, the node will be replaced with a dict)
            TypeError: if path is empty and the root node is not a set (can't add to list or dict) or the root node
                needs to be modified and isn't modifiable (e.g. tuple or frozenset)
        """
        return Fagus._build_node(
            self, value, path, "add", node_types, list_insert, path_split, fagus, if_, default_node_type, copy
        )

    def update(
        self: Collection,
        values: Iterable,
        path: Any = "",
        node_types: str = ...,
        list_insert: int = ...,
        path_split: str = ...,
        fagus: bool = ...,
        if_: Any = ...,
        default_node_type: str = ...,
        copy: bool = False,
    ) -> Collection:
        """Create (if they don't already exist) all sub-nodes in path, then update set at leaf-node with new values

        If the leaf-node is a list, tuple or other value it is converted to a set. That set is then updated with the new
        values. If the node at path is a dict, and values also is a dict, the node-dict is updated with the new values.

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            values: the set/dict at path is updated with ~, after creating new nodes along path as necessary
            path: List/Tuple of key-values that are traversed in self. If no nodes exist at the keys, new nodes are
                created. Can also be specified as a string, that is split into a tuple using path_split. See get()
            node_types: \\* Can be used to manually define if the nodes along path are supposed to be (l)ists or
                (d)icts. E.g. "dll" to create a dict at level 1, and lists at level 2 and 3. " " can also be used -
                space doesn't enforce a node-type like d or l. For " ", existing nodes are traversed if possible,
                otherwise default_node_type is used to create new nodes. Default "", interpreted as " " at each level.
            list_insert: \\* Level at which a new node shall be inserted into the list instead of traversing the
                existing node in the list at that index. See README
            path_split: \\* used to split path into a list if path is a string, default " "
            fagus: \\* return self as a Fagus-object if it is a node (tuple / list / dict), default False
            if_: \\* only update with values if they meet the condition specified here, otherwise do nothing. The
                condition can be a lambda, any value or a tuple of accepted values. Default _None (don't check values)
            default_node_type: \\* determines if new nodes by default should be created as (d)ict or (l)ist. Must be
                either "d" or "l", default "d"
            copy: if this is set, a copy of self is modified and then returned (thus self is not modified)

        Returns:
            self as a node if fagus is set, or a modified copy of self if copy is set

        Raises:
            ValueError: if it isn't possible to parse an int-index from the provided key in a position where node-types
                defines that the node shall be a list (if node-types is not l, the node will be replaced with a dict)
            TypeError: if path is empty and the root node is not a set or dict (can't update list) or the root node
                needs to be modified and isn't modifiable (e.g. tuple or frozenset)
        """
        return Fagus._build_node(
            self, values, path, "update", node_types, list_insert, path_split, fagus, if_, default_node_type, copy
        )

    def _build_node(
        self: Collection,
        value,
        path,
        action: str,
        node_types: str = ...,
        list_insert: int = ...,
        path_split: str = ...,
        fagus: bool = ...,
        if_: Any = ...,
        default_node_type: str = ...,
        copy: bool = False,
        index: int = ...,
    ) -> Collection:
        """Internal function that is used to _build all necessary subnodes in path"""
        root = self.root if isinstance(self, Fagus) else self
        if_ = Fagus._opt(self, "if_", if_)
        if if_ is not _None and not (
            if_(value) if callable(if_) else (value in if_ if _is(if_, Container) else if_ == value)
        ):
            return Fagus.child(self, root) if Fagus._opt(self, "fagus", fagus) else root
        node_types = Fagus._opt(self, "node_types", node_types)
        if copy:
            root = Fagus.__copy__(root)
        node = root
        if isinstance(path, str):
            l_path = path.split(Fagus._opt(self, "path_split", path_split)) if path else []
        else:
            l_path = list(path) if _is(path, Collection) else [path]
        if l_path:
            try:
                next_index = int(l_path[0])
            except (ValueError, TypeError):
                next_index = _None
            list_insert = Fagus._opt(self, "list_insert", list_insert)
            default_node_type = Fagus._opt(self, "default_node_type", default_node_type)
            nodes = [root]
            for i in range(len(l_path)):
                is_list = _is(node, Sequence)
                if is_list:
                    if next_index is _None:
                        raise ValueError(f"Can't parse numeric list-index from {l_path[i]}.")
                    node_key = next_index
                else:
                    node_key = l_path[i]
                try:
                    next_index = int(l_path[i + 1]) if i < len(l_path) - 1 else _None
                except (ValueError, TypeError):
                    next_index = _None
                next_node = (
                    Sequence
                    if node_types[i : i + 1] == "l"
                    or not node_types[i : i + 1].strip()
                    and default_node_type == "l"
                    and next_index is not _None
                    else Mapping
                )
                if is_list:
                    l_path[i] = node_key
                    if node_key >= len(node) and list_insert:
                        if nodes:
                            node = Fagus._ensure_mutable_node(nodes, l_path[: i + 1])
                            nodes.clear()
                        node.append([] if next_node is Sequence else {})
                        node_key = -1
                    elif node_key < -len(node):
                        if nodes:
                            node = Fagus._ensure_mutable_node(nodes, l_path[: i + 1])
                            nodes.clear()
                        node.insert(0, [] if next_node is Sequence else {})
                        node_key = 0
                    if i == len(l_path) - 1:
                        if nodes:
                            node = Fagus._ensure_mutable_node(nodes, l_path[: i + 1])
                            nodes.clear()
                        if list_insert <= 0:
                            node.insert(node_key, Fagus._put_value(_None, value, action, index))
                        else:
                            node[node_key] = Fagus._put_value(node[node_key], value, action, index)
                    else:
                        if list_insert <= 0:
                            if nodes:
                                node = Fagus._ensure_mutable_node(nodes, l_path[: i + 1])
                                nodes.clear()
                            node.insert(node_key, [] if next_node is Sequence else {})
                            list_insert = INF
                        else:
                            next_node_type = (
                                Mapping
                                if isinstance(node[node_key], Mapping)
                                else (Sequence if _is(node[node_key], Sequence) else _None)
                            )
                            if next_node_type is _None or (
                                next_node != next_node_type
                                if node_types[i : i + 1].strip()
                                else next_node_type is Sequence and next_index is _None
                            ):
                                if nodes:
                                    node = Fagus._ensure_mutable_node(nodes, l_path[: i + 1])
                                    nodes.clear()
                                node[node_key] = [] if next_node is Sequence else {}
                elif isinstance(node, Mapping):  # isinstance(node, dict)
                    if i == len(l_path) - 1:
                        if nodes:
                            node = Fagus._ensure_mutable_node(nodes, l_path[: i + 1])
                            nodes.clear()
                        node[node_key] = Fagus._put_value(node.get(node_key, _None), value, action, index)
                    else:
                        next_value = node.get(node_key, _None)
                        next_node_type = (
                            Mapping
                            if isinstance(next_value, Mapping)
                            else (Sequence if _is(next_value, Sequence) else _None)
                        )
                        if next_node_type is _None or (
                            next_node != next_node_type
                            if node_types[i : i + 1].strip()
                            else next_node_type is Sequence and next_index is _None
                        ):
                            if nodes:
                                node = Fagus._ensure_mutable_node(nodes, l_path[: i + 1])
                                nodes.clear()
                            node[node_key] = [] if next_node is Sequence else {}
                node = node[node_key]
                if nodes:
                    nodes.append(node)
                list_insert -= 1
        else:
            if not _is(root, MutableMapping, MutableSequence, MutableSet):
                raise TypeError(f"Can't modify root node self having the immutable type {type(self).__name__}.")
            if isinstance(root, MutableMapping) and action == "update":
                root.update(value)
            elif isinstance(root, MutableSequence) and action in ("append", "extend", "insert"):
                if action == "insert":
                    root.insert(index, value)
                else:
                    getattr(root, action)(value)
            elif isinstance(root, MutableSet) and action in ("add", "update"):
                getattr(root, action)(value)
            elif not action == "parent":
                raise TypeError(
                    f"Can't {action} value {'to' if action in ('add', 'append') else 'in'} root {type(root).__name__}."
                )
        return Fagus.child(self, root) if Fagus._opt(self, "fagus", fagus) else root

    @staticmethod
    def _put_value(node: Union[Collection, type], value, action: str, index: int):
        """internal function that sets, appends or adds value as the last step in building a node"""
        if action == "set":
            return value
        if action in ("append", "extend", "insert"):
            if not _is(node, MutableSequence):
                if _is(node, Iterable):
                    node = list(node)
                elif node is _None:
                    node = []
                else:
                    node = [node]
            if action == "insert":
                node.insert(index, value)
            else:
                getattr(node, action)(value)
        elif action in ("add", "update"):
            if node is _None:
                return dict(value) if isinstance(value, Mapping) else set(value) if _is(value, Iterable) else {value}
            else:
                if not isinstance(node, (MutableSet, MutableMapping)):
                    if _is(node, Iterable):
                        node = set(node)
                    else:
                        node = {node}
                elif isinstance(node, MutableMapping) and not isinstance(value, Mapping):  # it makes no sense to
                    return set(value)  # convert the existing node to a set if it's a Mapping, so just return set(value)
                getattr(node, action)(value)
        else:
            raise ValueError(
                f"Invalid action for _build_node(): {action}, must be one of add, append, extend, insert, set, update"
            )
        return node

    def setdefault(
        self: Collection,
        path: Any = "",
        default=...,
        fagus: bool = ...,
        node_types: str = ...,
        list_insert: int = ...,
        path_split: str = ...,
        default_node_type: str = ...,
    ) -> Any:
        """Get value at path and return it. If there is no value at path, set default at path, and return default

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            path: position in self where default shall be set / from where value shall be fetched. See get() and README
            default: \\* returned if path doesn't exist in self
            fagus: \\* return self as a Fagus-object if it is a node (tuple / list / dict), default False
            node_types: \\* Can be used to manually define if the nodes along path are supposed to be (l)ists or
                (d)icts. E.g. "dll" to create a dict at level 1, and lists at level 2 and 3. " " can also be used -
                space doesn't enforce a node-type like d or l. For " ", existing nodes are traversed if possible,
                otherwise default_node_type is used to create new nodes. Default "", interpreted as " " at each level.
            list_insert: \\* Level at which a new node shall be inserted into the list instead of traversing the
                existing node in the list at that index. See README
            path_split: \\* used to split path into a list if path is a str, default " "
            default_node_type: \\* determines if new nodes by default should be created as (d)ict or (l)ist. Must be
                either "d" or "l", default "d"

        Returns:
            value at path if it exists, otherwise default is set at path and returned

        Raises:
            ValueError: if it isn't possible to parse an int-index from the provided key in a position where node-types
                defines that the node shall be a list (if node-types is not l, the node will be replaced with a dict)
            TypeError: if the root node needs to be modified and isn't modifiable (e.g. tuple or frozenset)
        """
        if isinstance(path, str):
            l_path = path.split(Fagus._opt(self, "path_split", path_split)) if path else []
        else:
            l_path = list(path) if _is(path, Collection) else [path]
        parent_node = Fagus._get_mutable_node(
            self, l_path, Fagus._opt(self, "list_insert", list_insert), Fagus._opt(self, "node_types", node_types)
        )
        if parent_node is _None:
            value = Fagus._opt(self, "default", default)
            Fagus.set(self, value, path, node_types, list_insert, path_split, False, _None, default_node_type)
        else:
            value = Fagus.get(parent_node, l_path[-1], _None, fagus=False)
            if value is _None or (list_insert == len(l_path) - 1 and isinstance(parent_node, MutableSequence)):
                value = Fagus._opt(self, "default", default)
                if isinstance(parent_node, MutableSequence):
                    parent_node.insert(int(l_path[-1]), value)
                else:
                    parent_node[l_path[-1]] = value
        return Fagus.child(self, value) if Fagus._opt(self, "fagus", fagus) and _is(value, Collection) else value

    def mod(
        self: Collection,
        mod_function: Callable,
        path,
        default=...,
        replace_value=True,
        fagus: bool = ...,
        node_types: str = ...,
        list_insert: int = ...,
        path_split: str = ...,
        default_node_type: str = ...,
    ) -> Any:
        """Modifies the value at path using the function-pointer mod_function

        mod can be used like this Fagus.mod(obj, "kitchen spoon", lambda x: x + 1, 1) to count the number of spoons in
        the kitchen. If there is no value to modify, the default value (here 1) will be set at the node.

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            mod_function: A function pointer or lambda that modifies the existing value at path. TFunc can be used to
                call more complex functions requiring several arguments.
            path: position in self at which the value shall be modified. Defined as a list/Tuple of key-values to
                recursively traverse self. Can also be specified as string which is split into a tuple using path_split
            default: \\* this value is set in path if it doesn't exist
            fagus: \\* Return new value as a Fagus-object if it is a node (tuple / list / dict), default False
            replace_value: Replace the old value with what mod_function returns. Can be deactivated e.g. if mod_function
                changes the object, but returns None (if ~ stays on, the object is replaced with None). Default True.
                If no value exists at path, the default value is always set at path (independent of ~)
            node_types: \\* Can be used to manually define if the nodes along path are supposed to be (l)ists or
                (d)icts. E.g. "dll" to create a dict at level 1, and lists at level 2 and 3. " " can also be used -
                space doesn't enforce a node-type like d or l. For " ", existing nodes are traversed if possible,
                otherwise default_node_type is used to create new nodes. Default "", interpreted as " " at each level.
            list_insert: \\* Level at which a new node shall be inserted into the list instead of traversing the
                existing node in the list at that index. See README
            path_split: \\* used to split path into a list if path is a str, default " "
            default_node_type: \\* determines if new nodes by default should be created as (d)ict or (l)ist. Must be
                either "d" or "l", default "d"

        Returns:
            the new value that was returned by the mod_function, or default if there was no value at path

        Raises:
            ValueError: if it isn't possible to parse an int-index from the provided key in a position where node-types
                defines that the node shall be a list (if node-types is not l, the node will be replaced with a dict)
            TypeError: if the root node needs to be modified and isn't modifiable (e.g. tuple or frozenset)
        """
        root = self.root if isinstance(self, Fagus) else self
        if isinstance(path, str):
            l_path = path.split(Fagus._opt(self, "path_split", path_split)) if path else []
        else:
            l_path = list(path) if _is(path, Collection) else [path]
        list_insert = Fagus._opt(self, "list_insert", list_insert)
        parent = Fagus._get_mutable_node(
            self, l_path, list_insert=list_insert, node_types=Fagus._opt(self, "node_types", node_types)
        )
        if isinstance(parent, (MutableMapping, MutableSequence)) and list_insert != len(l_path):
            old_value = Fagus.get(parent, l_path[-1], _None, fagus=False)
            if replace_value:
                if isinstance(parent, MutableSequence):
                    if list_insert == len(l_path) - 1:
                        new_value = Fagus._opt(self, "default", default)
                        parent.insert(int(l_path[-1]), new_value)
                    else:
                        new_value = (
                            Fagus._opt(self, "default", default) if old_value is _None else mod_function(old_value)
                        )
                        parent[int(l_path[-1])] = new_value
                else:
                    new_value = Fagus._opt(self, "default", default) if old_value is _None else mod_function(old_value)
                    parent[l_path[-1]] = new_value
        else:
            new_value = Fagus._opt(self, "default", default)
            Fagus.set(root, new_value, path, node_types, list_insert, path_split, False, _None, default_node_type)
        return Fagus.child(self, default) if _is(default, Collection) and Fagus._opt(self, "fagus", fagus) else default

    def mod_all(
        self: Collection,
        mod_function: Callable,
        filter_: Fil = None,
        path: Any = "",
        replace_value=True,
        default=...,
        max_depth: int = INF,
        fagus: bool = ...,
        copy=False,
        path_split: str = ...,
    ) -> Collection:
        """Modify all the leaf-values that match a certain filter

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            mod_function: A function pointer or lambda that modifies the existing value at path. TFunc can be used to
                call more complex functions requiring several arguments.
            filter_: used to select which leaves shall be modified. Default None (all leaves are modified)
            path: position in self at which the value shall be modified. See get() / README
            default: \\* this value is returned if path doesn't exist, or if no leaves match the filter
            fagus: \\* Return new value as a Fagus-object if it is a node (tuple / list / dict), default False
            replace_value: Replace the old value with what mod_function returns. Can be deactivated e.g. if mod_function
                changes the object, but returns None (if ~ stays on, the object is replaced with None). Default True.
                If no value exists at path, the default value is always set at path (independent of ~)
            max_depth: Defines the maximum depth for the iteration. See Fagus.iter max_depth for more information
            copy: Can be ued to make sure that the node at path is not modified (instead a modified copy is returned)
            path_split: \\* used to split path into a list if path is a str, default " "

        Returns:
            the node at path where all the leaves matching filter\\_ are modified, or default if it didn't exist

        Raises:
            TypeError: if the root node needs to be modified and isn't modifiable (e.g. tuple or frozenset)
        """
        base = Fagus.get(self, path, _None, False, copy, path_split)
        if base is _None or not _is(base, Collection) or not base:
            return Fagus._opt(self, "default", default)
        f_iter = Fagus.iter(base, max_depth, filter_=filter_, fagus=False, iter_fill=_None, iter_nodes=True)
        if replace_value:
            parent, last_deepest = None, None
            for deepest_change, parent_not_deepest, *base_keys, parent_, key, old_value in tuple(
                (f_iter.deepest_change, f_iter.deepest_change < (len(p) - 3) / 2, *p[1::2], *p[-3:]) for p in f_iter
            ):
                if parent_not_deepest or last_deepest != deepest_change:
                    if not _is(parent_, MutableMapping, MutableSequence, MutableSet):
                        parent = Fagus._get_mutable_node(base, base_keys)
                    else:
                        parent = parent_
                    last_deepest = deepest_change
                if isinstance(parent, MutableSet):
                    parent.remove(old_value)
                    parent.add(mod_function(old_value))
                else:
                    parent[key] = mod_function(old_value)
        else:
            for *_, old_value in f_iter:
                mod_function(old_value)
        return Fagus.child(self, base) if Fagus._opt(self, "fagus", fagus) else base

    def serialize(
        self: Union[dict, list],
        mod_functions: Mapping = None,
        path: Any = "",
        node_types: str = ...,
        list_insert: int = ...,
        path_split: str = ...,
        copy: bool = False,
    ) -> Union[dict, list]:
        """Makes sure the object can be serialized so that it can be converted to JSON, YAML etc.

        The only allowed data-types for serialization are: dict, list, bool, float, int, str, None

        Sets and tuples are converted into lists. Other objects whose types are not allowed in serialized objects are
        modified to a type that is allowed using the mod_functions-parameter. mod_functions is a dict, with the type
        of object like IPv4Address or a tuple of types like (IPv4Address, IPv6Address). The values are function pointers
        or lambdas, that are executed to convert e.g. an IPv4Address to one of the allowed data types mentioned above.

        The default mod_functions are: {datetime: lambda x: x.isoformat(), date: lambda x: x.isoformat(), time:
        lambda x: x.isoformat(), "default": lambda x: str(x)}

        By default, date, datetime and time-objects are replaced by their isoformat-string. All other objects whose
        types don't appear in mod_functions are modified by the function behind the key "default". By default, this
        function is lambda x: str(x) that replaces the object with its string-representation.

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            mod_functions: \\* ~ is used to define how different types of objects are supposed to be serialized. This is
                defined in a dict. The keys are either a type (like IPAddress) or a tuple of different types
                (IPv4Address, IPv6Address). The values are function pointers, or lambdas, which are supposed to convert
                e.g. an IPv4Address into a string. Check out TFunc if you want to call more complicated functions with
                several arguments. See README for examples
            path: position in self at which the value shall be modified. See get() / README
            node_types: \\* Can be used to manually define if the nodes along path are supposed to be (l)ists or
                (d)icts. E.g. "dll" to create a dict at level 1, and lists at level 2 and 3. " " can also be used -
                space doesn't enforce a node-type like d or l. For " ", existing nodes are traversed if possible,
                otherwise default_node_type is used to create new nodes. Default "", interpreted as " " at each level.
            list_insert: \\* Level at which a new node shall be inserted into the list instead of traversing the
                existing node in the list at that index. See README
            path_split: \\* used to split path into a list if path is a str, default " "
            copy: Create a copy and make that copy serializable. Default is to modify self directly

        Returns:
            a serializable object that only contains types allowed in json or yaml

        Raises:
            TypeError: if root node is not a dict or list (serialize can't fix that for the root node)
            ValueError: if tuple_keys is not defined in mod_functions and a dict has tuples as keys
            Exception: Can raise any exception if it occurs in one of the mod_functions
        """
        if isinstance(path, str):
            l_path = path.split(Fagus._opt(self, "path_split", path_split)) if path else []
        else:
            l_path = list(path) if _is(path, Collection) else [path]
        node = Fagus._get_mutable_node(
            self,
            l_path,
            Fagus._opt(self, "list_insert", list_insert),
            Fagus._opt(self, "node_types", node_types),
            False,
        )
        if node is _None:
            return [] if Fagus._opt(self, "default_node_type") == "l" else {}
        if copy:
            node = Fagus.__copy__(node)
        if not (
            mod_functions is None
            or all(
                k in ("default", "tuple_keys")
                or all(isinstance(e, type) for e in (k if _is(k, Iterable) else (k,)))
                and callable(v)
                for k, v in mod_functions.items()
            )
        ):
            raise ValueError(
                "mod_functions must be a dict with types (or tuples of types) as keys and function pointers "
                "(either lambda or wrapped in TFunc-nodeects) as values."
            )
        return Fagus._serialize_r(
            node,
            {
                **{
                    datetime: lambda x: x.isoformat(" ", "seconds"),
                    date: lambda x: x.isoformat(),
                    time: lambda x: x.isoformat("seconds"),
                    "default": lambda x: repr(x),
                },
                **({} if mod_functions is None else mod_functions),
            },
        )

    @staticmethod
    def _serialize_r(node: Union[dict, list], mod_functions: Mapping):
        """Recursive function that returns a node where all the keys and values are serializable"""
        for k, v in list(node.items() if isinstance(node, MutableMapping) else enumerate(node)):
            ny_k, ny_v = _None, _None
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
                    ny_k = Fagus._serializable_value(k, mod_functions)
            if _is(v, Collection):
                if isinstance(v, (dict, list)):
                    Fagus._serialize_r(v, mod_functions)
                else:
                    ny_v = dict(v.items()) if isinstance(v, Mapping) else list(v)
                    Fagus._serialize_r(ny_v, mod_functions)
            elif not isinstance(v, (bool, float, int, str)) and v is not None:
                ny_v = Fagus._serializable_value(v, mod_functions)
            if ny_k is not _None:
                node.pop(k)
                node[ny_k] = v if ny_v is _None else ny_v
            elif ny_v is not _None:
                node[k] = ny_v
        return node

    @staticmethod
    def _serializable_value(value, mod_functions):
        """Returns the value modified through the mod-function for its type"""
        for types, mod_function in mod_functions.items():
            if type(value) == types or (_is(types, Collection) and type(value) in types):
                return mod_function(value)
        return mod_functions["default"](value)

    def merge(
        self: Collection,
        obj: Union["FagusIterator", Collection],
        path: Any = "",
        new_value_action: str = "r",
        extend_from: int = INF,
        update_from: int = INF,
        fagus: bool = ...,
        copy: bool = False,
        copy_obj: bool = False,
        path_split: str = ...,
        node_types: str = ...,
        list_insert: int = ...,
        default_node_type: str = ...,
    ) -> Collection:
        """Merges two or more tree-objects to update and extend the root node

        Args:
            obj: tree-object that shall be merged. Can also be a FagusIterator returned from iter() to only merge
                values matching a filter defined in iter()
            path: position in root where the new objects shall be merged, default ""
            new_value_action: This parameter defines what merge is supposed to do if a value at a path is present in the
                root and in one of the objects to merge. The possible values are: (r)eplace - the value in the root is
                replaced with the new value, this is the default behaviour; (i)gnore - the value in the root is not
                updated; (a)ppend - the old and new value are both put into a list, and thus aggregated
            extend_from: By default, lists are traversed, so the value at index i will be compared in both lists. If
                at some point you rather want to just append the contents from the objects to be merged, use this
                parameter to define the level (count of keys) from which lists should be extended isf traversed. Default
                infinite (never extend lists)
            update_from: Like extend_from, but for dicts. Allows you to define at which level the contents of the root
                should just be updated with the contents of the objects instead of traversing and comparing each value
            fagus: whether the returned tree-object should be returned as Fagus
            copy: Don't modify the root node, modify and return a copy instead
            copy_obj: The objects to be merged are not modified, but references to subnodes of the objects can be
                put into the root node. Set this to True to prevent that and keep root and objects independent
            path_split: \\* used to split path into a list if path is a str, default " "
            node_types: \\* Can be used to manually define if the nodes along path are supposed to be (l)ists or
                (d)icts. E.g. "dll" to create a dict at level 1, and lists at level 2 and 3. " " can also be used -
                space doesn't enforce a node-type like d or l. For " ", existing nodes are traversed if possible,
                otherwise default_node_type is used to create new nodes. Default "", interpreted as " " at each level.
            list_insert: \\* Level at which a new node shall be inserted into the list instead of traversing the
                existing node in the list at that index. See README
            default_node_type: \\* determines if new nodes by default should be created as (d)ict or (l)ist. Must be
                either "d" or "l", default "d"

        Returns:
            a reference to the modified root node, or a modified copy of the root node (see copy-parameter)

        Raises:
            ValueError: if it isn't possible to parse an int-index from the provided key in a position where node-types
                defines that the node shall be a list (if node-types is not l, the node will be replaced with a dict)
            TypeError: if obj is not either a FagusIterator or a Collection. Also raised if you try to merge different
                types of nodes at root level, e.g. a dict can only be merged with another Mapping, and a list can only
                be merged with another Iterable. ~ is also raised if a not modifiable root node needs to be modified
        """
        if new_value_action[0:1] not in "ria":
            raise ValueError(
                f"Invalid new_value_action: {new_value_action}. Valid inputs: (r)eplace, (i)gnore or (a)ppend."
            )
        node = Fagus.get(self, path, _None, False, copy, path_split)
        if node is _None or not _is(node, Collection):
            if isinstance(obj, FagusIterator):
                object_ = obj.obj()
            elif _is(obj, Collection):
                object_ = obj.root if isinstance(obj, Fagus) else obj
            else:
                raise TypeError(f"Can merge with FagusIterator or Collection, but not with {type(obj).__name__}")
            if copy_obj:
                object_ = Fagus.__copy__(object_)
            if not copy:
                Fagus.set(self, object_, path, node_types, list_insert, path_split, False, _None, default_node_type)
            return Fagus.child(self, object_) if Fagus._opt(self, "fagus", fagus) else object_
        base_nodes = [node]
        iter_options = dict(
            max_depth=extend_from + update_from,
            fagus=False,
            iter_fill=_None,
            iter_nodes=True,
            copy=copy_obj,
            filter_ends=True,
        )
        if isinstance(obj, FagusIterator):
            obj_iter = obj
            obj_iter.__dict__.update(**iter_options)
        elif _is(obj, Collection):
            obj_iter = FagusIterator(obj if isinstance(obj, Fagus) else Fagus.child(self, obj), **iter_options)
        else:
            raise TypeError(f"Can merge with FagusIterator or Collection, but not with {type(obj).__name__}")
        node_type, mutable_node = Fagus._node_type(node, True)
        obj_type = Fagus._node_type(obj_iter.obj())
        if not extend_from or not update_from or node_type != obj_type or node_type == Set:
            if obj_type == Mapping:
                if node_type == Mapping and not update_from:
                    node.update(obj_iter.obj())
                    return Fagus.child(self, node) if Fagus._opt(self, "fagus", fagus) else node
            elif node_type == Set:
                node.update(obj_iter.obj())
                return Fagus.child(self, node) if Fagus._opt(self, "fagus", fagus) else node
            elif node_type == Sequence and not extend_from or obj_type != Sequence:
                node.extend(obj_iter.obj())
                return Fagus.child(self, node) if Fagus._opt(self, "fagus", fagus) else node
            raise TypeError(
                f"Unsupported operand types for merge: {node_type.__name__} and {obj_type.__name__}. The types "
                "have to be equal, additionally a Sequence can be extended with a Set and a Set can be updated "
                "with anything except from a Mapping."
            )
        for path in obj_iter:
            i = obj_iter.deepest_change
            if i < len(base_nodes):
                del base_nodes[i + 1 :]
                node = base_nodes[-1]
                node_type, mutable_node = Fagus._node_type(node, True)
                try:
                    for i, k in enumerate(path[1 + i * 2 : -3 : 2], start=i):
                        obj_node_type = Fagus._node_type(path[2 * i])
                        extend_sequence = extend_from <= i and node_type == Sequence
                        if extend_sequence or update_from <= i or node_type == Set:
                            if not mutable_node:
                                Fagus._ensure_mutable_node(base_nodes, path[1:-1:2])
                                mutable_node = True
                            getattr(node, "extend" if extend_sequence else "update")(obj_iter.skip(i, copy_obj))
                            raise StopIteration
                        try:
                            if node_type == obj_node_type:
                                new_node = node[k]
                                if _is(new_node, Collection):
                                    node = new_node
                                    node_type, mutable_node = Fagus._node_type(node, True)
                                    base_nodes.append(node)
                        except (IndexError, KeyError):
                            if not mutable_node:
                                node = Fagus._ensure_mutable_node(base_nodes, path[1:-1:2])
                                mutable_node = True
                            if node_type == Mapping:
                                node[k] = obj_iter.skip(i + 1, copy_obj)
                            elif node_type == Sequence:
                                node.insert(k, obj_iter.skip(i + 1, copy_obj))
                            else:
                                node.add(obj_iter.skip(i + 1, copy_obj))
                            raise StopIteration
                except StopIteration:
                    continue
            old_value = Fagus.get(node, (path[2 * len(base_nodes) - 1],), _None)
            if old_value is _None:
                if not mutable_node:
                    node = Fagus._ensure_mutable_node(base_nodes, path[1 : 2 * len(base_nodes) : 2])
                    mutable_node = True
                if node_type == Mapping:
                    node[path[2 * len(base_nodes) - 1]] = path[-1]
                else:
                    getattr(node, "append" if node_type == Sequence else "add")(path[-1])
            else:
                if new_value_action[0:1] == "i":
                    continue
                elif new_value_action[0:1] == "a":
                    if _is(old_value, MutableSequence):
                        old_value.append(path[-1])
                        continue
                    new_value = [old_value, path[-1]]
                else:
                    new_value = path[2 * len(base_nodes)]
                if not mutable_node:
                    node = Fagus._ensure_mutable_node(base_nodes, path[1 : 2 * len(base_nodes) : 2])
                    mutable_node = True
                if node_type == Set:
                    node.add(new_value)
                elif new_value or not _is(new_value, Collection):
                    node[path[2 * len(base_nodes) - 1]] = new_value
        return Fagus.child(self, base_nodes[0]) if Fagus._opt(self, "fagus", fagus) else base_nodes[0]

    def pop(self: Collection, path: Any = "", default=..., fagus: bool = ..., path_split: str = ...):
        """Deletes the value at path and returns it

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            path: pop value at this position in self, or don't do anything if path doesn't exist in self
            default: \\* returned if path doesn't exist in self
            fagus: \\* return the result as Fagus-object if possible (default is just to return the result)
            path_split: \\* used to split path into a list if path is a str, default " "

        Returns:
            value at path if it exists, or default if it doesn't

        Raises:
            TypeError: if the root node needs to be modified and isn't modifiable (e.g. tuple or frozenset)
        """
        if isinstance(path, str):
            l_path = path.split(Fagus._opt(self, "path_split", path_split)) if path else []
        else:
            l_path = list(path) if _is(path, Collection) else [path]
        default = Fagus._opt(self, "default", default)
        node = Fagus._get_mutable_node(self, l_path)
        try:
            if isinstance(node, MutableMapping):
                node = node.pop(l_path[-1])
            elif isinstance(node, MutableSequence):
                node = node.pop(int(l_path[-1]))
            elif isinstance(node, MutableSet):
                node.remove(l_path[-1])
                node = l_path[-1]
            else:
                node = default
        except (IndexError, ValueError, KeyError):
            node = default
        return Fagus.child(self, node) if _is(node, Collection) and Fagus._opt(self, "fagus", fagus) else node

    def popitem(self):
        """This function is not implemented in Fagus"""
        pass

    def discard(self: Collection, path: Any = "", path_split: str = ...) -> None:
        """Deletes the value at path if it exists

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            path: pop value at this position in self, or don't do anything if path doesn't exist in self
            path_split: \\* used to split path into a list if path is a str, default " "

        Returns: None
        """
        Fagus.pop(self, path, path_split=path_split)

    def remove(self, path: Any = "", path_split: str = ...) -> None:
        """Deletes the value at path if it exists, raises KeyError if it doesn't

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            path: pop value at this position in self, or don't do anything if path doesn't exist in self
            path_split: \\* used to split path into a list if path is a str, default " "

        Returns: None

        Raises:
            KeyError: if the value at path doesn't exist
        """
        if Fagus.pop(self, path, _None, path_split=path_split) is _None:
            raise KeyError(f"Couldn't remove {path}: Does not exist")

    def keys(self: Collection, path: Any = "", path_split: str = ...):
        """Returns keys for the node at path, or None if that node is a set or doesn't exist / doesn't have keys

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            path: get keys for node at this position in self. Default "" (gets values from the root node), See get()
            path_split: \\* used to split path into a list if path is a str, default " "

        Returns:
            keys for the node at path, or an empty tuple if that node is a set or doesn't exist / doesn't have keys
        """
        node = Fagus.get(self, path, fagus=False, path_split=path_split)
        if isinstance(node, Mapping):
            return node.keys()
        if _is(node, Sequence):
            return range(len(node))
        if isinstance(node, Set):
            return (... for _ in node)
        return ()

    def values(
        self: Collection,
        path: Any = "",
        path_split: str = ...,
        fagus: bool = ...,
        copy: bool = False,
    ):
        """Returns values for node at path

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            path: get values at this position in self, default "" (gets values from the root node). See get()
            path_split: \\* used to split path into a list if path is a str, default " "
            fagus: \\* converts sub-nodes into Fagus-objects in the returned list of values, default False
            copy: ~ creates a copy of the node before values() are returned. This can be beneficial if you want to make
                changes to the returned nodes, but you don't want to change self. Default False

        Returns:
            values for the node at path. Returns an empty tuple if the value doesn't exist, or just the value in a
            tuple if the node isn't iterable.
        """
        node = Fagus.get(self, path, _None, path_split=path_split, fagus=False, copy=copy)
        if _is(node, Collection):
            values = node.values() if isinstance(node, Mapping) else node
            if Fagus._opt(self, "fagus", fagus):
                return (Fagus.child(self, e) if _is(e, Collection) else e for e in values)
            return values
        elif node is _None:
            return ()
        return (node,)

    def items(
        self: Collection,
        path: Any = "",
        path_split: str = ...,
        fagus: bool = ...,
        copy: bool = False,
    ):
        """Returns in iterator of (key, value)-tuples in self, like dict.items()

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            path: get items at this position in self, Default "" (gets values from the root node). See get()
            path_split: \\* used to split path into a list if path is a str, default " "
            fagus: \\* converts sub-nodes into Fagus-objects in the returned iterator, default False
            copy: ~ creates a copy of the node before items() are returned. This can be beneficial if you want to make
                changes to the returned nodes, but you don't want to change self. Default False

        Returns:
            iterator of (key, value)-tuples in self, like dict.items()
        """
        node = Fagus.get(self, path, _None, False, copy, path_split)
        if isinstance(node, Mapping):
            items = node.items()
        elif _is(node, Sequence):
            items = enumerate(node)
        elif isinstance(node, Set):
            items = ((..., e) for e in node)
        else:
            return ()
        if Fagus._opt(self, "fagus", fagus):
            return ((k, Fagus.child(self, v) if _is(v, Collection) else v) for k, v in items)
        return items

    def clear(
        self: Collection,
        path: Any = "",
        path_split: str = ...,
        copy: bool = False,
        fagus: bool = ...,
    ) -> Collection:
        """Removes all elements from node at path.

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            path: clear at this position in self, Default "" (gets values from the root node). See get()
            path_split: \\* used to split path into a list if path is a str, default " "
            copy: if ~ is set, a copy of self is modified and then returned (thus self is not modified), default False
            fagus: \\* return self as a Fagus-object if it is a node (tuple / list / dict), default False

        Returns:
            self as a node if fagus is set, or a modified copy of self if copy is set

        Raises:
            TypeError: if the root node needs to be modified and isn't modifiable (e.g. tuple or frozenset)
        """
        root = Fagus.__copy__(self) if copy else self
        if isinstance(path, str):
            l_path = path.split(Fagus._opt(self, "path_split", path_split)) if path else []
        else:
            l_path = list(path) if _is(path, Collection) else [path]
        node = Fagus._get_mutable_node(root, l_path, parent=False)
        if node is not _None:
            node.clear()
        if isinstance(root, Fagus):
            return root if Fagus._opt(self, "fagus", fagus) else root()
        return Fagus.child(self, root) if Fagus._opt(self, "fagus", fagus) else root

    def contains(self: Collection, value, path: Any = "", path_split: str = ...) -> bool:
        """Check if value is present in the node at path

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            value: value to check
            path: check if value is in node at this position in self, Default "" (checks root node). See get()
            path_split: \\* used to split path into a list if path is a str, default " "

        Return:
            whether value is in node at path in self. returns value == node if the node isn't iterable, and false if
            path doesn't exit in self"""
        node = Fagus.get(self, path, _None, fagus=False, path_split=path_split)
        return value in node if _is(node, Collection) else value == node

    def count(self: Collection, path: Any = "", path_split: str = ...) -> int:
        """Check the number of elements in the node at path

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            path: position in self where the number of elements shall be found.Default "" (checks root node). See get()
            path_split: \\* used to split path into a list if path is a str, default " "

        Return:
            the number of elements in the node at path. if there is no node at path, 0 is returned. If the element
            at path is not a node, 1 is returned
        """
        node = Fagus.get(self, path, _None, fagus=False, path_split=path_split)
        return len(node) if _is(node, Collection) else 0 if node is _None else 1

    def index(
        self: Collection,
        value: Any,
        start: int = ...,
        stop: int = ...,
        path: Any = "",
        all_: bool = False,
        path_split: str = ...,
    ) -> Optional[Union[int, Any, Sequence]]:
        """Returns the index / key of the specified value in the node at path if it exists

        Args:
            value: ~ to search index for
            start: start searching at this index. Only applicable if the node at path is a list / tuple
            stop: stop searching at this index. Only applicable if the node at path is a list / tuple
            path: position in self where the node shall be searched for value. Default "" (checks root node). See get()
            all_: returns all matching indices / keys in a generator (instead of only the first)
            path_split: \\* used to split path into a list if path is a str, default " "

        Returns:
            The first index of value if the node at path is a list, or the first key containing value if the node at
            path is a dict. True if the node at path is a Set and contains value. If the element can't be found in the
            node at path, or there is no Collection at path, None is returned (instead of a ValueError).
        """
        node = Fagus.get(self, path, None, False, False, path_split)
        if isinstance(node, Set):
            if all_:
                return
            return ((True,) if value in node else ()) if all_ else (True if value in node else None)
        if isinstance(node, Mapping):
            if all_:
                return (k for k, v in node.items() if v == value)
            for k, v in node.items():
                if v == value:
                    return k
            return
        if _is(node, Sequence):
            if all_:
                indices = []
                try:
                    start = 0 if start is ... else start
                    stop = INF if stop is ... else (stop if stop >= 0 else len(node) + stop)
                    while start < stop:
                        indices.append(node.index(value, start, stop))
                        start = indices[-1] + 1
                except ValueError:
                    pass
                return indices
            try:
                return node.index(value, *((() if start is ... else (start,)) + (() if stop is ... else (stop,))))
            except ValueError:
                pass

    def isdisjoint(
        self: Collection, other: Iterable, path: Any = "", path_split: str = ..., dict_: str = "keys"
    ) -> bool:
        """Returns whether the other iterable is disjoint (has no common items) with the node at path

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            other: other object to check
            path: check if the node at this position in self, is disjoint from other
            path_split: \\* used to split path into a list if path is a str, default " "
            dict_: use (k)eys, (v)alues or (i)tems for if value is a dict. Default keys

        Returns: whether the other iterable is disjoint from the value at path. If value is a dict, the keys are used.
            Checks if value is present in other if value isn't iterable. Returns True if there is no value at path.
        """
        node = Fagus.get(self, path, _None, False, False, path_split)
        if isinstance(node, Mapping):
            if not dict_ or dict_[0] not in ("k", "v", "i"):
                raise ValueError(f"dict_ attribute must bei either (k)eys, (v)alues or (i)tems. You provided {dict_}")
            return set(getattr(node, {"k": "keys", "v": "values", "i": "items"}[dict_[0]])()).isdisjoint(other)
        if isinstance(node, Set):
            return node.isdisjoint(other)
        return set(node).isdisjoint(other) if _is(node, Collection) else node not in other

    def child(self: Collection, obj: Collection = None, **kwargs) -> "Fagus":
        """Creates a Fagus-object for obj that has the same options as self"""
        return Fagus(obj, **({**self._options, **kwargs} if isinstance(self, Fagus) and self._options else kwargs))

    def reversed(
        self: Collection,
        path: Any = "",
        fagus: bool = ...,
        path_split: str = ...,
        copy: bool = False,
    ):
        """Get reversed child-node at path if that node is a list

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            path: position in self where a list / tuple shall be returned reversed
            fagus: \\* converts sub-nodes into Fagus-objects in the returned iterator, default False
            path_split: \\* used to split path into a list if path is a str, default " "
            copy: ~ creates a copy of the node before it is returned reversed(). This can be beneficial if you want to
                make changes to the returned nodes, but you don't want to change self. Default False

        Returns:
            a reversed iterator on the node at path (empty if path doesn't exist)
        """
        node = Fagus.values(self, path, path_split, fagus, copy)
        if not _is(node, Reversible):
            node = tuple(node) if _is(node, Iterable) else (node,)
        return reversed(node)

    def reverse(
        self: Collection,
        path: Any = "",
        fagus: bool = ...,
        path_split: str = ...,
        copy: bool = False,
    ) -> Collection:
        """Reverse child-node at path if that node exists and is reversible

        \\* means that the parameter is a Fagus-Setting, see Fagus-class-docstring for more information about options

        Args:
            path: position in self where a list / tuple shall be reversed
            fagus: \\* converts sub-nodes into Fagus-objects in the returned iterator, default False
            path_split: \\* used to split path into a list if path is a str, default " "
            copy: ~ creates a copy of the node before it is returned reversed(). This can be beneficial if you want to
                make changes to the returned nodes, but you don't want to change self. Default False

        Returns:
            self as a node if fagus is set, or a modified copy of self if copy is set

        Raises:
            TypeError: if the root node needs to be modified and isn't modifiable (e.g. tuple or frozenset)
        """
        root = self.root if isinstance(self, Fagus) else self
        if copy:
            root = Fagus.__copy__(self)
        if isinstance(path, str):
            l_path = path.split(Fagus._opt(self, "path_split", path_split)) if path else []
        else:
            l_path = list(path) if _is(path, Collection) else [path]
        if l_path:
            parent = Fagus._get_mutable_node(root, l_path)
            node = Fagus.get(parent, l_path[-1], _None, fagus=False)
            if hasattr(node, "reverse"):
                node.reverse()
            elif isinstance(node, Mapping):  # if node.items() isn't reversible, the native error is thrown (that's ok)
                parent[l_path[-1]] = dict(reversed(tuple(node.items())))
            elif isinstance(node, Reversible):
                parent[int(l_path[-1]) if isinstance(parent, Sequence) else l_path[-1]] = list(reversed(node))
            elif node is not _None:
                raise TypeError(f"Cannot reverse node of type {type(node).__name__}.")
        else:
            if hasattr(root, "reverse"):
                root.reverse()
            else:
                if isinstance(root, MutableMapping):
                    tmp = cp.copy(root)
                    root.clear()
                    root.update(reversed(tuple(tmp.items())))
                elif isinstance(root, MutableSequence):
                    tmp = cp.copy(root)
                    root.clear()
                    root.extend(reversed(tmp))
                else:
                    raise TypeError(f"Cannot reverse root node of type {type(root).__name__}")
        return Fagus.child(self, root) if Fagus._opt(self, "fagus", fagus) else root

    def copy(self: Collection, deep: bool = False):
        """Creates a copy of self. Creates a recursive shallow copy by default, or a copy.deepcopy() if deep is set."""
        if deep:
            return cp.deepcopy(self)
        return Fagus.__copy__(self)

    def __options(  # at runtime, this function is renamed to options (see __init__). That was necessary to not override
        self,  # options in FagusMeta when Fagus.options() is called, instead of a = Fagus(); a.options(). Little hack
        options: dict = None,
        get_default_options: bool = False,
        reset: bool = False,
    ) -> dict:
        """Function to set multiple Fagus-options in one line

        Args:
            options: dict with options that shall be set
            get_default_options: return all options (include default-values). Default: only return options that are set
            reset: if ~ is set, all options are reset before options is set

        Returns:
            a dict of options that are set, or all options if get_default_options is set
        """
        if all(Fagus.__verify_option__(k, v) for k, v in options.items()) if options else True:
            if reset or self._options is None:
                self._options = options
            elif options:
                self._options.update(options)
        return {
            **{k: v[0] for k, v in (self.__default_options__ if get_default_options else {}).items()},
            **Fagus.options(),
            **(self._options if self._options else {}),
        }

    def _opt(self: Collection, option_name: str, option=...):
        """Internal function that is used for Fagus-options (see Fagus-help or README for more information)"""
        if option is not ...:
            return Fagus.__verify_option__(option_name, option)
        return (
            self._options[option_name]
            if isinstance(self, Fagus) and isinstance(self._options, dict) and option_name in self._options
            else getattr(Fagus, option_name)
        )

    @staticmethod
    def _ensure_mutable_node(
        nodes: List[Collection], path: Sequence, parent: bool = True
    ) -> Union[MutableMapping, MutableSequence, MutableSet]:
        """Internal function that ensures that the current node (the last in nodes) is mutable

        Args:
            nodes: list of nodes that probably will be modified to make the last node mutable
            path: list of keys used to traverse the nodes (and that link the nodes together)

        Returns:
            the node, but modifiable (a tuple will have turned into a list, a frozenset will have turned into a set)
        """
        node = None
        parent = int(not parent)
        i = -1
        for i in range(i, -len(nodes) - 1, -1):
            node = nodes[i]
            if _is(node, MutableMapping, MutableSequence, MutableSet):
                break
            elif i == -len(nodes):
                raise TypeError(f"Can't modify root node self having the immutable type {type(node).__name__}.")
        for i in range(i, -1):
            if i == -2 and _is(nodes[i + 1], Set, is_not=MutableSet):
                node[path[i + parent]] = set(nodes[i + 1])
            else:
                node[path[i + parent]] = (dict if isinstance(nodes[i + 1], Mapping) else list)(nodes[i + 1])
            nodes[i] = node
            node = node[path[i + parent]]
        return node

    def _get_mutable_node(
        self: Collection, l_path: MutableSequence, list_insert: int = INF, node_types: str = "", parent: bool = True
    ) -> Union[MutableMapping, MutableSequence, MutableSet, type(_None)]:
        """Internal function retrieving the parent_node, changing necessary nodes on the way to make it mutable

        Args:
            l_path: must already be a list, so a string from a calling path-function must already be split
            list_insert: \\* Level at which a new node shall be inserted into the list instead of traversing the
                existing node in the list at that index. See README
            node_types: \\* Can be used to manually define if the nodes along path are supposed to be (l)ists or
                (d)icts. E.g. "dll" to create a dict at level 1, and lists at level 2 and 3. " " can also be used -
                space doesn't enforce a node-type like d or l. For " ", existing nodes are traversed if possible,
                otherwise default_node_type is used to create new nodes. Default "", interpreted as " " at each level.

        Returns:
            the parent node if it exists, otherwise None
        """
        node = self.root if isinstance(self, Fagus) else self
        nodes = [node]
        node_types = Fagus._opt(self, "node_types", node_types)
        try:
            for i in range(len(l_path) - int(parent)):
                if isinstance(node, Sequence):
                    if list_insert <= 0 or node_types[i - 1 : i] == "d":
                        return _None
                    l_path[i] = int(l_path[i])
                elif node_types[i - 1 : i] == "l":
                    return _None
                node = node[l_path[i]]
                nodes.append(node)
                list_insert -= 1
            if _is(node, Collection):
                return Fagus._ensure_mutable_node(nodes, l_path, parent)
        except (IndexError, ValueError, KeyError):
            pass
        return _None

    @staticmethod
    def _node_type(node: Collection, check_mutable: bool = False) -> Union[Tuple[type, bool], type]:
        """Internal function. Returns the type of node, and if check_mutable is on also whether the node is mutable

        Args:
            node: the node whose type shall be checked
            check_mutable: if this is on, a tuple is returned of the node-type and whether it is mutable

        Returns:
            Returns the type of node, and if check_mutable is on a tuple: (node-type, mutable) where mutable is a bool
        """
        if check_mutable:
            if isinstance(node, MutableMapping):
                return Mapping, True
            elif _is(node, MutableSequence):
                return Sequence, True
            elif isinstance(node, MutableSet):
                return Set, True
            elif isinstance(node, Mapping):
                return Mapping, False
            elif _is(node, Sequence):
                return Sequence, False
            elif isinstance(node, Set):
                return Set, False
            elif isinstance(node, Iterable):
                return Iterable, False
            else:
                return type(node), False
        if isinstance(node, Mapping):
            return Mapping
        elif _is(node, Sequence):
            return Sequence
        elif isinstance(node, Set):
            return Set
        elif isinstance(node, Iterable):
            return Iterable
        else:
            return type(node)

    def _hash(self) -> int:
        """Inherited from Set. Overridden to ensure that two equal Fagus's have equal hashes (ignoring options)"""
        return hash(self.root)

    def __copy__(self: Collection, recursive=False):
        """Recursively creates a shallow-copy of self"""
        new_node = _copy_node(self.root if isinstance(self, Fagus) else self, recursive)
        return Fagus.child(self, new_node) if isinstance(self, Fagus) else new_node

    def __call__(self):
        """Calling the Fagus-object returns the root node the Fagus-object is wrapped around (equivalent to .root)

        Example:
            >>> from fagus import Fagus
            >>> a = Fagus({"f": "q"})
            >>> a
            Fagus({'f': 'q'})
            >>> a()
            {'f': 'q'}
            >>> a.root  # .root returns the root-object in the same way as ()
            {'f': 'q'}

        Returns:
            the root object Fagus is wrapped around
        """
        return self.root

    def __getattr__(self, attr):  # Enable dot-notation for getting items at a path
        if attr == "root":
            return self.root
        elif hasattr(Fagus, attr):
            if isinstance(self._options, dict):
                return self._options.get(attr, getattr(Fagus, attr))
            return getattr(Fagus, attr)
        else:
            return self.get(attr.lstrip(Fagus._opt(self, "path_split") if isinstance(attr, str) else attr))

    def __getitem__(self, item):  # Enable [] access for dict-keys at the top-level
        return self.get(item)

    def __setattr__(self, attr, value):  # Enable dot-notation for setting items at a given path
        if attr in ("root", "_options", "options"):
            super(Fagus, self).__setattr__(attr, value)
        elif attr in Fagus.__default_options__:
            if self._options is None:
                super(Fagus, self).__setattr__("_options", {})
            self._options[attr] = Fagus.__verify_option__(attr, value)
        else:
            self.set(value, attr.lstrip(Fagus._opt(self, "path_split") if isinstance(attr, str) else attr))

    def __setitem__(self, path, value):  # Enable [] for setting items at a given path
        self.set(value, path)

    def __delattr__(self, attr):  # Enable dot-notation for deleting items at a given path
        if hasattr(Fagus, attr):
            if self._options and attr in self._options:
                del self._options[attr]
                if not self._options:
                    self._options = None
        else:
            self.pop(attr.lstrip(Fagus._opt(self, "path_split") if isinstance(attr, str) else attr))

    def __delitem__(self, path):  # Enable [] for deleting items
        self.pop(path)

    def __iter__(self):
        return iter(self.root if isinstance(self.root, Mapping) else self.values())

    def __hash__(self):
        return hash(self.root)

    def __eq__(self, other):
        return isinstance(other, Fagus) and self.root == other.root

    def __ne__(self, other):
        return not isinstance(other, Fagus) or self.root != other.root

    def __lt__(self, other):
        return self.root < (other.root if isinstance(other, Fagus) else other)

    def __le__(self, other):
        return self.root <= (other.root if isinstance(other, Fagus) else other)

    def __gt__(self, other):
        return self.root > (other.root if isinstance(other, Fagus) else other)

    def __ge__(self, other):
        return self.root >= (other.root if isinstance(other, Fagus) else other)

    def __contains__(self, value):
        return value in self.root

    def __len__(self):
        return len(self.root)

    def __bool__(self):
        return bool(self.root)

    def __repr__(self):
        return "Fagus(%s)" % ", ".join(
            (repr(self.root), *(f"{e[0]}={repr(e[1])}" for e in (self._options.items() if self._options else ())))
        )

    def __str__(self):
        return str(self.root)

    def __iadd__(self, value):
        self.merge(value)
        return self

    def __add__(self, other):
        res = Fagus.merge(self, other, copy=True)
        return self.child(res) if Fagus._opt(self if isinstance(self, Fagus) else other, "fagus") else res

    def __radd__(self, other):
        res = Fagus.merge(other if isinstance(other, Fagus) else self.child(other), self, copy=True)
        return self.child(res) if Fagus._opt(self if isinstance(self, Fagus) else other, "fagus") else res

    def __isub__(self, other):
        if isinstance(self.root, (MutableMapping, MutableSet)):
            for e in other if _is(other, Iterable) else (other,):
                self.root.pop(e, None)
        elif isinstance(self.root, MutableSequence):
            other = set(other() if isinstance(other, Fagus) else other) if _is(other, Iterable) else (other,)
            for i in (k for k, v in enumerate(self.root) if v in other):
                self.root.pop(i)
        else:
            raise TypeError(
                "Unsupported operand types for -=: Can't remove items from self being an immutable "
                f"{type(self.root).__name__}."
            )
        return self

    def __sub__(self, other):
        root = self.root if isinstance(self, Fagus) else self
        other = set(other() if isinstance(other, Fagus) else other) if _is(other, Iterable) else (other,)
        if isinstance(root, Mapping):
            res = {k: v for k, v in root.items() if k not in other}
        else:  # isinstance(self(), (Sequence, Set)):
            res = (set if isinstance(root, Set) else list)(filter(lambda x: x not in other, root))
        return self.child(res) if Fagus._opt(self if isinstance(self, Fagus) else other, "fagus") else res

    def __rsub__(self, other):
        return Fagus.__sub__(other, self)

    def __imul__(self, times: int):
        if not isinstance(times, int):
            raise TypeError(f"Unsupported operand types for *: times must b an int, got {type(times).__name__}.")
        if _is(self.root, MutableSequence):
            self.root.extend(tuple(self.root) * (times - 1))
            return self
        raise TypeError(f"Unsupported operand types for *=: root node must be a list, got {type(self.root).__name__}.")

    def __mul__(self, times: int):
        if not isinstance(times, int):
            raise TypeError(f"Unsupported operand types for *: times must b an int, got {type(times).__name__}.")
        if not _is(self(), Sequence):
            raise TypeError(
                "Unsupported operand types for *: root node must a tuple or list to get multiplied, got "
                f"{type(self.root).__name__}."
            )
        return self.child(self() * times) if Fagus._opt(self, "fagus") else self() * times

    def __rmul__(self, times: int):
        return Fagus.__mul__(self, times)

    def __reversed__(self):
        return self.reversed()

    def __reduce__(self):
        return self.root.__reduce__()

    def __reduce_ex__(self, protocol):
        return self.root.__reduce_ex__(protocol)
