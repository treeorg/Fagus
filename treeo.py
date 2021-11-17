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
from enum import Enum, auto
from typing import Union, Tuple, Any, Optional, List


class TType(Enum):
    """Filter-types for TFilter

    DEFAULT:
        What matches this filter will actually be visible in the result. When a TFilter is passed as an argument to a
        a function in TreeO, it always has to be a DEFAULT-filter. Inside that DEFAULT-filter on the top, CHECK- and
        DEFAULT-filters can be defined for additional verification

    CHECK:
        This type of filter is used to additionally verify nodes that have matched the parent DEFAULT-filter. You can
        use this if you want to filter on values which you don't want to appear in the result.

    VALUE:
        DEFAULT and CHECK-filters only check the keys and leaf-values while filtering. This special type of filter can
        be used to select nodes based on their properties (e. g. select all the nodes that contain at least 10 elements)
    """

    DEFAULT = auto()
    CHECK = auto()
    VALUE = auto()


class _None:
    """Dummy type used internally in TFilter and TreeO to represent non-existing while allowing None as a value"""

    pass


class TFilter:
    """This class is used to specify filter-rules used for filtering trees of dicts and lists in TreeO"""

    def __init__(self, *filter_args, inexclude: str = "", ttype: TType = TType.DEFAULT, string_as_re: bool = False):
        """Initializes TFilter and verifies the arguments passed to it

        Args:
            *filter_args: Each argument filters one key in the tree, the last argument filters the leaf-value. You can
                put a list of values to match different values in the same filter. In this list, you can also specify
                subfilters to match different grains differently.
            inexclude: In some cases it's easier to specify that a filter shall match everything except b, rather than
                match a. ~ can be used to specify for each argument if the filter shall include it (+) or exclude it
                (-). Valid example: "++-+". If this parameter isn't specified, all args will be treated as (+).
            ttype: filter-type, must be one of DEFAULT, CHECK and NODE (see TFilter.Types documentation). CHECK and NODE
                are only supported in subfilters
            string_as_re: If this is set to True, it will be evaluated for all str's if they'd match differently as a
                regex, and in the latter case match these strings as regex patterns. E.g. re.match("a.*", b) will match
                differently than "a.*" == b. In this case, "a.*" will be used as a regex-pattern. However
                re.match("abc", b) will give the same result as "abc" == b, so here "abc" == b will be used.
        """
        self.inexclude = inexclude
        if not bool(re.fullmatch("[+-]*", self.inexclude)):
            raise ValueError(
                f"{self.inexclude} is invalid for inexclude. It must be a str consisting of only + (to include) and "
                f"- (to exclude). If nothing has been specified all filteres will be treated as include (+)-filters."
            )
        self.ttype = ttype
        self.args = list(filter_args)
        if self.ttype == TType.VALUE:
            if not all(callable(arg) or TreeO.__is__(arg, Mapping, Sequence) for arg in filter_args):
                raise TypeError(
                    "The args of a value-filter must either be lambdas, "
                    "or dicts / lists the whole node is compared with."
                )
        else:
            for i, arg in enumerate(self.args):
                if string_as_re and isinstance(arg, str) and arg != re.escape(arg):
                    self[i] = re.compile(arg)
                elif not isinstance(arg, Mapping) and TreeO.__is__(arg, Collection):
                    for j, e in enumerate(arg):
                        if string_as_re and isinstance(e, str) and e != re.escape(e):
                            if not isinstance(arg, MutableSequence):
                                self[i] = list(arg)
                            self[i][j] = re.compile(e)
                        elif isinstance(e, TFilter):
                            if self.ttype == TType.CHECK and e.ttype != TType.VALUE:  # make sure that all children
                                e.ttype = TType.CHECK  # of CHECK-filters are either CHECK-filters or VALUE-filters
                            elif e.ttype != TType.DEFAULT:  # move CHECK and VALUE-filters from args to extra_filters
                                if not isinstance(arg, MutableSequence):
                                    self[i] = list(arg)  # make self[i] a mutable list if necessary
                                self.__set_extra_filter(i, self[i].pop(j))  # to be able to pop out the filter-arg
                                if not self[i]:  # if there only were CHECK- and VALUE-filters in the list and it is now
                                    self[i] = ...  # empty, put ... to give these filters something to match on
                elif isinstance(arg, TFilter):
                    if self.ttype == TType.DEFAULT and arg != TType.DEFAULT:
                        self.__set_extra_filter(i, arg)  # pop out extra-filter and replace it with ... so that
                        self[i] = ...  # it can match anything
                    else:
                        raise ValueError(
                            "You can put a VALUE- or CHECK-filter as a standalone arg (in no list) into a "
                            "DEFAULT-filter It will then be treated as: <<Check this filter, and pass the whole node if"
                            "the filter matches>>. In all other circumstances it makes no sense to have a filter as a "
                            "standalone argument in another."
                        )

    def __set_extra_filter(self, index: int, filter_: "TFilter"):
        if not hasattr(self, "extra_filters"):
            self.extra_filters = {}
        if index not in self.extra_filters:
            self.extra_filters[index] = []
        self.extra_filters[index].append(filter_)

    def __getitem__(self, index: int) -> Any:
        """Get filter-argument at index

        Returns:
            filter-argument at index, TreeO.__Empty__ if index isn't defined
        """
        try:
            return self.args[index]
        except IndexError:
            return _None

    def __setitem__(self, key, value):
        """Set filter-argument at index. Throws IndexError if that index isn't defined"""
        self.args[key] = value

    def match(self, value, index: int) -> Tuple[bool, Optional["TFilter"], int]:
        """match filter at index (matches recursively into subfilters if necessary)

        Args:
            value: the value to be matched against the filter
            index: index of filter-argument to check

        Returns:
            whether the value matched the filter, the filter that matched (as it can be a subfilter), and the next index
                in that (sub)filter
        """
        filter_arg, included = self[index], self.included(index)
        if filter_arg is _None:  # this happens when the filter actually has no argument defined at this index
            return True, None, index + 1  # return True, and None as next filter to prevent unnecessary filtering
        for e in filter_arg if TreeO.__is__(filter_arg, Collection) else (filter_arg,):
            if e is ...:
                return True, self, index + 1
            elif isinstance(e, TFilter):
                match, filter_, index_ = e.match(value, 0)  # recursion to correctly handle nested filters
            else:
                if callable(e):
                    match = e(value)
                elif isinstance(e, re.Pattern):
                    match = bool(e.fullmatch(value))
                else:
                    match = e == value
                filter_, index_ = self, index + 1
            if included == match:
                return True, filter_, index_
        return False, self, index + 1

    def match_list(self, value: int, index: int, node_length: int) -> Tuple[bool, Optional["TFilter"], int]:
        """match_list: same as match, but optimized to match list-indices (e. g. no regex-matching here)

        Args:
            value: the value to be matched against the filter
            index: index of filter-argument to check
            node_length: length of the list whose indices shall be verified

        Returns:
            whether the value matched the filter, the filter that matched (as it can be a subfilter), and the next index
                in that (sub)filter
        """
        if not isinstance(value, int) or not (-node_length <= value < node_length):
            return False, self, index + 1
        filter_arg, included = self[index], self.included(index)
        if filter_arg is _None:
            return True, None, index + 1
        for e in filter_arg if TreeO.__is__(filter_arg, Collection) else (filter_arg,):
            if e is ...:
                return True, self, index + 1
            elif isinstance(e, TFilter):
                match, filter_, index_ = e.match_list(value, 0, node_length)
            else:
                if callable(e):
                    match = e(value)
                else:
                    match = e == value
                filter_, index_ = self, index + 1
            if included == match:
                return True, filter_, index_
        return False, self, index + 1

    def match_extra_filters(self, node: Collection, index: int = 0) -> bool:
        """Match extra filters on node (CHECK and VALUE). Called to additionally verify a node if it passed the filter

        Args:
            node: node to be verified
            index: filter_index to check for extra filters

        Returns:
            bool whether the extra filters matched
        """
        if hasattr(self, "extra_filters") and index in self.extra_filters:
            for filter_ in self.extra_filters[index]:
                if filter_.ttype == TType.CHECK:
                    if not filter_.__match_check_filter_r(node):
                        return False
                else:  # value filter
                    for i, arg in enumerate(filter_.args):
                        if filter_.included(i) != (arg(node) if callable(arg) else node == arg):
                            return False
        return True

    def __match_check_filter_r(self, node: Collection, index: int = 0) -> bool:
        """Recursive function to completely verify a node and its subnodes in a CHECK-filter

        Args:
            node: node to check
            index: index in filter to check (filter is self)

        Returns:
            bool whether the CHECK-filter matched
        """
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
                    if match_v:
                        match_v = match_k[1].match_extra_filters(v, match_k[2] - 1)
                else:
                    match_v, *_ = match_k[1].match(v, match_k[2])
                if match_v:
                    return True
        return False

    def included(self, index) -> bool:
        """This function returns if the filter should be an include-filter (+) or an exclude-filter (-) at a given index

        Args:
            index: index in filter-arguments that shall be interpreted as include- or exclude-filter

        Returns:
            bool that is True if it is an include-filter, and False if it is an Exclude-Filter, defaults to True if
                undefined at index
        """
        return self.inexclude[index : index + 1] != "-"


