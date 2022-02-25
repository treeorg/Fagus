# ICS (Internet Software Consortium) License
#
# Copyright 2021 Lukas Neuenschwander
#
# Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby
# granted, provided that the above copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN
# AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.
import math
import copy as cp
import re
from abc import ABCMeta
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
)
from datetime import date, datetime, time
from typing import Union, Tuple, Any, Optional, List


class _None:
    """Dummy type used internally in TFilter and TreeO to represent non-existing while allowing None as a value"""

    pass


class TFilterBase:
    """Base-class for all filters used in TreeO, providing basic functions shared by all filters"""

    def __init__(self, *filter_args, inexclude: str = ""):
        """Basic constructor for all filter-classes used in TreeO

        Args:
            *filter_args: Each argument filters one key in the tree, the last argument filters the leaf-value. You can
                put a list of values to match different values in the same filter. In this list, you can also specify
                subfilters to match different grains differently.
            inexclude: In some cases it's easier to specify that a filter shall match everything except b, rather than
                match a. ~ can be used to specify for each argument if the filter shall include it (+) or exclude it
                (-). Valid example: "++-+". If this parameter isn't specified, all args will be treated as (+).
        """
        if not bool(re.fullmatch("[+-]*", inexclude)):
            raise ValueError(
                f"{inexclude} is invalid for inexclude. It must be a str consisting of only + (to include) and "
                f"- (to exclude). If nothing has been specified all filters will be treated as include (+)-filters."
            )
        self.inexclude = inexclude
        self.args = filter_args

    def included(self, index) -> bool:
        """This function returns if the filter should be an include-filter (+) or an exclude-filter (-) at a given index

        Args:
            index: index in filter-arguments that shall be interpreted as include- or exclude-filter

        Returns:
            bool that is True if it is an include-filter, and False if it is an Exclude-Filter, defaults to True if
                undefined at index
        """
        return self.inexclude[index : index + 1] != "-"

    def match_node(self, node: Collection, _=None) -> bool:
        """This method is overridden by TCheckFilter and TValueFilter, and otherwise not in use"""
        pass


class TValueFilter(TFilterBase):
    """This special type of filter can be used to inspect the entire node

    It can be used to e. g. select all the nodes that contain at least 10 elements. See README.md for an example"""

    def __init__(self, *filter_args, inexclude: str = "", invert: bool = False):
        """

        Args:
            *filter_args: Each argument filters one key in the tree, the last argument filters the leaf-value. You can
                put a list of values to match different values in the same filter. In this list, you can also specify
                subfilters to match different grains differently.
            inexclude: In some cases it's easier to specify that a filter shall match everything except b, rather than
                match a. ~ can be used to specify for each argument if the filter shall include it (+) or exclude it
                (-). Valid example: "++-+". If this parameter isn't specified, all args will be treated as (+).
            invert: Invert this whole filter to match if it doesn't match. E. g. if you want to select all the nodes
                that don't have a certain property.
        """
        if not all(callable(arg) or TreeO.__is__(arg, Collection) for arg in filter_args):
            raise TypeError(
                "The args of a value-filter must either be lambdas, "
                "or dicts / lists / sets the whole node is compared with."
            )
        self.invert = invert
        super().__init__(*filter_args, inexclude=inexclude)

    def match_node(self, node: Collection, _=None) -> bool:
        """Verify that a node matches TValueFilter

        Args:
            node: node to check
            _: this argument is ignored

        Returns:
            bool whether the filter matched
        """
        for i, arg in enumerate(self.args):
            if self.included(i) != (arg(node) if callable(arg) else node == arg):
                return False
        return True


class TKeyFilter(TFilterBase):
    """Base class for filters in TreeO that inspect key-values to determine whether the filter matched"""

    def __init__(self, *filter_args, inexclude: str = "", str_as_re: bool = False):
        """Initializes TKeyFilter and verifies the arguments passed to it

        Args:
            *filter_args: Each argument filters one key in the tree, the last argument filters the leaf-value. You can
                put a list of values to match different values in the same filter. In this list, you can also specify
                subfilters to match different grains differently.
            inexclude: In some cases it's easier to specify that a filter shall match everything except b, rather than
                match a. ~ can be used to specify for each argument if the filter shall include it (+) or exclude it
                (-). Valid example: "++-+". If this parameter isn't specified, all args will be treated as (+).
            str_as_re: If this is set to True, it will be evaluated for all str's if they'd match differently as a
                regex, and in the latter case match these strings as regex patterns. E.g. re.match("a.*", b) will match
                differently than "a.*" == b. In this case, "a.*" will be used as a regex-pattern. However
                re.match("abc", b) will give the same result as "abc" == b, so here "abc" == b will be used.
        """
        super().__init__(*filter_args, inexclude=inexclude)
        self.args = list(self.args)
        for i, arg in enumerate(self.args):
            if str_as_re and isinstance(arg, str) and arg != re.escape(arg):
                self[i] = re.compile(arg)
            elif TreeO.__is__(arg, Collection, is_not=Mapping):
                j = 0
                for e in arg:
                    if str_as_re and isinstance(e, str) and e != re.escape(e):
                        if not isinstance(self[i], MutableSequence):
                            self[i] = list(arg)
                        self[i][j] = re.compile(e)
                    elif isinstance(e, TFilterBase):
                        # Sort out TCheckFilter and TValueFilter from args to extra_filters. Skip if TFilter has a
                        # TFilter as a child, or TCheckFilter has a TCheckFilter as a child
                        if isinstance(self, TCheckFilter) and isinstance(e, TFilter):  # Alert if someone has put a
                            raise TypeError(  # TFilter into a TCheckFilter, as that makes no sense.
                                "All subfilters of TCheckFilter must be either TCheckFilter or TValueFilter."
                            )
                        elif not isinstance(self, e.__class__):  # Move
                            if not isinstance(self[i], MutableSequence):
                                self[i] = list(arg)  # make self[i] a mutable list if necessary
                            self._set_extra_filter(i, self[i].pop(j))  # to be able to pop out the filter-arg
                            j -= 1
                            if not self[i]:  # if there only were TCheck- and TValue-filters in the list and it is now
                                self[i] = ...  # empty, put ... to give these filters something to match on
                    j += 1
            elif isinstance(arg, TFilterBase):
                if isinstance(self, TFilter) and isinstance(arg, (TCheckFilter, TValueFilter)):
                    self._set_extra_filter(i, arg)  # pop out extra-filter and replace it with ... so that
                    self[i] = ...  # it can match anything
                else:
                    raise ValueError(
                        "You can put a TCheckFilter or TValueFilter as a standalone arg (in no list) into a TFilter. "
                        "It will then be treated as: <<Check this filter, and pass the whole node if the filter matches"
                        ">>. In any other case it makes no sense to have a filter as a standalone argument in another."
                    )

    def _set_extra_filter(self, index: int, filter_: Union["TCheckFilter", "TValueFilter"]):
        """Removes TValueFilter / TCheckFilter from args and puts it"""
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

    def match(self, value, index: int = 0, _=None) -> Tuple[bool, Optional["TKeyFilter"], int]:
        """match filter at index (matches recursively into subfilters if necessary)

        Args:
            value: the value to be matched against the filter
            index: index of filter-argument to check
            _: this argument is ignored

        Returns:
            whether the value matched the filter, the filter that matched (as it can be a subfilter), and the next index
                in that (sub)filter
        """
        filter_arg, included = self[index], self.included(index)
        if filter_arg is _None:  # this happens when the filter actually has no argument defined at this index
            return True, None, index + 1  # return True, and None as next filter to prevent unnecessary filtering
        for e in filter_arg if TreeO.__is__(filter_arg, Collection, is_not=Set) else (filter_arg,):
            if e is ...:
                return True, self, index + 1
            elif isinstance(e, TKeyFilter):
                match, filter_, index_ = e.match(value, 0)  # recursion to correctly handle nested filters
            else:
                if callable(e):
                    match = e(value)
                elif isinstance(e, re.Pattern) or str(type(e)) == "<type 'SRE_Pattern'>":
                    match = bool(e.fullmatch(value))
                elif isinstance(e, Set):
                    match = value in e
                else:
                    match = e == value
                filter_, index_ = self, index + 1
            if included == match:
                return True, filter_, index_
        return False, self, index + 1

    def match_list(self, value: int, index: int = 0, node_length: int = 0) -> Tuple[bool, Optional["TKeyFilter"], int]:
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
        for e in filter_arg if TreeO.__is__(filter_arg, Collection, is_not=Set) else (filter_arg,):
            if e is ...:
                return True, self, index + 1
            elif isinstance(e, TKeyFilter):
                match, filter_, index_ = e.match_list(value, 0, node_length)
            else:
                if callable(e):
                    match = e(value)
                elif isinstance(e, Set):
                    match = value in e
                else:
                    match = e == value
                filter_, index_ = self, index + 1
            if included == match:
                return True, filter_, index_
        return False, self, index + 1

    def match_extra_filters(self, node: Collection, index: int = 0) -> bool:
        """Match extra filters on node (TCheckFilter and TValueFilter).

        Args:
            node: node to be verified
            index: filter_index to check for extra filters

        Returns:
            bool whether the extra filters matched
        """
        if hasattr(self, "extra_filters") and index in self.extra_filters:
            for filter_ in self.extra_filters[index]:
                if filter_.invert == filter_.match_node(node):
                    return False
        return True


