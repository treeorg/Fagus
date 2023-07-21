"""This module contains filter-classes used in Fagus"""
import re
from collections.abc import Collection, MutableSequence, Mapping, Set, Sequence
from typing import Union, Any, Optional, Callable

from .utils import _None, _is

_RE_PATTERN = getattr(re, "Pattern" if hasattr(re, "Pattern") else "_pattern_type")


class FilBase:
    """FilterBase - base-class for all filters used in Fagus, providing basic functions shared by all filters"""

    def __init__(self, *filter_args: Any, inexclude: str = "") -> None:
        """Basic constructor for all filter-classes used in Fagus

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
                "%s is invalid for inexclude. It must be a str consisting of only + (to include) and - (to exclude). "
                "If nothing has been specified all filters will be treated as include (+)-filters." % inexclude
            )
        self.inexclude = inexclude
        self.args = list(filter_args)

    def included(self, index: int) -> bool:
        """This function returns if the filter should be an include-filter (+) or an exclude-filter (-) at a given index

        Args:
            index: index in filter-arguments that shall be interpreted as include- or exclude-filter

        Returns:
            bool that is True if it is an include-filter, and False if it is an Exclude-Filter, defaults to True if
                undefined at index
        """
        return self.inexclude[index : index + 1] != "-"

    def match_node(self, node: Collection[Any], _: Any = None) -> bool:
        """This method is overridden by CheckFilter and ValueFilter, and otherwise not in use"""
        return False


class VFil(FilBase):
    """ValueFilter - This special type of filter can be used to inspect the entire node

    It can be used to e.g. select all the nodes that contain at least 10 elements. See README for an example"""

    def __init__(self, *filter_args: Any, inexclude: str = "", invert: bool = False) -> None:
        """

        Args:
            *filter_args: Each argument filters one key in the tree, the last argument filters the leaf-value. You can
                put a list of values to match different values in the same filter. In this list, you can also specify
                subfilters to match different grains differently.
            inexclude: In some cases it's easier to specify that a filter shall match everything except b, rather than
                match a. ~ can be used to specify for each argument if the filter shall include it (+) or exclude it
                (-). Valid example: "++-+". If this parameter isn't specified, all args will be treated as (+).
            invert: Invert this whole filter to match if it doesn't match. E.g. if you want to select all the nodes
                that don't have a certain property.
        """
        if not all(callable(arg) or _is(arg, Collection) for arg in filter_args):
            raise TypeError(
                "The args of a value-filter must either be lambdas, "
                "or dicts / lists / sets the whole node is compared with."
            )
        self.invert = invert
        super().__init__(*filter_args, inexclude=inexclude)

    def match_node(self, node: Collection[Any], _: Any = None) -> bool:
        """Verify that a node matches ValueFilter

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