class TFunc:
    """This wrapper class allows you to run any function at places in the code that normally only accept lambdas"""

    def __init__(self, function_pointer: callable, old_value_position: Union[int, str] = 1, *args, **kwargs):
        """Initializes TFunc-wrapper around function-pointer with optional args and kwargs

        Args:
            function_pointer: Points to the function that is supposed to be called by TFunc. Remember to put no ()
            old_value_position: Where to insert the old_value. If ~ is an int, the old value will be inserted as the
                n'th (or n'th last if negative) argument. If ~ is 0, the old value won't be inserted at all. ~ can also
                be a str, then the old value is inserted into kwargs with ~ as key. Default 1 (old value as first arg)
            *args: args to pass to function. Old value can be inserted into args (see old_value_position)
            **kwargs: keyword-arguments to pass to function. Old value can be added to kwargs (see old_value_position)
        """
        self.function_pointer = function_pointer
        self.old_value_pos = old_value_position
        self.args = args
        self.kwargs = kwargs

    def __call__(self, old_value):
        """Call function in function-pointer with the specified args and kwargs.

        Args:
            old_value: The value to be modified by this function

        Returns:
            the modified value
        """
        if isinstance(self.old_value_pos, str):
            return self.function_pointer(*self.args, **self.kwargs, **{self.old_value_pos: old_value})
        args = list(self.args)
        if self.old_value_pos != 0:
            args.insert(self.old_value_pos if self.old_value_pos < 0 else self.old_value_pos - 1, old_value)
        return self.function_pointer(*args, **self.kwargs)