class TFilter(TKeyFilter):
    """Default TKeyFilter. What matches this filter will actually be visible in the result."""

    pass


class TCheckFilter(TKeyFilter):
    """TKeyFilter that can be used to select nodes based on values which you don't want to appear in the result."""

    def __init__(self, *filter_args, inexclude: str = "", str_as_re: bool = False, invert: bool = False):
        self.invert = invert
        super().__init__(*filter_args, inexclude=inexclude, str_as_re=str_as_re)

    def match_node(self, node: Collection, index: int = 0) -> bool:
        """Recursive function to completely verify a node and its subnodes in TCheckFilter

        Args:
            node: node to check
            index: index in filter to check (filter is self)

        Returns:
            bool whether the filter matched
        """
        match_key = None
        if isinstance(node, Mapping):
            match_key = self.match
        elif isinstance(node, Sequence):
            match_key = self.match_list
        for k, v in node.items() if isinstance(node, Mapping) else enumerate(node):
            match_k = match_key(k, index, len(node)) if match_key else (True, self, index)
            if match_k[0]:
                if TreeO.__is__(v, Collection):
                    match_v = match_k[1].match_node(v, match_k[2])
                    if match_v:
                        match_v = match_k[1].match_extra_filters(v, match_k[2] - 1)
                else:
                    match_v, *_ = match_k[1].match(v, match_k[2])
                if match_v:
                    return True
        return False


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
        self.old_pos = old_value_position
        self.middle_index = old_value_position in (-1, 0)
        if not self.middle_index:
            self.old_pos += 1 if old_value_position < 0 else -1
        self.args = args
        self.kwargs = kwargs

    def __call__(self, old_value):
        """Call function in function-pointer with the specified args and kwargs.

        Args:
            old_value: The value to be modified by this function

        Returns:
            the modified value
        """
        if self.middle_index:
            if self.old_pos == 0:
                return self.function_pointer(*self.args, **self.kwargs)
            return self.function_pointer(*self.args, old_value, **self.kwargs)
        elif isinstance(self.old_pos, str):
            return self.function_pointer(*self.args, **{**self.kwargs, self.old_pos: old_value})
        return self.function_pointer(*self.args[: self.old_pos], old_value, *self.args[self.old_pos :], **self.kwargs)


class TreeOMeta(ABCMeta):
    """Meta-class for TreeO-objects to facilitate settings at class-level"""

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
        iter_fill=(_None,),
        iter_nodes=(False, bool),
        is_not=((str, bytes, bytearray), tuple, lambda x: all(isinstance(e, type) for e in x)),
        list_insert=(
            0,
            int,
            lambda x: x >= 0,
            "List-insert must be a positive int. By default (list_insert == 0), "
            "all existing list-indices will be traversed. If list-insert > 0, a "
            "new node will be inserted in the n'th list that is traversed.",
        ),
        no_node=((str, bytes, bytearray), tuple, lambda x: all(isinstance(e, type) for e in x)),
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
                or all(isinstance(e, type) for e in (k if TreeO.__is__(k, Iterable) else (k,)))
                and callable(v)
                for k, v in x.items()
            ),
            "mod_functions must be a dict with types (or tuples of types) as keys and function pointers "
            "(either lambda or wrapped in TFunc-objects) as values.",
        ),
        node_types=(
            "",
            str,
            lambda x: bool(re.fullmatch("[dl]*", x)),
            "The only allowed characters in node_types are d (for dict) and l (for list).",
        ),
        return_node=(False, bool),
        value_split=(" ", str, lambda x: bool(x), 'value_split can\'t be "", as a string can\'t be split by "".'),
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
            if hasattr(TreeOMeta, attr) or attr == "__abstractmethods__" or attr.startswith("_abc_")
            else TreeOMeta.__verify_option__(attr, value),
        )