class KFil(FilBase):
    """KeyFilter - Base class for filters in Fagus that inspect key-values to determine whether the filter matched"""

    def __init__(self, *filter_args: Any, inexclude: str = "", str_as_re: bool = False) -> None:
        """Initializes KeyFilter and verifies the arguments passed to it

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

        Raises:
            TypeError: if the filters are not stacked correctly / stacked in a way that doesn't make sense
        """
        super().__init__(*filter_args, inexclude=inexclude)
        self.args = list(self.args)
        for i, arg in enumerate(self.args):
            if str_as_re and isinstance(arg, str) and arg != re.escape(arg):
                self[i] = re.compile(arg)
            elif _is(arg, Collection, is_not=Mapping):
                j = 0
                for e in arg:
                    if str_as_re and isinstance(e, str) and e != re.escape(e):
                        if not isinstance(self[i], MutableSequence):
                            self[i] = list(arg)
                        self[i][j] = re.compile(e)
                    elif isinstance(e, FilBase):
                        # Sort out CFil and VFil from args to extra_filters. Skip if Fil has a Fil as a child, or CFil
                        # has a CFil as a child
                        if isinstance(self, CFil) and isinstance(e, Fil):  # Alert if someone has put a
                            raise TypeError(  # Fil into a CFil, as that makes no sense.
                                "All subfilters of CFil must be either CFil or Fil."
                            )
                        if not isinstance(self, e.__class__):  # Move
                            if not isinstance(self[i], MutableSequence):
                                self[i] = list(arg)  # make self[i] a mutable list if necessary
                            self._set_extra_filter(i, self[i].pop(j))  # to be able to pop out the filter-arg
                            j -= 1
                            if not self[i]:  # if there only were C- and V-filters in the list, and it is now
                                self[i] = ...  # empty, put ... to give these filters something to match on
                    j += 1
            elif isinstance(arg, FilBase):
                if isinstance(self, Fil) and isinstance(arg, (CFil, VFil)):
                    self._set_extra_filter(i, arg)  # pop out extra-filter and replace it with ... so that
                    self[i] = ...  # it can match anything
                else:
                    raise TypeError(
                        "You can put a CFil or VFil as a standalone arg (in no list) into a Fil. It will then be "
                        "treated as: <<Check this filter, and pass the whole node if the filter matches>>. In any "
                        "other case it makes no sense to have a filter as a standalone argument in another."
                    )

    def _set_extra_filter(self, index: int, filter_: Union["CFil", VFil]) -> None:
        """Removes VFil / CFil from args and puts it into extra_filters"""
        if not hasattr(self, "extra_filters"):
            self.extra_filters: dict[int, list[Union["CFil", VFil]]] = {}
        if index not in self.extra_filters:
            self.extra_filters[index] = []
        self.extra_filters[index].append(filter_)

    def __getitem__(self, index: int) -> Any:
        """Get filter-argument at index

        Returns:
            filter-argument at index, _None if index isn't defined
        """
        try:
            return self.args[index]
        except IndexError:
            return _None

    def __setitem__(self, key: int, value: Any) -> None:
        """Set filter-argument at index. Throws IndexError if that index isn't defined"""
        self.args[key] = value

    def match(self, value: Any, index: int = 0, _: Any = None) -> tuple[bool, Optional["KFil"], int]:
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
            return (
                True,
                None,
                index + 1,
            )  # return True, and None as next filter to prevent unnecessary filtering
        for e in filter_arg if _is(filter_arg, Collection, is_not=Set) else (filter_arg,):
            if e is ...:
                return True, self, index + 1
            if isinstance(e, KFil):
                match, filter_, index_ = e.match(value, 0)  # recursion to correctly handle nested filters
            else:
                if callable(e):
                    match = e(value)
                elif isinstance(e, _RE_PATTERN):
                    match = bool(e.fullmatch(value))
                elif isinstance(e, Set):
                    match = value in e
                else:
                    match = e == value
                filter_, index_ = self, index + 1
            if included == match:
                return True, filter_, index_
        return False, self, index + 1

    def match_list(self, value: int, index: int = 0, node_length: int = 0) -> tuple[bool, Optional["KFil"], int]:
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
        for e in filter_arg if _is(filter_arg, Collection, is_not=Set) else (filter_arg,):
            if e is ...:
                return True, self, index + 1
            if isinstance(e, KFil):
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

    def match_extra_filters(self, node: Collection[Any], index: int = 0) -> bool:
        """Match extra filters on node (CFil and VFil).

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


class Fil(KFil):
    """TFilter - what matches this filter will actually be visible in the result. See README"""

    pass


class CFil(KFil):
    """CFil - can be used to select nodes based on values that shall not appear in the result. See README"""

    def __init__(self, *filter_args: Any, inexclude: str = "", str_as_re: bool = False, invert: bool = False) -> None:
        """Initializes KeyFilter and verifies the arguments passed to it

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

        Raises:
            TypeError: if the filters are not stacked correctly, or stacked in a way that doesn't make sense
        """
        self.invert = invert
        super().__init__(*filter_args, inexclude=inexclude, str_as_re=str_as_re)

    def match_node(self, node: Collection[Any], index: int = 0) -> bool:
        """Recursive function to completely verify a node and its subnodes in CFil

        Args:
            node: node to check
            index: index in filter to check (filter is self)

        Returns:
            bool whether the filter matched
        """
        match_key: Optional[Callable[[Any, int, Any], tuple[bool, Optional["KFil"], int]]] = None
        if isinstance(node, Mapping):
            match_key = self.match
        elif isinstance(node, Sequence):
            match_key = self.match_list
        for k, v in node.items() if isinstance(node, Mapping) else enumerate(node):
            match_k: tuple[bool, Optional["KFil"], int] = (
                match_key(k, index, len(node)) if match_key else (True, self, index)
            )
            if match_k[0] and match_k[1] is not None:
                if _is(v, Collection):
                    match_v = match_k[1].match_node(v, match_k[2])
                    if match_v:
                        match_v = match_k[1].match_extra_filters(v, match_k[2] - 1)
                else:
                    match_v, *_ = match_k[1].match(v, match_k[2])
                if match_v:
                    return True
        return False