class TreeOMeta(ABCMeta):
    """Meta-class for TreeO-objects to facilitate settings at class-level"""

    @staticmethod
    def __is__(value, *args):
        """Override of isinstance, making sure that Sequence, Iterable or Collection doesn't match on str or bytearray

        Args:
            value: Value whose instance shall be checked
            *args: types to compare against

        Returns:
            whether the value is instance of one of the types in args (but not str, bytes or bytearray)
        """
        if not all([isinstance(arg, type) for arg in args]):
            raise TypeError("All args must be of the type type.")
        return not isinstance(value, (str, bytes, bytearray)) and isinstance(value, args)

    @staticmethod
    def __verify_option__(option_name: str, option):
        """Verify TreeO-setting using the functions / types in __default_options__

        Args:
            option_name: name of the setting to verify
            option: the value to be verified

        Returns:
            the option-value if it was valid (otherwise the function is left in an error)
        """
        if option_name in TreeOMeta.__default_options__:
            opt_cls = TreeOMeta.__default_options__[option_name]
            if len(opt_cls) > 1 and not isinstance(option, opt_cls[1]):
                raise TypeError(
                    f"Can't apply {option_name} because {option_name} needs to be a {opt_cls[1].__name__}, "
                    f"and you provided a {option.__class__.__name__}."
                )
            if len(opt_cls) > 3 and not opt_cls[2](option):
                raise ValueError(opt_cls[3])
            return option
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
                "default": lambda x: repr(x),
            },
            MutableMapping,
            lambda x: all(
                k in ("default", "tuple_keys")
                or all(isinstance(y, type) for y in (k if TreeO.__is__(k, Iterable) else (k,)))
                and callable(v)
                for k, v in x.items()
            ),
            "mod_functions must be a dict with types (or tuples of types) as keys and function pointers "
            "(either lambda or wrapped in TFunc-objects) as values.",
        ),
        iter_fill=(...,),
        value_split=(" ", str, lambda x: bool(x), 'value_split can\'t be "", as a string can\'t be split by "".'),
        return_node=(False, bool),
    )
    """Default values for all options used in TreeO"""

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


class TCopy(Enum):
    """Enum-class representing the three different values the copy-parameter in TreeO can have

    NO_COPY:
        Directly modify the object, don't copy (default)

    SHALLOW:
        Create a shallow copy of the TreeO-object, modify that shallow copy and return it (leaves the calling TreeO
        object untouched). A shallow-copy creates references to the calling object as much as possible, and thus takes
        a lot less space in memory than a deep-copy. Therefore, a shallow-copy is normally preferred over a deep-copy.

    DEEP:
        Create a deep copy of the calling TreeO-object, modify that deep copy and return it (leaves the calling
        TreeO object untouched). A deep-copy is completely independent of the copied object, thus two deep-copied
        objects use twice as much memory as a single object.
    """

    NO_COPY = auto()
    SHALLOW = auto()
    DEEP = auto()