class TreeO(Mapping, Sequence, metaclass=TreeOMeta):
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
        self: Collection,
        path: Any = "",
        default_value=...,
        return_node: bool = ...,
        copy: bool = False,
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
            copy: Option to return a copy of the returned value. The default behaviour is that if there are subnodes
                (dicts, lists) in the returned values and you make changes to these nodes, these changes will also be
                applied in the base-object from which values() was called. If you want the returned values to be
                independent, use copy to get a shallow copy of the returned value
            value_split: * used to split path into a list if path is a string, default " "

        Returns:
            the value if the path exists, or default_value if it doesn't exist
        """
        node = self.obj if isinstance(self, TreeO) else self
        if isinstance(path, str):
            t_path = path.split(TreeO.opt(self, "value_split", value_split)) if path else ()
        else:
            t_path = tuple(path) if TreeO.__is__(path, Collection) else (path,)
        if t_path:
            for node_name in t_path:
                try:
                    if TreeO.__is__(node, Mapping, Sequence):
                        node = node[node_name if isinstance(node, Mapping) else int(node_name)]
                    else:
                        node = TreeO.opt(self, "default_value", default_value)
                        break
                except (IndexError, ValueError, KeyError):
                    node = TreeO.opt(self, "default_value", default_value)
                    break
        if copy:
            node = TreeO.copy_any(node)
        return (
            TreeO.child(self, node)
            if TreeO.__is__(node, Collection) and TreeO.opt(self, "return_node", return_node)
            else node
        )

    @staticmethod
    def _ensure_mutable_node(
        node: Collection, nodes: List[Collection], path: Sequence, empty_nodes: bool = True
    ) -> Union[MutableMapping, MutableSequence, MutableSet]:
        i = -1
        for i in range(i, -len(nodes) - 1, -1):
            node = nodes[i]
            if TreeO.__is__(node, MutableMapping, MutableSequence, MutableSet):
                break
            elif i == -len(nodes):
                raise TypeError(f"Can't modify base-object self having the immutable type {type(node).__name__}.")
        for i in range(i, -1):
            if i == -2 and TreeO.__is__(nodes[i + 1], Set, is_not=MutableSet):
                node[path[i]] = set(nodes[i + 1])
            else:
                node[path[i]] = (dict if isinstance(nodes[i + 1], Mapping) else list)(nodes[i + 1])
            node = node[path[i]]
        if empty_nodes:
            nodes.clear()
        return node

    def _mutable_parent(
        self: Collection, l_path: list, list_insert=0, default_value=None
    ) -> Optional[Union[MutableMapping, MutableSequence, MutableSet]]:
        """Internal function retrieving the parent_node, changing necessary nodes on the way to make it mutable

        Args:
            l_path: must already be a list, so a string from a calling path-function must already be split
            default_value: returned if path doesn't exist in self
            list_insert: defines at which list-level a new node shall be inserted instead of traversing the tree. See
                docstring for set or README.md for more thorough documentation. Default 0 (parameter is ignored)

        Returns:
            the parent node if it exists, otherwise None
        """
        node = self.obj if isinstance(self, TreeO) else self
        nodes = [node]
        try:
            for i in range(len(l_path) - 1):
                if isinstance(node, Sequence):
                    l_path[i] = int(l_path[i])
                    list_insert -= 1
                    if list_insert == 1:
                        return default_value
                node = node[l_path[i]]
                nodes.append(node)
            return TreeO._ensure_mutable_node(node, nodes, l_path)
        except (IndexError, ValueError, KeyError):
            return default_value

    def iter(
        self: Collection,
        max_items: int = -1,
        path: Any = "",
        filter_: TFilter = None,
        return_node: bool = ...,
        iter_fill=...,
        reduce: Union[int, Iterable] = None,
        copy: bool = False,
        iter_nodes: bool = ...,
        filter_ends: bool = False,
        value_split: str = ...,
    ) -> "TreeOIterator":
        """Recursively iterate through TreeO-object, starting at path

        \\* means that the parameter is a TreeO-Setting, see TreeO-class-docstring for more information about settings

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
            copy: Iterate on a shallow-copy to make sure that you can edit base-object without disturbing the iteration
            iter_nodes: * includes the traversed nodes into the resulting tuples, order is then:
                node1, key1, node2, key2, ..., leaf_value
            filter_ends: Affects the end dict/list that is returned if max_items is used. Normally, filters are not
                applied on that end node. If you would like to get the end node filtered too, set this to True. If this
                is set to True, the last nodes will always be copies (if unfiltered they are references)
            value_split: * used to split path into a list if path is a string, default " "

        Returns:
            TreeOIterator with one tuple for each leaf-node, containing the keys of the parent-nodes until the leaf
        """
        iter_fill = TreeO.opt(self, "iter_fill", iter_fill)
        node = TreeO.get(self, path, (), True, copy and iter_fill, value_split)
        if isinstance(max_items, int) and 0 <= max_items <= 1 or max_items < -1:
            raise ValueError(
                "max_items must be either -1 to always iter to the leaf, or >= 2 to have up to that "
                "number of items in the tuples."
            )
        if not TreeO.__is__(node, Collection) or isinstance(filter_, TFilter) and not filter_.match_extra_filters(node):
            node = TreeO.child(node, ())
        return TreeOIterator(
            node,
            max_items,
            filter_,
            TreeO.opt(self, "return_node", return_node),
            iter_fill,
            reduce,
            TreeO.opt(self, "iter_nodes", iter_nodes),
            copy and not iter_fill,
            filter_ends,
        )

    def filter(
        self: Collection,
        filter_: TFilter,
        path: Any = "",
        return_node: bool = ...,
        copy: bool = False,
        default_value=...,
        value_split: str = ...,
    ):
        """Filters self, only keeping the nodes that pass the filter

        \\* means that the parameter is a TreeO-Setting, see TreeO-class-docstring for more information about settings

        Args:
            filter_: TFilter-object in which the filtering-critera are specified
            path: at this point in self, the filtering will start (apply filter_ relatively from this point).
                Default "", meaning that the whole object is filtered, see get() and README for examples
            return_node: * return the filtered self as TreeO-object (default is just to return the filtered node)
            copy: Create a copy and filter on that copy. Default is to modify the object directly
            default_value: * returned if path doesn't exist in self, or the value at path can't be filtered
            value_split: * used to split path into a list if path is a string, default " "

        Returns:
            the filtered object, starting at path
        """
        if isinstance(path, str):
            l_path = path.split(TreeO.opt(self, "value_split", value_split)) if path else []
        else:
            l_path = list(path) if TreeO.__is__(path, Collection) else [path]
        if copy:
            parent_node = TreeO.get(self, l_path[:-1], _None, False, copy, value_split)
        else:
            parent_node = TreeO._mutable_parent(self, l_path, default_value=_None)
        node = _None if parent_node is _None else TreeO.get(parent_node, l_path[-1:], _None, False)
        if node is _None or not TreeO.__is__(node, Collection):
            filtered = TreeO.opt(self, "default_value", default_value)
        else:
            filtered = TreeO.filter_r(node, copy, filter_)
            if not filter_.match_extra_filters(node):
                filtered.clear()
            if not copy:
                if path:
                    parent_node[int(l_path[-1]) if isinstance(parent_node, Sequence) else l_path[-1]] = filtered
                else:
                    parent_node.clear()
                    getattr(parent_node, "extend" if isinstance(parent_node, MutableSequence) else "update")(filtered)
        return TreeO.child(self, filtered) if TreeO.opt(self, "return_node", return_node) else filtered

    @staticmethod
    def filter_r(node: Collection, copy: bool, filter_: Optional[TFilter], index: int = 0):
        """Internal recursive method that facilitates filtering

        Args:
            node: the node to filter
            copy: creates copies instead of directly referencing nodes included in the filter
            filter_: TFilter-object in which the filtering-critera are specified
            index: index in the current filter-object

        Returns:
            the filtered node
        """
        if isinstance(node, Mapping):
            new_node, action, match_key = {}, None, filter_.match if filter_ else None
        elif isinstance(node, Sequence):
            new_node, action, match_key = [], "append", filter_.match_list if filter_ else None
        else:
            new_node, action, match_key = set(), "add", None
        for k, v in node.items() if isinstance(node, Mapping) else enumerate(node):
            match_k = match_key(k, index, len(node)) if callable(match_key) else (True, filter_, index + 1)
            if match_k[0]:
                if match_k[1] is None:
                    match_v = True
                elif TreeO.__is__(v, Collection):
                    if match_k[1].match_extra_filters(v, match_k[2]):
                        v_old = v
                        v = TreeO.filter_r(v, copy, *match_k[1:])
                        match_v = bool(v_old) == bool(v)
                    else:
                        match_v = False
                else:
                    match_v, *_ = match_k[1].match(v, match_k[2])
                if match_v:
                    if action:
                        getattr(new_node, action)(TreeO.copy_any(v) if copy else v)
                    else:
                        new_node[k] = TreeO.copy_any(v) if copy else v
        return new_node

    def split(
        self: Collection,
        filter_: TFilter,
        path: Any = "",
        return_node: bool = ...,
        copy: bool = False,
        default_value=...,
        value_split: str = ...,
    ):
        """Filters self, only keeping the nodes that pass the filter

        \\* means that the parameter is a TreeO-Setting, see TreeO-class-docstring for more information about settings

        Args:
            filter_: TFilter-object in which the filtering-critera are specified
            path: at this point in self, the filtering will start (apply filter_ relatively from this point).
                Default "", meaning that the whole object is filtered, see get() and README for examples
            return_node: * return the filtered self as TreeO-object (default is just to return the filtered node)
            copy: Create a copy and filter on that copy. Default is to modify the object directly
            default_value: * returned if path doesn't exist in self, or the
            value_split: * used to split path into a list if path is a string, default " "

        Returns:
            the filtered object, starting at path
        """
        if isinstance(path, str):
            l_path = path.split(TreeO.opt(self, "value_split", value_split)) if path else []
        else:
            l_path = list(path) if TreeO.__is__(path, Collection) else [path]
        if copy:
            parent_node = TreeO.get(self, l_path[:-1], _None, False, copy, value_split)
        else:
            parent_node = TreeO._mutable_parent(self, l_path, default_value=_None)
        node = _None if parent_node is _None else TreeO.get(parent_node, l_path[-1:], _None, False)
        if node is _None or not TreeO.__is__(node, Collection):
            filter_out = TreeO.opt(self, "default_value", default_value)
            TreeO.set(self, filter_out, path, value_split=value_split)
            if copy:
                filter_in = filter_out.copy() if hasattr(filter_out, "copy") else filter_out
            else:
                return TreeO.child(self, filter_out) if TreeO.opt(self, "return_node", return_node) else filter_out

        else:
            filter_in, filter_out = TreeO.split_r(node, copy, filter_)
            if not filter_.match_extra_filters(node):
                filter_in.clear()
                filter_out = node
            if not copy:
                if path:
                    parent_node[int(l_path[-1]) if isinstance(parent_node, Sequence) else l_path[-1]] = filter_in
                else:
                    parent_node.clear()
                    getattr(parent_node, "extend" if isinstance(parent_node, MutableSequence) else "update")(filter_in)
                return TreeO.child(self, filter_out) if TreeO.opt(self, "return_node", return_node) else filter_out
        return (
            (TreeO.child(self, filter_in), TreeO.child(self, filter_out))
            if TreeO.opt(self, "return_node", return_node)
            else (filter_in, filter_out),
        )

    @staticmethod
    def split_r(node: Collection, copy: bool, filter_: Optional[TFilter], index: int = 0):
        """Internal recursive method that facilitates filtering

        Args:
            node: the node to filter
            copy: creates copies instead of directly referencing nodes included in the filter
            filter_: TFilter-object in which the filtering-critera are specified
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
                elif TreeO.__is__(v, Collection):
                    if match_k[1].match_extra_filters(v, match_k[2]):
                        v_in, v_out = TreeO.split_r(v, copy, *match_k[1:])
                        match_v = bool(v) == bool(v_in)
                else:
                    match_v, *_ = match_k[1].match(v, match_k[2])
                if match_v or v_in is not _None:
                    if v_in is _None:
                        v_in = v
                    if action:
                        getattr(filter_in, action)(TreeO.copy_any(v_in) if copy else v_in)
                    else:
                        filter_in[k] = TreeO.copy_any(v_in) if copy else v_in
            if not match_v or v_out is not _None:
                if v_out is _None:
                    v_out = v
                elif bool(v) != bool(v_out):
                    continue
                if action:
                    getattr(filter_out, action)(TreeO.copy_any(v_out) if copy else v_out)
                else:
                    filter_out[k] = TreeO.copy_any(v_out) if copy else v_out
        return filter_in, filter_out

    def set(
        self: Collection,
        value,
        path: Iterable,
        node_types: str = ...,
        list_insert: int = ...,
        value_split: str = ...,
        return_node: bool = ...,
        default_node_type: str = ...,
        copy: bool = False,
    ):
        """Create (if they don't already exist) all sub-nodes in path, and finally set value at leaf-node

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO._build_node(
            self, value, path, "set", node_types, list_insert, value_split, return_node, default_node_type, copy
        )

    def append(
        self: Collection,
        value,
        path: Any = "",
        node_types: str = ...,
        list_insert: int = ...,
        value_split: str = ...,
        return_node: bool = ...,
        default_node_type: str = ...,
        copy: bool = False,
    ):
        """Create (if they don't already exist) all sub-nodes in path, and finally append value to list at leaf-node

        If the leaf-node is a set, tuple or other value it is converted to a list. Then the new value is appended.

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO._build_node(
            self, value, path, "append", node_types, list_insert, value_split, return_node, default_node_type, copy
        )

    def extend(
        self: Collection,
        values: Iterable,
        path: Any = "",
        node_types: str = ...,
        list_insert: int = ...,
        value_split: str = ...,
        return_node: bool = ...,
        default_node_type: str = ...,
        copy: bool = False,
    ):
        """Create (if they don't already exist) all sub-nodes in path. Then extend list at leaf-node with the new values

        If the leaf-node is a set, tuple or other value it is converted to a list. Then the new values are appended.

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO._build_node(
            self, values, path, "extend", node_types, list_insert, value_split, return_node, default_node_type, copy
        )

    def insert(
        self: Collection,
        index: int,
        value,
        path: Any = "",
        node_types: str = ...,
        list_insert: int = ...,
        value_split: str = ...,
        return_node: bool = ...,
        default_node_type: str = ...,
        copy: bool = False,
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
        self: Collection,
        value,
        path: Any = "",
        node_types: str = ...,
        list_insert: int = ...,
        value_split: str = ...,
        return_node: bool = ...,
        default_node_type: str = ...,
        copy: bool = False,
    ):
        """Create (if they don't already exist) all sub-nodes in path, and finally add new value to set at leaf-node

        If the leaf-node is a list, tuple or other value it is converted to a list. Then the new values are added.

        node_types can be used to manually define if the nodes along path are supposed to be lists or dicts. If left
        empty, TreeO will try to use TreeO.default_node_type to create new nodes or just use the existing nodes."""
        return TreeO._build_node(
            self, value, path, "add", node_types, list_insert, value_split, return_node, default_node_type, copy
        )

    def update(
        self: Collection,
        values: Iterable,
        path: Any = "",
        node_types=...,
        list_insert: int = ...,
        value_split: str = ...,
        return_node: bool = ...,
        default_node_type: str = ...,
        copy: bool = False,
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
        self: Collection,
        value,
        path,
        action: str,
        node_types: str = ...,
        list_insert: int = ...,
        value_split: str = ...,
        return_node: bool = ...,
        default_node_type: str = ...,
        copy: bool = False,
        index: int = ...,
    ):
        node_types = TreeO.opt(self, "node_types", node_types)
        obj = self.obj if isinstance(self, TreeO) else self
        node = obj
        if copy:
            obj = TreeO.__copy__(obj)
        if isinstance(path, str):
            l_path = path.split(TreeO.opt(self, "value_split", value_split)) if path else []
        else:
            l_path = list(path) if TreeO.__is__(path, Collection) else [path]
        if l_path:
            next_index = TreeO._index(l_path[0], ...)
            list_insert = TreeO.opt(self, "list_insert", list_insert)
            default_node_type = TreeO.opt(self, "default_node_type", default_node_type)
            nodes = [obj]
            if (
                isinstance(obj, MutableMapping)
                and node_types[0:1] == "l"
                or TreeO.__is__(obj, MutableSequence)
                and (node_types[0:1] == "d" or next_index is ...)
            ):
                raise TypeError(
                    f"Your base object is a {type(obj).__name__}. Due to limitations in how references "
                    "work in Python, TreeO can't convert that base-object to a "
                    f"{'list' if node_types[0:1] == 'l' else 'dict'}, which was requested %s."
                    % (
                        f"because {l_path[0]} is no numeric list-index"
                        if TreeO.__is__(obj, MutableSequence) and not l_path[0].lstrip("-").isdigit()
                        else f"by the first character in node_types being {node_types[0:1]}"
                    )
                )
            for i in range(len(l_path)):
                node_key = next_index if TreeO.__is__(node, Sequence) else l_path[i]
                l_path[i] = node_key
                next_index = TreeO._index(l_path[i + 1], ...) if i < len(l_path) - 1 else ...
                next_node = (
                    Sequence
                    if node_types[i + 1 : i + 2] == "l"
                    or not node_types[i + 1 : i + 2]
                    and default_node_type == "l"
                    and next_index is not ...
                    else Mapping
                )
                if TreeO.__is__(node, Sequence):
                    if node_key is ...:
                        raise ValueError(f"Can't parse numeric list-index from {node_key}.")
                    elif node_key >= len(node):
                        if nodes:
                            node = TreeO._ensure_mutable_node(node, nodes, l_path[: i + 1])
                        node.append([] if next_node is Sequence else {})
                        node_key = -1
                    elif node_key < -len(node):
                        if nodes:
                            node = TreeO._ensure_mutable_node(node, nodes, l_path[: i + 1])
                        node.insert(0, [] if next_node is Sequence else {})
                        node_key = 0
                    if i == len(l_path) - 1:
                        if nodes:
                            node = TreeO._ensure_mutable_node(node, nodes, l_path[: i + 1])
                        if list_insert == 1:
                            node.insert(node_key, TreeO._put_value(_None, value, action, index))
                        else:
                            node[node_key] = TreeO._put_value(node[node_key], value, action, index)
                    else:
                        if list_insert == 1:
                            if nodes:
                                node = TreeO._ensure_mutable_node(node, nodes, l_path[: i + 1])
                            node.insert(node_key, [] if next_node is Sequence else {})
                        else:
                            next_node_type = (
                                Mapping
                                if isinstance(node[node_key], Mapping)
                                else (Sequence if TreeO.__is__(node[node_key], Sequence) else _None)
                            )
                            if next_node_type is _None or (
                                    next_node != next_node_type
                                    if node_types[i + 1: i + 2]
                                    else next_node_type is Sequence and next_index is ...
                            ):
                                if nodes:
                                    node = TreeO._ensure_mutable_node(node, nodes, l_path[: i + 1])
                                node[node_key] = [] if next_node is Sequence else {}
                        list_insert -= 1
                elif isinstance(node, Mapping):  # isinstance(node, dict)
                    if i == len(l_path) - 1:
                        if nodes:
                            node = TreeO._ensure_mutable_node(node, nodes, l_path[: i + 1])
                        node[node_key] = TreeO._put_value(node.get(node_key, _None), value, action, index)
                    else:
                        next_value = node.get(node_key, _None)
                        next_node_type = (
                            Mapping
                            if isinstance(next_value, Mapping)
                            else (Sequence if TreeO.__is__(next_value, Sequence) else _None)
                        )
                        if next_node_type is _None or (
                            next_node != next_node_type
                            if node_types[i + 1 : i + 2]
                            else next_node_type is Sequence and next_index is ...
                        ):
                            if nodes:
                                node = TreeO._ensure_mutable_node(node, nodes, l_path[: i + 1])
                            node[node_key] = [] if next_node is Sequence else {}
                node = node[node_key]
                if nodes:
                    nodes.append(node)
        else:
            if not TreeO.__is__(obj, MutableMapping, MutableSequence, MutableSet):
                raise TypeError(f"Can't modify base-object self having the immutable type {type(self).__name__}.")
            if isinstance(obj, MutableMapping) and action == "update":
                obj.update(value)
            elif isinstance(obj, MutableSequence) and action in ("append", "extend", "insert"):
                if action == "insert":
                    obj.insert(index, value)
                else:
                    getattr(obj, action)(value)
            elif isinstance(obj, MutableSet) and action in ("add", "update"):
                getattr(obj, action)(value)
            elif not action == "parent":
                raise TypeError(
                    f"Can't {action} value {'to' if action in ('add', 'append') else 'in'} base-{type(obj).__name__}."
                )
        return TreeO.child(self, obj) if TreeO.opt(self, "return_node", return_node) else obj

    @staticmethod
    def _index(value, default):
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _put_value(node: Union[Collection, type], value, action: str, index: int):
        if action == "set":
            return value
        elif action in ("append", "extend", "insert"):
            if not TreeO.__is__(node, MutableSequence):
                if TreeO.__is__(node, Iterable):
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
        self: Collection,
        path: Any = "",
        default_value=...,
        return_node: bool = ...,
        node_types: str=...,
        list_insert: int = ...,
        value_split: str = ...,
        default_node_type: str = ...,
    ):
        """Get value at path and return it. If there is no value at path, set default at path, and return default."""
        if isinstance(path, str):
            l_path = path.split(TreeO.opt(self, "value_split", value_split)) if path else []
        else:
            l_path = list(path) if TreeO.__is__(path, Collection) else [path]
        parent_node = TreeO._mutable_parent(self, l_path, TreeO.opt(self, "list_insert", list_insert), _None)
        if parent_node is _None:
            value = TreeO.opt(self, "default_value", default_value)
            TreeO.set(self, value, path, node_types, list_insert, value_split, False, default_node_type)
        else:
            value = TreeO.get(parent_node, l_path[-1], _None, return_node=False)
            if value is _None:
                value = TreeO.opt(self, "default_value", default_value)
                TreeO.set(self, value, path, node_types, list_insert, value_split, False, default_node_type)
        return (
            TreeO.child(self, value)
            if TreeO.opt(self, "return_node", return_node) and TreeO.__is__(value, Collection)
            else value
        )

    def mod(
        self: Collection,
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
        if isinstance(path, str):
            l_path = path.split(TreeO.opt(self, "value_split", value_split)) if path else []
        else:
            l_path = list(path) if TreeO.__is__(path, Collection) else [path]
        parent_node = TreeO._mutable_parent(self, l_path, list_insert=TreeO.opt(self, "list_insert", list_insert))
        if isinstance(parent_node, (MutableMapping, MutableSequence)):
            old_value = TreeO.get(parent_node, l_path[-1], _None, return_node=False)
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
                    parent_node[int(l_path[-1]) if isinstance(parent_node, Sequence) else l_path[-1]] = new_value
                return new_value
        default_value = TreeO.opt(self, "default_value") if default is ... else default
        TreeO.set(obj, default_value, path, node_types, list_insert, value_split, False, default_node_type)
        return default_value

    def pop(self: Collection, path: Any = "", default_value=..., return_node: bool = ..., value_split: str = ...):
        """Deletes the value at path and returns it

        \\* means that the parameter is a TreeO-Setting, see TreeO-class-docstring for more information about settings

        Args:
            path: pop value at this position in self, or don't do anything if path doesn't exist in self
            default_value: * returned if path doesn't exist in self
            return_node: * return the result as TreeO-object if possible (default is just to return the result)
            value_split: * used to split path into a list if path is a string, default " "

        Returns:
            value at path if it exists, or default_value if it doesn't
        """
        if isinstance(path, str):
            l_path = path.split(TreeO.opt(self, "value_split", value_split)) if path else []
        else:
            l_path = list(path) if TreeO.__is__(path, Collection) else [path]
        default_value = TreeO.opt(self, "default_value", default_value)
        node = TreeO._mutable_parent(self, l_path, default_value=default_value)
        try:
            if isinstance(node, MutableMapping):
                node = node.pop(l_path[-1])
            elif isinstance(node, MutableSequence):
                node = node.pop(int(l_path[-1]))
            elif isinstance(node, MutableSet):
                node.remove(l_path[-1])
                node = l_path[-1]
        except (IndexError, ValueError, KeyError):
            node = default_value
        return (
            TreeO.child(self, node)
            if TreeO.__is__(node, Collection) and TreeO.opt(self, "return_node", return_node)
            else node
        )

    def serialize(
        self: Union[dict, list],
        mod_functions: MutableMapping = ...,
        path: Any = "",
        value_split: str = ...,
        copy: bool = False,
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
        if copy:
            node = TreeO.__copy__(node)
        return TreeO._serialize_r(
            node,
            {
                **TreeO.opt(self, "mod_functions"),
                **(TreeOMeta.__verify_option__("mod_functions", {} if mod_functions is ... else mod_functions)),
            },
        )

    @staticmethod
    def _serialize_r(node: Union[MutableMapping, MutableSequence], mod_functions: MutableMapping):
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

    @staticmethod
    def __is__(value, *args, is_not: Union[tuple, type] = None):
        """Override of isinstance, making sure that Sequence, Iterable or Collection doesn't match on str or bytearray

        Args:
            value: Value whose instance shall be checked
            *args: types to compare against

        Returns:
            whether the value is instance of one of the types in args (but not str, bytes or bytearray)
        """
        if is_not is None:
            return not isinstance(value, TreeO.no_node) and isinstance(value, args)
        elif isinstance(is_not, type):
            return not isinstance(value, TreeO.no_node + (is_not,)) and isinstance(value, args)
        else:
            return not isinstance(value, TreeO.no_node + is_not) and isinstance(value, args)

    def opt(self: Collection, option_name: str, option=...):
        if option is not ...:
            return TreeO.__verify_option__(option_name, option)
        return (
            self._options[option_name]
            if isinstance(self, TreeO) and isinstance(self._options, dict) and option_name in self._options
            else getattr(TreeO, option_name)
        )

    def keys(self: Collection, path: Any = "", value_split: str = ...):
        """Returns keys for node at path

        If node is iterable but not a dict, the indices are returned. If node is a single value, [0] is returned."""
        obj = TreeO.get(self, path, return_node=False, value_split=value_split)
        if isinstance(obj, Mapping):
            return obj.keys()
        elif TreeO.__is__(obj, Sequence):
            return [x[0] for x in enumerate(obj)]

    def values(
        self: Collection,
        path: Any = "",
        value_split: str = ...,
        return_node: bool = ...,
        copy: bool = False,
    ) -> Collection:
        """Returns values for node at path

        Args:
            path: fetch values for this path, Default "" (gets values from the base node)
            value_split: * used to split path into a list if path is a string, default " "
            return_node: * converts sub-nodes into TreeO-objects in the returned list of values. Default false
            copy: Option to return a copy of the returned value. The default behaviour is that if there are subnodes
                (dicts, lists) in the returned values and you make changes to these nodes, these changes will also be
                applied in the base-object from which values() was called. If you want the returned values to be
                independent, use copy to get a shallow copy of the returned value

        Returns:
            values for the node at path. Returns an empty tuple if the value doesn't exist, or just the value in a
            tuple if the node isn't iterable.
        """
        node = TreeO.get(self, path, _None, value_split=value_split, return_node=False, copy=copy)
        if TreeO.__is__(node, Collection):
            if TreeO.opt(self, "return_node", return_node):
                values = list(node.values() if isinstance(node, Mapping) else node)
                for i, v in filter(lambda x: TreeO.__is__(x[1], Mapping, Sequence), enumerate(values)):
                    values[i] = TreeO.child(self, v)
                return values
            elif isinstance(node, Mapping):
                return node.values()
            else:
                return node
        elif node is _None:
            return ()
        return (node,)

    def items(
        self: Collection,
        path: Any = "",
        iter_fill=...,
        value_split: str = ...,
        return_node: bool = ...,
        copy: bool = False,
    ):
        """Returns a list with one tuple for each leaf - the first value is the key, the second is the child-dict."""
        return TreeO.iter(
            self, 2, path, iter_fill=iter_fill, value_split=value_split, return_node=return_node, copy=copy
        )

    def clear(
        self: Collection,
        path: Any = "",
        value_split: str = ...,
        copy: bool = False,
        return_node: bool = ...,
    ):
        """Removes all elements from node at path."""
        obj = TreeO.__copy__(self) if copy else self
        node = TreeO.get(obj, path, _None, value_split=value_split)
        if TreeO.__is__(node, Collection):
            node.clear()
        if isinstance(obj, TreeO):
            return obj if TreeO.opt(self, "return_node", return_node) else obj()
        return TreeO.child(self, obj) if TreeO.opt(self, "return_node", return_node) else obj

    def contains(self: Collection, value, path: Any = "", value_split: str = ...):
        """Check if value is present in the node at path. Returns value == node if the node isn't iterable."""
        node = TreeO.get(self, path, _None, return_node=False, value_split=value_split)
        return value in node if TreeO.__is__(node, Collection) else value == node

    def count(self: Collection, path: Any = "", value_split: str = ...):
        """Get the number of child-nodes at path"""
        node = TreeO.get(self, path, _None, return_node=False, value_split=value_split)
        return len(node) if TreeO.__is__(node, Collection) else 0 if node is _None else 1

    def reversed(
        self: Collection,
        path: Any = "",
        return_node: bool = ...,
        value_split: str = ...,
        copy: bool = False,
    ):
        """Get reversed child-node at path if that node is a list.

        Note that if you want to iterate reversed on this node with TreeO-child-nodes, use
        reversed(obj.values(path, ...,  return_node=True))

        \\* means that the parameter is a TreeO-Setting, see TreeO-class-docstring for more information about settings
        Args:
            path: position of reversible list in self
            return_node: * whether the returned list should be returned as a TreeO-object, default False
            value_split: * used to split path into a list if path is a string, default " "
            copy: Option to return a copy of the returned value. The default behaviour is that if there are subnodes
                (dicts, lists) in the returned values and you make changes to these nodes, these changes will also be
                applied in the base-object from which values() was called. If you want the returned values to be
                independent, use copy to get a shallow copy of the returned value

        Returns:
            the reversed node
        """
        node = TreeO.values(self, path, value_split, return_node, copy)
        if not TreeO.__is__(node, Reversible):
            node = tuple(node)
        return reversed(node)

    def reverse(
        self: Union[MutableMapping, MutableSequence],
        path: Any = "",
        return_node: bool = ...,
        value_split: str = ...,
        copy: bool = False,
    ):
        """Reverse child-node at path if that node is a list"""
        obj = self.obj if isinstance(self, TreeO) else self
        if copy:
            obj = TreeO.__copy__(obj)
        node = TreeO.get(self, path, return_node=False, value_split=value_split)
        if TreeO.__is__(node, MutableSequence):
            node.reverse()
            return TreeO.child(self, obj) if TreeO.opt(self, "return_node", return_node) else obj
        else:
            raise TypeError(f"Cannot reverse node of type {type(node).__name__}.")

    def popitem(self):
        """This function is not implemented in TreeO"""
        pass

    @staticmethod
    def node_type(node: Collection, check_mutable: bool = False) -> Union[Tuple[type, bool], type]:
        if check_mutable:
            if isinstance(node, MutableMapping):
                return Mapping, True
            elif TreeO.__is__(node, MutableSequence):
                return Sequence, True
            elif isinstance(node, MutableSet):
                return Set, True
            elif isinstance(node, Mapping):
                return Mapping, False
            elif TreeO.__is__(node, Sequence):
                return Sequence, False
            elif isinstance(node, Set):
                return Set, False
            elif isinstance(node, Iterable):
                return Iterable, False
            else:
                return type(node), False
        if isinstance(node, Mapping):
            return Mapping
        elif TreeO.__is__(node, Sequence):
            return Sequence
        elif isinstance(node, Set):
            return Set
        elif isinstance(node, Iterable):
            return Iterable
        else:
            return type(node)

    def merge(
        self: Collection,
        obj: Union["TreeOIterator", Collection],
        path: Any = "",
        copy: bool = False,
        copy_objects: bool = False,
        new_value_action: str = "r",
        extend_from: int = math.inf,
        update_from: int = math.inf,
        return_node: bool = ...,
        value_split: str = ...,
        node_types: str = ...,
        list_insert: int = ...,
        default_node_type: str = ...,
    ):
        """Merges two or more tree-objects to update and extend the base-object

        Args:
            obj: tree-object that shall be merged. Can also be a TreeOIterator returned from iter() to only merge
                values matching a filter defined in iter()
            path: position in base where the new objects shall be merged, default ""
            copy: Don't modify the base-object, modify and return a copy instead
            copy_objects: The objects to be merged are not modified, but references to subnodes of the objects can be
                put into the base-object. Set this to True to prevent that and keep base and objects independent
            new_value_action: This parameter defines what merge is supposed to do if a value at a path is present in the
                base and in one of the objects to merge. The possible values are: (r)eplace - the value in the base is
                replaced with the new value, this is the default behaviour; (i)gnore - the value in the base is not
                updated; (a)ppend - the old and new value are both put into a list, and thus aggregated
            extend_from: By default, lists are traversed, so the value at index i will be compared in both lists. If
                at some point you rather want to just append the contents from the objects to be merged, use this
                parameter to define the level (count of keys) from which lists should be extended isf traversed. Default
                infinite (never extend lists)
            update_from: Like extend_from, but for dicts. Allows you to define at which level the contents of the base
                should just be updated with the contents of the objects instead of traversing and comparing each value
            return_node: whether the returned tree-object should be returned as TreeO
            value_split: * used to split path into a list if path is a string, default " "

        Returns:
            a reference to the modified base object, or a modified copy of the base object (see copy-parameter)
        """
        if new_value_action[0:1] not in "ria":
            raise ValueError(
                f"Invalid new_value_action: {new_value_action}. Valid inputs: (r)eplace, (i)gnore or (a)ppend."
            )
        if isinstance(obj, TreeOIterator):
            object_ = obj.obj()
        elif TreeO.__is__(obj, Collection):
            object_ = obj.obj if isinstance(obj, TreeO) else obj
        else:
            raise TypeError(f"Can merge with TreeOIterator or Collection, but not with {type(obj).__name__}")
        if copy:
            node = TreeO.get(self, path, _None, False, True, value_split)
            if node is _None or not TreeO.__is__(node, Collection):
                return TreeO.child(self, object_) if TreeO.opt(self, "return_node", return_node) else object_
        else:
            if isinstance(path, str):
                t_path = path.split(TreeO.opt(self, "value_split", value_split)) if path else ()
            else:
                t_path = tuple(path) if TreeO.__is__(path, Collection) else [path]
            parent = TreeO._mutable_parent(self, t_path, list_insert=TreeO.opt(self, "list_insert", list_insert))
            node = TreeO.get(parent, t_path[-1:], _None)
            if node is _None or not TreeO.__is__(node, Collection):
                if t_path:
                    TreeO.set(parent, object_, t_path[-1])
                    return TreeO.child(self, object_) if TreeO.opt(self, "return_node", return_node) else object_
        base_nodes = [node]
        if isinstance(obj, TreeOIterator):
            obj_iter = obj
            obj_iter.__dict__.update(dict(return_node=False, iter_fill=_None, iter_nodes=True))
        elif TreeO.__is__(obj, Collection):
            obj_iter = TreeOIterator(obj if isinstance(obj, TreeO) else TreeO.child(self, obj), iter_nodes=True)
        else:
            raise TypeError(f"Can merge with TreeOIterator or Collection, but not with {type(obj).__name__}")
        node_type, mutable_node = TreeO.node_type(node, True)
        obj_type = TreeO.node_type(obj_iter.obj())
        if not extend_from or not update_from or node_type != obj_type or node_type == Set:
            if obj_type == Mapping:
                if node_type == Mapping and not update_from:
                    node.update(obj_iter.obj())
                    return TreeO.child(self, node) if TreeO.opt(self, "return_node", return_node) else node
            elif node_type == Set:
                node.update(obj_iter.obj())
                return TreeO.child(self, node) if TreeO.opt(self, "return_node", return_node) else node
            elif node_type == Sequence and not extend_from or obj_type != Sequence:
                node.extend(obj_iter.obj())
                return TreeO.child(self, node) if TreeO.opt(self, "return_node", return_node) else node
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
                node_type, mutable_node = TreeO.node_type(node, True)
                try:
                    for i, k in enumerate(path[1 + i * 2 : -3 : 2], start=i):
                        obj_node_type = TreeO.node_type(path[2 * i])
                        extend_sequence = extend_from <= i and node_type == Sequence
                        if extend_sequence or update_from <= i or node_type == Set:
                            if mutable_node:
                                TreeO._ensure_mutable_node(node, base_nodes, path[1:-1:2], False)
                                mutable_node = True
                            getattr(node, "extend" if extend_sequence else "update")(obj_iter.skip(i, copy_objects))
                            raise StopIteration
                        try:
                            if node_type == obj_node_type:
                                new_node = node[k]
                                if TreeO.__is__(new_node, Collection):
                                    node = new_node
                                    node_type, mutable_node = TreeO.node_type(node, True)
                                    base_nodes.append(node)
                        except (IndexError, KeyError):
                            if not mutable_node:
                                node = TreeO._ensure_mutable_node(node, base_nodes, path[1:-1:2], False)
                                mutable_node = True
                            if node_type == Mapping:
                                node[k] = obj_iter.skip(i + 1, copy_objects)
                            elif node_type == Sequence:
                                node.insert(k, obj_iter.skip(i + 1, copy_objects))
                            else:
                                node.add(obj_iter.skip(i + 1, copy_objects))
                            raise StopIteration
                except StopIteration:
                    continue
            old_value = TreeO.get(node, (path[2 * len(base_nodes) - 1],), _None)
            if old_value is _None:
                if not mutable_node:
                    node = TreeO._ensure_mutable_node(node, base_nodes, path[1 : 2 * len(base_nodes) : 2], False)
                    mutable_node = True
                if node_type == Mapping:
                    node[path[2 * len(base_nodes) - 1]] = path[-1]
                else:
                    getattr(node, "append" if node_type == Sequence else "add")(path[-1])
            else:
                if new_value_action[0:1] == "i":
                    continue
                elif new_value_action[0:1] == "a":
                    if TreeO.__is__(old_value, MutableSequence):
                        old_value.append(path[-1])
                        continue
                    new_value = [old_value, path[-1]]
                else:
                    new_value = path[2 * len(base_nodes)]
                if not mutable_node:
                    node = TreeO._ensure_mutable_node(node, base_nodes, path[1 : 2 * len(base_nodes) : 2], False)
                    mutable_node = True
                if node_type == Set:
                    node.add(new_value)
                elif new_value or not TreeO.__is__(new_value, Collection):
                    node[path[2 * len(base_nodes) - 1]] = new_value
        return TreeO.child(self, node) if TreeO.opt(self, "return_node", return_node) else node

    def __init__(
        self,
        obj: Collection = None,
        node_types: str = ...,
        list_insert: int = ...,
        value_split: str = ...,
        default_node_type: str = ...,
        default_value=...,
        mod_functions: Mapping = ...,
        iter_fill=...,
        return_node: bool = ...,
        copy: bool = False,
    ):
        if obj is None:
            obj = [] if TreeO.default_node_type == "l" else {}
        if copy:
            obj = TreeO.__copy__(obj)
        if isinstance(obj, TreeO):
            self.obj = obj()
            self._options = None if obj._options is None else obj._options.copy()
        else:
            self.obj = obj
            self._options = None
        for kw, value in locals().copy().items():
            if kw not in ("copy", "self", "obj") and value is not ...:
                setattr(self, kw, value)

    def child(self: Collection, obj: Collection = None, **kwargs) -> "TreeO":
        return TreeO(obj, **({**self._options, **kwargs} if isinstance(self, TreeO) and self._options else kwargs))

    def copy(self: Collection, deep: bool = False):
        if deep:
            return cp.deepcopy(self)
        return TreeO.__copy__(self)

    @staticmethod
    def copy_any(value, deep: bool = False):
        if deep:
            return cp.deepcopy(value)
        elif TreeO.__is__(value, Collection):
            return TreeO.__copy__(value)
        return cp.copy(value)

    def __copy__(self: Collection, recursive=False):
        obj = self.obj if isinstance(self, TreeO) else self
        if hasattr(obj, "copy"):
            new_node = obj if recursive else obj.copy()
            if isinstance(obj, (Mapping, Sequence)):
                for k, v in obj.items() if isinstance(obj, Mapping) else enumerate(obj):
                    collection = TreeO.__is__(v, Collection)
                    if collection or hasattr(v, "copy"):
                        new_node[k] = TreeO.__copy__(v) if collection else v.copy()
            elif isinstance(new_node, MutableSet):  # must be a set or similar
                for v in obj:
                    collection = TreeO.__is__(v, Collection)
                    if collection or hasattr(v, "copy"):
                        new_node.remove(v)
                        new_node.add(TreeO.__copy__(v) if collection else v.copy())
        elif not any(TreeO.__is__(v, Collection) or hasattr(v, "copy") for v in obj):
            new_node = obj
        elif isinstance(obj, tuple):
            new_node = tuple(TreeO.__copy__(list(obj), True))
        elif isinstance(obj, frozenset):
            new_node = frozenset(TreeO.__copy__(set(obj), True))
        else:
            new_node = cp.deepcopy(self)
        return TreeO.child(self, new_node) if isinstance(self, TreeO) else new_node

    def __call__(self):
        return self.obj

    def __getattr__(self, attr):  # Enable dot-notation for getting dict-keys at the top-level
        if attr == "obj":
            return self.obj
        elif hasattr(TreeO, attr):
            if isinstance(self._options, dict):
                return self._options.get(attr, getattr(TreeO, attr))
            return getattr(TreeO, attr)
        else:
            return self.get(attr.lstrip(TreeO.opt(self, "value_split") if isinstance(attr, str) else attr))

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
            self.set(value, attr.lstrip(TreeO.opt(self, "value_split") if isinstance(attr, str) else attr))

    def __setitem__(self, path, value):  # Enable [] for setting items for dict-keys at the top-level
        self.set(value, path)

    def __delattr__(self, path):  # Enable dot-notation for deleting items for dict-keys at the top-level
        if hasattr(TreeO, path):
            if path in self._options:
                del self._options[path]
                if not self._options:
                    self._options = None
        else:
            self.pop(path.lstrip(TreeO.opt(self, "value_split") if isinstance(path, str) else path))

    def __delitem__(self, path):  # Enable [] for deleting items at dict-keys at the top-level
        self.pop(path)

    def __iter__(self):
        return iter(self.obj if isinstance(self.obj, Mapping) else self.values())

    def __eq__(self, other):
        return isinstance(other, TreeO) and self.obj == other.obj

    def __ne__(self, other):
        return not isinstance(other, TreeO) or self.obj != other.obj

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
        self.merge(value)
        return self

    def __add__(self, other):
        res = TreeO.merge(self, other, copy=True)
        return self.child(res) if TreeO.opt(self if isinstance(self, TreeO) else other, "return_node") else res

    def __radd__(self, other):
        res = TreeO.merge(other if isinstance(other, TreeO) else self.child(other), self, copy=True)
        return self.child(res) if TreeO.opt(self if isinstance(self, TreeO) else other, "return_node") else res

    def __sub__(self, other):
        obj = self() if isinstance(self, TreeO) else self
        other = set(other() if isinstance(other, TreeO) else other) if TreeO.__is__(other, Iterable) else (other,)
        if isinstance(obj, Mapping):
            res = {k: v for k, v in obj.items() if k in other}
        else:  # isinstance(self(), Sequence):
            res = list(filter(lambda x: x not in other, obj))
        return self.child(res) if TreeO.opt(self if isinstance(self, TreeO) else other, "return_node") else res

    def __rsub__(self, other):
        return TreeO.__sub__(other, self)

    def __mul__(self, times: int):
        if not isinstance(times, int):
            raise TypeError("To use the * (times)-operator, times must be an int")
        if not TreeO.__is__(self(), Sequence):
            raise TypeError("Your base-object must a tuple or list to get multiplied.")
        return self.child(self() * times) if TreeO.opt(self, "return_node") else self() * times

    def __rmul__(self, other):
        return TreeO.__mul__(self, other)

    def __reversed__(self: Collection):
        return TreeO.reversed(self)


class FilteredIterator:
    """Iterator class that gives keys and values for any object (use optimal_iterator() to initialize it)"""

    @staticmethod
    def optimal_iterator(obj: Collection, filter_value: bool = False, filter_: TFilter = None, filter_index: int = 0):
        """This method returns the simplest possible Iterator to loop through a given object.

        If no filter is present, either items or enumerate are called to loop through the keys, for sets ... is put
        as key for each value (as sets have no meaningful keys). If you additionally need filtering, this class is
        initialized to support iteration on only the keys and values that pass the filter"""
        if filter_ is None:
            if isinstance(obj, Sequence):
                return iter(enumerate(obj))
            elif isinstance(obj, Mapping):
                return iter(obj.items())
            else:
                return ((..., e) for e in obj)
        else:
            return FilteredIterator(obj, filter_value, filter_, filter_index)

    def __init__(self, obj: Collection, filter_value: bool, filter_: TFilter, filter_index: int = 0):
        self.filter_ = filter_
        self.filter_index = filter_index
        self.filter_value = filter_value
        if isinstance(obj, Mapping):
            self.match_key = self.filter_.match
        elif isinstance(obj, Sequence):
            self.match_key = self.filter_.match_list
        else:
            self.match_key = lambda *_: (True, self.filter_, self.filter_index + 1)
        self.obj = obj
        self.iter = self.optimal_iterator(obj)

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            k, v = next(self.iter)
            match_k, filter_, index = self.match_key(k, self.filter_index, len(self.obj))
            if not match_k:
                continue
            if filter_ is not None:
                if not filter_.match_extra_filters(v, index):
                    continue
            if TreeO.__is__(v, Collection):  # filter v if it is a leaf (either because it is a set or because
                if self.filter_value if isinstance(v, (Mapping, Sequence)) else True:  # of the limiting max_items)
                    v = TreeO.filter_r(v, False, filter_, index)
            elif filter_ and not filter_.match(v, index)[0]:
                continue
            return k, v, filter_, index


class TreeOIterator:
    """Iterator-class for TreeO to facilitate the complex iteration with filtering etc. in the tree-object

    Internal - use TreeO.iter() to use this iterator on your object"""

    def __init__(
        self,
        obj: TreeO,
        max_items: int = -1,
        filter_: TFilter = None,
        return_node: bool = False,
        iter_fill=_None,
        reduce: Union[int, Iterable] = None,
        iter_nodes: bool = False,
        copy: bool = False,
        filter_ends: bool = False,
    ):
        """Internal function. Recursively iterates through TreeO-object

        Initiate this iterator through TreeO.iter(), there the parameters are discussed as well. It should not be
        initialized directly"""
        self.obj = obj
        self.max_items = math.inf if max_items == -1 else max_items
        self.return_node = return_node
        self.iter_fill = iter_fill
        self.filter_ends = filter_ends
        self.copy = copy
        if not (
            reduce is None
            or isinstance(reduce, int)
            or isinstance(reduce, Iterable)
            and all(isinstance(e, int) for e in reduce)
        ):
            raise TypeError(f"Invalid type {type(reduce).__name__} for reduce parameter. Must be int or list of ints.")
        self.reduce = reduce
        self.iter_nodes = iter_nodes
        self.iter_keys = [obj if return_node else obj()]
        self.iterators = [FilteredIterator.optimal_iterator(obj(), max_items == 2, filter_)]
        self.deepest_change = 0

    def __iter__(self):
        return self

    def __next__(self):
        self.deepest_change = len(self.iterators) - 1
        while True:
            try:
                try:
                    k, v, *filter_ = next(self.iterators[-1])
                except IndexError:
                    raise StopIteration
                if len(self.iterators) + 1 < self.max_items and v and TreeO.__is__(v, Collection):
                    self.iter_keys.extend((k, self.obj.child(v) if self.return_node else v))
                    self.iterators.append(
                        FilteredIterator.optimal_iterator(
                            v, self.filter_ends and len(self.iterators) < self.max_items, *filter_
                        )
                    )
                else:
                    if self.return_node and TreeO.__is__(v, Collection):
                        v = self.obj.child(v)
                    iter_list = (
                        *(self.iter_keys if self.iter_nodes else self.iter_keys[1::2]),
                        k,
                        TreeO.copy_any(v) if self.copy else v,
                        *(
                            (self.iter_fill,) * (self.max_items - len(self.iterators) - 1)
                            if self.iter_fill is not _None and self.max_items < math.inf
                            else ()
                        ),
                    )
                    if self.reduce is not None:
                        if isinstance(self.reduce, int):
                            return iter_list[self.reduce]
                        return tuple(iter_list[i] for i in self.reduce if -len(iter_list) <= i < len(iter_list))
                    return iter_list
            except StopIteration:
                try:
                    self.iterators.pop()
                    del self.iter_keys[-2:]
                    self.deepest_change = len(self.iterators) - 1
                except IndexError:
                    raise StopIteration

    def skip(self, level: int, copy: bool = False) -> Collection:
        node = self.iter_keys[level * 2]
        if isinstance(self.iterators[-1], FilteredIterator):
            node = TreeO.filter_r(node, copy, self.iterators[level].filter_, self.iterators[level].filter_index)
        else:
            node = TreeO.__copy__(node)
        del self.iterators[level:]
        del self.iter_keys[level * 2 - 1 :]
        return node