class TreeO(MutableMapping, MutableSequence, metaclass=TreeOMeta):
    """TreeO (TreeObject) is a wrapper-class for complex, nested objects of dicts and lists in Python.

    TreeO can be used as an object by instantiating it, but it's also possible to use all methods statically without
    even an object, so that a = {}; TreeO.set(a, "top med", 1) and a = TreeO({}); a.set(1, "top med") do the same.

    The base-object is always modified directly. If you don't want to change the base-object, all the functions where it
    makes sense support to rather modify a copy, and return that modified copy using the copy-parameter.

    Several parameters used in functions in TreeO work as settings so that you don't have to specify them each time you
    run a function. In the docstrings, these settings are marked with a *, e. g. the return_node parameter is a setting.
    Settings can be specified at three levels with increasing precedence: at class-level (TreeO.return_node = True), at
    object-level (a = TreeO(), a.return_node = True) and in each function-call (a.get("b", return_node=True)). If you
    generally want to change a setting, change it at class-level - all objects in that file will inherit this setting.
    If you want to change the setting specifically for one object, change the setting at object-level. If you only want
    to change the setting for one single run of a function, put it as a function-parameter. More thorough examples of
    settings can be found in README.md.
    """

    def get(
        self: Union[Mapping, Sequence],
        path: Iterable = "",
        default_value=...,
        return_node: bool = ...,
        copy: TCopy = TCopy.NO_COPY,
        value_split: str = ...,
    ) -> Any:
        """Retrieves value at path. If the value doesn't exist, default_value is returned.

        To get "hello" from x = TreeO({"a": ["b", {"c": "d"}], e: ["f", "g"]}), you can use x[("a", 1, "c")]. The tuple
        ("a", 1, "c") is the path-parameter that is used to traverse x. At first, the list at "a" is picked in the
        top-most dict, and then the 2nd element {"c": "d"} is picked from that list. Then, "d" is picked from {"c": "d"}
        and returned. The path-parameter can be a tuple or list, the keys must be either integers for lists, or any
        hashable objects for dicts. For convenience, the keys can also be put in a single string separated by
        value_split (default " "), so a["a 1 c"] also returns "d".

        \\* means that the parameter is a TreeO-Setting, see TreeO-class-docstring for more information about settings

        Args:
            path: List/Tuple of key-values to recursively traverse self. Can also be specified as string, that is split
                into a tuple using value_split
            default_value: * returned if path doesn't exist in self
            return_node: * returns a TreeO-object if the value at path is a list or dict
            copy: Option to return a copy of the returned value if it is a node. The default behaviour (TCopy.NO_COPY)
                is that if a node (dict, list) is returned and you make changes to that node, these changes will also
                be applied in the base-object from which get() was called. If you want the returned value to be
                independent, use either TCopy.SHALLOW or TCopy.DEEP (see docstring of TCopy for more information)
            value_split: * used to split path into a tuple if path is a string, default " "

        Returns:
            the value if the path exists, or default_value if it doesn't exist
        """
        node = self.obj if isinstance(self, TreeO) else self
        t_path = path.split(TreeO._opt(self, "value_split", value_split)) if isinstance(path, str) else tuple(path)
        if path:
            for node_name in t_path:
                try:
                    if TreeO.__is__(node, Mapping, Sequence):
                        node = node[node_name if isinstance(node, Mapping) else int(node_name)]
                    else:
                        node = TreeO._opt(self, "default_value", default_value)
                        break
                except (IndexError, ValueError, KeyError):
                    node = TreeO._opt(self, "default_value", default_value)
                    break
        if copy != TCopy.NO_COPY and TreeO.__is__(node, Mapping, Sequence):
            node = TreeO.__copy__(node) if copy == TCopy.SHALLOW else deepcopy(node)
        return (
            TreeO._child(self, node)
            if TreeO.__is__(node, Mapping, Sequence) and TreeO._opt(self, "return_node", return_node)
            else node
        )

    def _parent(
        self: Union[Mapping, Sequence], t_path: tuple, list_insert: int = ...
    ) -> Optional[Union[Mapping, Sequence]]:
        """Internal function retrieving the parent_node

        \\* means that the parameter is a TreeO-Setting, see TreeO-class-docstring for more information about settings

        Args:
            t_path: must already be a tuple, so a string from a calling path-function must already be split
            list_insert: * defines at which list-level a new node shall be inserted instead of traversing the tree. See
                docstring for set or README.md for more thorough documentation

        Returns:
            the parent node if it exists, otherwise None
        """
        node = self.obj if isinstance(self, TreeO) else self
        list_insert = TreeO._opt(self, "list_insert", list_insert)
        for node_name in t_path[:-1]:
            try:
                if TreeO.__is__(node, Mapping, Sequence):
                    node = node[node_name if isinstance(node, Mapping) else int(node_name)]
                    if TreeO.__is__(node, Sequence):
                        if list_insert == 1:
                            return None
                        list_insert -= 1
                else:
                    return None
            except (IndexError, ValueError, KeyError):
                return None
        return node

    def iter(
        self: Union[Mapping, Sequence],
        max_items: int = -1,
        path: Iterable = "",
        filter_: TFilter = None,
        return_node: bool = ...,
        iter_fill=...,
        reduce: Union[int, List[int]] = None,
        copy: TCopy = TCopy.NO_COPY,
        value_split: str = ...,
    ) -> list:
        """Recursively iterate through TreeO-object, starting at path

        Args:
            max_items: Defines the max amount of keys to have in a tuple. E. g. if max_items is four, it means that the
                keys of the three topmost nodes will be put in the tuple. The last element in the tuple contains the
                remaining part of the tree at that path as a dict / list. Default -1 (iterate as deeply as possible)
            path: Start iterating at path. Internally calls get(path), and iterates on the node get returns. See get()
            filter_: Only iterate over specific nodes defined using TFilter (see README.md and TFilter for more info)
            return_node: * If the leaf in the tuple is a dict or list, return it as a TreeO-object. This setting has no
                effect if max_items is -1.
            iter_fill: * Fill up tuples with iter_fill (can be any object, e. g. None) to ensure that all the tuples
                iter() returns are exactly max_items long. This can be useful if you want to unpack the keys / leaves
                from the tuples in a loop, which fails if the count of items in the tuples varies. This setting has no
                effect if max_items is -1. The default value is ..., meaning that the tuples are not filled, and the
                length of the tuples can vary. See README.md for a more thorough example.
            reduce: Extract only some specified values from the tuples. E. g. if ~ is -1, only the leaf-values are
                returned. ~ can also be a list of indices. Default None (don't reduce the tuples)
            value_split: * used to split path into a tuple if path is a string, default " "
            copy: Iterate on a copy to make sure that the base-object is not modified if one of the nodes iter() returns
                are modified. Often not necessary as an internal shallow copy is created for all the keys anyway. Only
                the leaves are returned as references if max_items isn't -1. Copy can make sure that these references
                in the leaves are pointing on a shallow- or deep copy of the base-object.

        Returns:
            list with one tuple for each leaf-node, containing the keys of the parent-nodes until the leaf
        """
        node = TreeO.get(self, path, [], False, copy, value_split)
        if isinstance(max_items, int) and 0 <= max_items <= 1 or max_items < -1:
            raise ValueError(
                "max_items must be either -1 to always iter to the leaf, or >= 2 to have up to that "
                "number of items in the tuples."
            )
        if isinstance(filter_, TFilter):
            if filter_.ttype != TType.DEFAULT:
                raise ValueError(
                    "The filter-object passed to iter always has to be a DEFAULT-filter. That filter can "
                    "contain CHECK- and VALUE-filters. See documentation of TFilter.Types for more information."
                )
            if not filter_.match_extra_filters(node):
                return []
        iter_list = TreeO._iter_r(
            self,
            node,
            max_items,
            TreeO._opt(self, "return_node", return_node),
            TreeO._opt(self, "iter_fill", iter_fill),
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

    def _iter_r(
        self: Union[Mapping, Sequence],
        node,
        max_items,
        return_node: bool,
        iter_fill,
        filter_: TFilter = None,
        index: int = 0,
    ):
        """Internal recursive function to facilitate iterating

        Args:
            node: the node to filter
            max_items: This value is decreased for each iteration to know how deep the recursion already is
            return_node: * this parameter is passed-through until it gets necessary
            iter_fill: * this parameter is passed-through until it gets necessary
            filter_: The filter to apply to the keys and values in this node
            index: index pointing on the argument in filter_ to use

        Returns:
            A list of elements that have been iterated over at this level (builds up in the recursion)
        """
        iter_list = []
        for k, v in node.items() if isinstance(node, Mapping) else enumerate(node):
            filter__, index_ = filter_, index + 1
            if filter_ is not None:
                if isinstance(node, Mapping):
                    match_k, filter__, index_ = filter_.match(k, index)
                elif isinstance(node, Sequence):
                    match_k, filter__, index_ = filter_.match_list(k, index, len(node))
                else:
                    match_k = True  # for a set, all the keys always match
                if not match_k:
                    continue
                if filter__ is not None:
                    if not filter__.match_extra_filters(v, index_):
                        continue
                    if TreeO.__is__(v, Collection):  # filter v if it is a leaf (either because it is a set or because
                        if max_items == 2 if isinstance(v, (Mapping, Sequence)) else True:  # of the limiting max_items)
                            v = TreeO._filter_r(v, filter__, index_)
                    elif not filter__.match(v, index_)[0]:  # check if value matches filter if value is no node
                        continue
            if max_items != 2 and TreeO.__is__(v, Collection):  # continue recursion while max_items != 2
                if isinstance(v, (Mapping, Sequence)):
                    iter_list.extend(
                        (k, *e) for e in TreeO._iter_r(self, v, max_items - 1, return_node, iter_fill, filter__, index_)
                    )
                else:
                    iter_list.extend(  # add all the elements in this Collection, filling up with iter_fill if necessary
                        (k, ..., e, *(() if iter_fill is ... else (iter_fill,) * (max_items - 3))) for e in v
                    )
                continue
            iter_list.append(
                (
                    k,
                    TreeO._child(self, v) if return_node and TreeO.__is__(v, Mapping, Sequence) else v,
                    *(() if iter_fill is ... else (iter_fill,) * (max_items - 2)),
                )
            )
        return iter_list

    def filter(
        self: Union[MutableMapping, MutableSequence],
        filter_: TFilter,
        path: Iterable = "",
        return_node: bool = ...,
        value_split: str = ...,
        copy: TCopy = TCopy.NO_COPY,
    ):
        obj = self.obj if isinstance(self, TreeO) else self
        if path:
            filtered = TreeO._filter_r(TreeO.get(obj, path, [], False, copy, value_split), filter_)
            if not filter_.match_extra_filters(filtered, 0):
                filtered.clear()
            TreeO.set(self, filtered, path)
        else:
            if copy != TCopy.NO_COPY:
                obj = TreeO.__copy__(obj) if copy == TCopy.SHALLOW else deepcopy(obj)
            filtered = TreeO._filter_r(obj, filter_)
            obj.clear()
            if filter_.match_extra_filters(filtered, 0):
                getattr(obj, "update" if isinstance(obj, MutableMapping) else "extend")(filtered)
        return TreeO._child(self, filtered) if TreeO._opt(self, "return_node", return_node) else filtered

    @staticmethod
    def _filter_r(node: Collection, filter_: Optional[TFilter], index: int = 0):
        if isinstance(node, Mapping):
            new_node, action = {}, None
        elif isinstance(node, Sequence):
            new_node, action = [], "append"
        else:
            new_node, action = set(), "add"
        for k, v in node.items() if isinstance(node, Mapping) else enumerate(node):
            if action == "add" or filter_ is None:
                match_k = True, filter_, index + 1
            elif isinstance(node, Mapping):
                match_k = filter_.match(k, index)
            else:
                match_k = filter_.match_list(k, index, len(node))
            if match_k[0]:
                if match_k[1] is None:
                    match_v = True
                elif TreeO.__is__(v, Collection):
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

    def set(
        self: Union[MutableMapping, MutableSequence],
        value,
        path: Iterable,
        node_types: str = ...,
        list_insert: int = ...,
        value_split: str = ...,
        return_node: bool = ...,
        default_node_type: str = ...,
        copy: TCopy = TCopy.NO_COPY,
    ):
        """Create (if they don't already exist) all sub-nodes in path, and finally set value at leaf-node

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO._build_node(
            self, value, path, "set", node_types, list_insert, value_split, return_node, default_node_type, copy
        )

    def append(
        self: Union[MutableMapping, MutableSequence],
        value,
        path: Iterable = "",
        node_types: str = ...,
        list_insert: int = ...,
        value_split: str = ...,
        return_node: bool = ...,
        default_node_type: str = ...,
        copy: TCopy = TCopy.NO_COPY,
    ):
        """Create (if they don't already exist) all sub-nodes in path, and finally append value to list at leaf-node

        If the leaf-node is a set, tuple or other value it is converted to a list. Then the new value is appended.

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO._build_node(
            self, value, path, "append", node_types, list_insert, value_split, return_node, default_node_type, copy
        )

    def extend(
        self: Union[MutableMapping, MutableSequence],
        values: Iterable,
        path: Iterable = "",
        node_types: str = ...,
        list_insert: int = ...,
        value_split: str = ...,
        return_node: bool = ...,
        default_node_type: str = ...,
        copy: TCopy = TCopy.NO_COPY,
    ):
        """Create (if they don't already exist) all sub-nodes in path. Then extend list at leaf-node with the new values

        If the leaf-node is a set, tuple or other value it is converted to a list. Then the new values are appended.

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO._build_node(
            self, values, path, "extend", node_types, list_insert, value_split, return_node, default_node_type, copy
        )

    def insert(
        self: Union[MutableMapping, MutableSequence],
        index: int,
        value,
        path: Iterable = "",
        node_types: str = ...,
        list_insert: int = ...,
        value_split: str = ...,
        return_node: bool = ...,
        default_node_type: str = ...,
        copy: TCopy = TCopy.NO_COPY,
    ):
        """Create (if they don't already exist) all sub-nodes in path. Insert new value at index in list at leaf-node

        If the leaf-node is a set, tuple or other value it is converted to a list. Then insert new value at index

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO._build_node(
            self,
            value,
            path,
            "insert",
            node_types,
            list_insert,
            value_split,
            return_node,
            default_node_type,
            copy,
            index,
        )

    def add(
        self: Union[MutableMapping, MutableSequence],
        value,
        path,
        node_types: str = ...,
        list_insert: int = ...,
        value_split: str = ...,
        return_node: bool = ...,
        default_node_type: str = ...,
        copy: TCopy = TCopy.NO_COPY,
    ):
        """Create (if they don't already exist) all sub-nodes in path, and finally add new value to set at leaf-node

        If the leaf-node is a list, tuple or other value it is converted to a list. Then the new values are added.

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO._build_node(
            self, value, path, "add", node_types, list_insert, value_split, return_node, default_node_type, copy
        )

    def update(
        self: Union[MutableMapping, MutableSequence],
        values: Iterable,
        path: Iterable = "",
        node_types=...,
        list_insert: int = ...,
        value_split: str = ...,
        return_node: bool = ...,
        default_node_type: str = ...,
        copy: TCopy = TCopy.NO_COPY,
    ):
        """Create (if they don't already exist) all sub-nodes in path, then update set at leaf-node with new values

        If the leaf-node is a list, tuple or other value it is converted to a set. That set is then updated with the new
        values. If the node at path is a dict, and values also is a dict, the node-dict is updated with the new values.

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO._build_node(
            self, values, path, "update", node_types, list_insert, value_split, return_node, default_node_type, copy
        )

    def _build_node(
        self: Union[MutableMapping, MutableSequence],
        value,
        path,
        action: str,
        node_types: str = ...,
        list_insert: int = ...,
        value_split: str = ...,
        return_node: bool = ...,
        default_node_type: str = ...,
        copy: TCopy = TCopy.NO_COPY,
        index: int = ...,
    ):
        if not TreeO.__is__(self, MutableMapping, MutableSequence):
            raise TypeError(f"Can't modify base object self having the immutable type {type(self).__name__}.")
        node_types = TreeO._opt(self, "node_types", node_types)
        obj = self.obj if isinstance(self, TreeO) else self
        if copy != TCopy.NO_COPY:
            obj = TreeO.__copy__(obj) if copy == TCopy.SHALLOW else deepcopy(obj)
        if path:
            t_path = path.split(TreeO._opt(self, "value_split", value_split)) if isinstance(path, str) else tuple(path)
            next_index = TreeO._index(t_path[0], ...)
            list_insert = TreeO._opt(self, "list_insert", list_insert)
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
                    and TreeO._opt(self, "default_node_type", default_node_type) == "l"
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
                            node.insert(node_key, TreeO._put_value(..., value, action, index))
                        else:
                            node[node_key] = TreeO._put_value(node[node_key], value, action, index)
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
                        node[node_key] = TreeO._put_value(node.get(node_key, ...), value, action, index)
                    else:
                        if not TreeO.__is__(node.get(node_key), MutableMapping, MutableSequence) and TreeO.__is__(
                            node.get(node_key), Iterable
                        ):
                            node[node_key] = (
                                dict(node[node_key].items())
                                if isinstance(node[node_key], Mapping)
                                else list(node[node_key])
                            )
                        elif node.get(node_key, _None) is _None:
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
                    obj.insert(index, value)
                else:
                    getattr(obj, action)(value)
            else:
                raise ValueError(f"Can't {action} value {'to' if action == 'add' else 'in'} base-{type(obj).__name__}.")
        return TreeO._child(self, obj) if TreeO._opt(self, "return_node", return_node) else obj

    @staticmethod
    def _index(value, default):
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _put_value(node, value, action, index):
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
                node.insert(index, value)
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

    def setdefault(
        self: Union[MutableMapping, MutableSequence],
        path: Iterable = "",
        default=...,
        node_types=...,
        list_insert: int = ...,
        value_split: str = ...,
        return_node: bool = ...,
        default_node_type: str = ...,
    ):
        """Get value at path and return it. If there is no value at path, set default at path, and return default."""
        t_path = path.split(TreeO._opt(self, "value_split", value_split)) if isinstance(path, str) else tuple(path)
        parent_node = TreeO._parent(self, t_path, list_insert)
        if TreeO.__is__(parent_node, Mapping, Sequence):
            original_value = TreeO.get(parent_node, t_path[-1], _None, return_node=False)
            if original_value is not _None:
                return original_value
        default_value = TreeO._opt(self, "default_value", default)
        TreeO.set(self, default_value, path, node_types, list_insert, value_split, False, default_node_type)
        return default_value

    def mod(
        self: Union[MutableMapping, MutableSequence],
        mod_function: Union[TFunc, callable],
        path,
        default=...,
        node_types: str = ...,
        replace_value=True,
        list_insert: int = ...,
        value_split: str = ...,
        default_node_type: str = ...,
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
        obj = self.obj if isinstance(self, TreeO) else self
        t_path = path.split(TreeO._opt(self, "value_split", value_split)) if isinstance(path, str) else tuple(path)
        parent_node = TreeO._parent(self, t_path, list_insert)
        if isinstance(parent_node, (MutableMapping, MutableSequence)):
            old_value = TreeO.get(parent_node, t_path[-1], _None, return_node=False)
            if old_value is not _None:
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
                    TreeO.set(parent_node, new_value, t_path[-1])
                return new_value
        default_value = TreeO._opt(self, "default_value") if default is ... else default
        TreeO.set(obj, default_value, path, node_types, list_insert, value_split, False, default_node_type)
        return default_value

    def pop(self: Union[MutableMapping, MutableSequence], path, value_split: str = ...):
        """Deletes the value at path and returns it"""
        t_path = path.split(TreeO._opt(self, "value_split", value_split)) if isinstance(path, str) else tuple(path)
        node = self.obj if isinstance(self, TreeO) else self
        for node_name in t_path[:-1]:
            try:
                node = node[node_name if isinstance(node, dict) else int(node_name)]
            except (IndexError, ValueError, KeyError):
                return
        return node.pop(int(t_path[-1]) if TreeO.__is__(node, Sequence) else t_path[-1])

    def serialize(
        self: Union[dict, list],
        mod_functions: MutableMapping = ...,
        path: Iterable = "",
        value_split: str = ...,
        copy: TCopy = TCopy.NO_COPY,
    ):
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
        node = TreeO.get(self, path, return_node=False, value_split=value_split)
        if copy != TCopy.NO_COPY:
            node = TreeO.__copy__(node) if copy == TCopy.SHALLOW else deepcopy(node)
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

    def _opt(self: Union[Mapping, Sequence], option_name: str, option=...):
        if option is not ...:
            return TreeO.__verify_option__(option_name, option)
        return (
            self._options[option_name]
            if isinstance(self, TreeO) and isinstance(self._options, dict) and option_name in self._options
            else getattr(TreeO, option_name)
        )

    def keys(self: Union[Mapping, Sequence], path: Iterable = "", value_split: str = ...):
        """Returns keys for node at path

        If node is iterable but not a dict, the indices are returned. If node is a single value, [0] is returned."""
        obj = TreeO.get(self, path, return_node=False, value_split=value_split)
        if isinstance(obj, MutableMapping):
            return obj.keys()
        elif TreeO.__is__(obj, Collection):
            return [x[0] for x in enumerate(obj)]
        else:
            return

    def values(
        self: Union[Mapping, Sequence],
        path: Iterable = "",
        value_split: str = ...,
        return_node: bool = ...,
        copy: TCopy = TCopy.NO_COPY,
    ):
        """Returns values for node at path"""
        obj = TreeO.get(self, path, value_split=value_split, return_node=False)
        return_node = TreeO._opt(self, "return_node", return_node)
        if isinstance(obj, MutableMapping):
            return [TreeO._child(self, x) for x in obj.values()] if return_node else obj.values()
        else:
            return [TreeO._child(self, x) for x in obj] if return_node else list(obj)

    def items(
        self: Union[Mapping, Sequence],
        path: Iterable = "",
        iter_fill=...,
        value_split: str = ...,
        return_node: bool = ...,
        copy: TCopy = TCopy.NO_COPY,
    ):
        """Returns a list with one tuple for each leaf - the first value is the key, the second is the child-dict."""
        return TreeO.iter(
            self, 2, path, iter_fill=iter_fill, value_split=value_split, return_node=return_node, copy=copy
        )

    def clear(
        self: Union[Mapping, Sequence],
        path: Iterable = "",
        return_node: str = ...,
        value_split: str = ...,
        copy: TCopy = TCopy.NO_COPY,
    ):
        """Removes all elements from node at path."""
        obj = self.obj if isinstance(self, TreeO) else self
        if copy != TCopy.NO_COPY:
            obj = TreeO.__copy__(obj) if copy == TCopy.SHALLOW else deepcopy(obj)
        TreeO.get(self, path, value_split=value_split, return_node=False).clear()
        return TreeO._child(self, obj) if TreeO._opt(self, "return_node", return_node) else obj

    def contains(self: Union[Mapping, Sequence], value, path: Iterable = "", value_split: str = ...):
        """Check if value is present in the node at path. Returns value == node if the node isn't iterable."""
        node = TreeO.get(self, path, return_node=False, value_split=value_split)
        return value in node if TreeO.__is__(node, Collection) else value == node

    def count(self: Union[Mapping, Sequence], path: Iterable = "", value_split: str = ...):
        """Get the number of child-nodes at path"""
        node = TreeO.get(self, path, _None, return_node=False, value_split=value_split)
        return len(node) if TreeO.__is__(node, Collection) else 0 if node is _None else 1

    def reversed(self: Union[Mapping, Sequence], path: Iterable = "", return_node: bool = ..., value_split: str = ...):
        """Get reversed child-node at path if that node is a list"""
        node = TreeO.get(self, path, value_split=value_split, return_node=False)
        if TreeO.__is__(node, Reversible):
            return (
                TreeO._child(self, list(reversed(node)))
                if TreeO._opt(self, "return_node", return_node)
                else reversed(node)
            )
        else:
            raise TypeError(f"Cannot reverse node of type {type(node).__name__}.")

    def reverse(
        self: Union[MutableMapping, MutableSequence],
        path: Iterable = "",
        return_node: bool = ...,
        value_split: str = ...,
        copy: TCopy = TCopy.NO_COPY,
    ):
        """Reverse child-node at path if that node is a list"""
        obj = self.obj if isinstance(self, TreeO) else self
        if copy != TCopy.NO_COPY:
            obj = TreeO.__copy__(obj) if copy == TCopy.SHALLOW else deepcopy(obj)
        node = TreeO.get(self, path, return_node=False, value_split=value_split)
        if TreeO.__is__(node, MutableSequence):
            node.reverse()
            return TreeO._child(self, obj) if TreeO._opt(self, "return_node", return_node) else obj
        else:
            raise TypeError(f"Cannot reverse node of type {type(node).__name__}.")

    def popitem(self):
        """This function is not implemented in TreeO"""
        pass

    def __init__(
        self,
        obj: Union[Mapping, Sequence] = None,
        node_types: str = ...,
        list_insert: int = ...,
        value_split: str = ...,
        default_node_type: str = ...,
        default_value=...,
        mod_functions: Mapping = ...,
        iter_fill=...,
        return_node: bool = ...,
        copy: TCopy = TCopy.NO_COPY,
    ):
        if obj is None:
            obj = [] if TreeO.default_node_type == "l" else {}
        if copy != TCopy.NO_COPY:
            obj = TreeO.__copy__(obj) if copy == TCopy.SHALLOW else deepcopy(obj)
        if isinstance(obj, TreeO):
            self.obj = obj()
            self._options = None if self._options is None else self._options.copy()
        else:
            self.obj = obj
            self._options = None
        for kw, value in locals().copy().items():
            if kw not in ("copy", "self", "obj") and value is not ...:
                setattr(self, kw, value)

    def _child(self: Union[Mapping, Sequence], obj: Union[Mapping, Sequence] = None, **kwargs) -> "TreeO":
        new_obj = TreeO(obj, **kwargs)
        if isinstance(self, TreeO):
            new_obj._options = None if self._options is None else self._options.copy()
        return new_obj

    def __copy__(self: Collection):
        obj = self.obj if isinstance(self, TreeO) else self
        new_node = obj.copy()
        for k, v in obj.items() if isinstance(obj, Mapping) else enumerate(obj):
            if hasattr(v, "copy"):
                new_node[k] = TreeO.__copy__(v) if TreeO.__is__(v, Collection) else v.copy()
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
        return "TreeO(%s)" % ", ".join(
            (repr(self.obj), *(f"{e[0]}={repr(e[1])}" for e in (self._options.items() if self._options else ())))
        )

    def __str__(self):
        return str(self.obj)

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
