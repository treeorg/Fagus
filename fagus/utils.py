"""This module contains classes and functions used across the Fagus-library that didn't fit in another module"""
import copy as cp
import re
import sys
from abc import ABCMeta
from collections.abc import MutableMapping, Iterable, Collection, Mapping, Sequence, MutableSet
from datetime import datetime, date, time
from typing import Union, Optional, TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .filters import Fil

END = sys.maxsize


class _None:
    """Dummy type used internally in TFilter and Fagus to represent non-existing while allowing None as a value"""

    pass


class FagusMeta(ABCMeta):
    """Metaclass for Fagus-objects to facilitate settings at class-level"""

    @staticmethod
    def __verify_option__(option_name: str, option):
        """Verify Fagus-setting using the functions / types in __default_options__

        Args:
            option_name: name of the setting to verify
            option: the value to be verified

        Returns:
            the option-value if it was valid (otherwise the function is left in an error)
        """
        if option_name in FagusMeta.__default_options__:
            opt_cls = FagusMeta.__default_options__[option_name]
            if len(opt_cls) > 1 and not isinstance(option, opt_cls[1]):
                raise TypeError(
                    f"Can't apply {option_name} because {option_name} needs to be a {opt_cls[1].__name__}, "
                    f"and you provided a {option.__class__.__name__}."
                )
            if len(opt_cls) > 3 and not opt_cls[2](option):
                raise ValueError(opt_cls[3])
            return option
        raise ValueError(f"The option named {option_name} is not defined in Fagus.")

    __default_options__ = dict(
        default_node_type=(
            "d",
            str,
            lambda x: x in ("d", "l"),
            'default_node_type must be either "d" for dict or "l" for list.',
        ),
        default=(None,),
        if_=(_None,),
        iter_fill=(_None,),
        iter_nodes=(False, bool),
        list_insert=(
            END,
            int,
            lambda x: x >= 0,
            "list-insert must be a positive int. By default (list_insert == END), all existing list-indices are "
            "traversed. If list-insert < maxsize, earliest at level n a new node is inserted if that node is a list",
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
                or all(isinstance(e, type) for e in (k if _is(k, Iterable) else (k,)))
                and callable(v)
                for k, v in x.items()
            ),
            "mod_functions must be a dict with types (or tuples of types) as keys and function pointers "
            "(either lambda or wrapped in TFunc-nodeects) as values.",
        ),
        node_types=(
            "",
            str,
            lambda x: bool(re.fullmatch("[dl ]*", x)),
            'The only allowed characters in node_types are d (for dict) and l (for list). " " can also be used. '
            "In that case, existing nodes are used if possible, and default_node_type is used to create new nodes.",
        ),
        fagus=(False, bool),
        value_split=(" ", str, lambda x: bool(x), 'value_split can\'t be "", as a string can\'t be split by "".'),
    )
    """Default values for all options used in Fagus"""

    no_node = (str, bytes, bytearray)

    def __new__(cls, name, bases, dct):
        node = super().__new__(cls, name, bases, dct)
        for option_name, option in FagusMeta.__default_options__.items():
            setattr(cls, option_name, option[0])
        return node

    def __setattr__(cls, attr, value):
        if attr == "no_node":
            if not (isinstance(value, tuple) and all(isinstance(e, type) for e in value)):
                raise ValueError(
                    "no_node must be a tuple of types. These are not treated as nodes, default (str, bytes, bytearray)."
                )
            FagusMeta.no_node = value
        else:
            super(FagusMeta, cls).__setattr__(
                attr,
                value
                if hasattr(FagusMeta, attr) or attr == "__abstractmethods__" or attr.startswith("_abc_")
                else FagusMeta.__verify_option__(attr, value),
            )

    def __delattr__(cls, attr):
        if attr == "no_node":
            FagusMeta.no_node = (str, bytes, bytearray)
        elif hasattr(cls, attr):
            super(FagusMeta, cls).__delattr__(attr)
        else:
            raise AttributeError(attr)


class Func:
    """This wrapper class allows you to run any function at places in the code that normally only accept lambdas"""

    def __init__(self, function_pointer: Callable, old_value_position: Union[int, str] = 1, *args, **kwargs):
        """Initializes TFunc-wrapper around function-pointer with optional args and kwargs

        Args:
            function_pointer: Points to the function that is supposed to be called by TFunc. Remember to put no ()
            old_value_position: Where to insert the old_value. If ~ is an int, the old value will be inserted as the
                nth (or nth last if negative) argument. If ~ is 0, the old value won't be inserted at all. ~ can also
                be a str, then the old value is inserted into kwargs with ~ as key. Default 1 (old value as first arg)
            *args: args to pass to function. Old value can be inserted into args (see old_value_position)
            **kwargs: keyword-arguments to pass to function. Old value can be added to kwargs (see old_value_position)
        """
        self.function_pointer = function_pointer
        self.old_pos = old_value_position
        self.middle_index = old_value_position in (-1, 0)
        if not self.middle_index and isinstance(self.old_pos, int):
            self.old_pos += 1 if old_value_position < 0 else -1
        self.args = args
        self.kwargs = kwargs

    def __call__(self, old_value):
        """Call the function in function-pointer with the specified args and kwargs.

        Args:
            old_value: The value to be modified by this function

        Returns:
            the modified value
        """
        if self.middle_index:
            if self.old_pos == 0:
                return self.function_pointer(*self.args, **self.kwargs)
            return self.function_pointer(*self.args, old_value, **self.kwargs)
        if isinstance(self.old_pos, str):
            return self.function_pointer(*self.args, **{**self.kwargs, self.old_pos: old_value})
        return self.function_pointer(*self.args[: self.old_pos], old_value, *self.args[self.old_pos :], **self.kwargs)


def _filter_r(node: Collection, copy: bool, filter_: Optional["Fil"], index: int = 0):
    """Internal recursive method that facilitates filtering

    Args:
        node: the node to filter
        copy: creates copies instead of directly referencing nodes included in the filter
        filter_: TFilter-nodeect in which the filtering-criteria are specified
        index: index in the current filter-nodeect

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
            elif _is(v, Collection):
                if match_k[1].match_extra_filters(v, match_k[2]):
                    v_old = v
                    v = _filter_r(v, copy, *match_k[1:])
                    match_v = bool(v_old) == bool(v)
                else:
                    match_v = False
            else:
                match_v, *_ = match_k[1].match(v, match_k[2])
            if match_v:
                if action:
                    getattr(new_node, action)(_copy_any(v) if copy else v)
                else:
                    new_node[k] = _copy_any(v) if copy else v
    return new_node


def _copy_node(node: Collection, recursive: bool = False) -> Collection:
    """Recursive function that creates a recursive shallow copy of node.

    This is needed as copy.copy() only creates a shallow copy at the base level, lower levels are just referenced.

    Args:
        node: node to be copied
        recursive: this parameter is internal. When you call this function, always keep it false (default)

    Returns:
        recursive shallow copy of node
    """
    if hasattr(node, "copy"):
        new_node = node if recursive else node.copy()
        if isinstance(node, (Mapping, Sequence)):
            for k, v in node.items() if isinstance(node, Mapping) else enumerate(node):
                collection = _is(v, Collection)
                if collection or hasattr(v, "copy"):
                    new_node[k] = _copy_node(v) if collection else v.copy()
        elif isinstance(new_node, MutableSet):  # must be a set or similar
            for v in node:
                collection = _is(v, Collection)
                if collection or hasattr(v, "copy"):
                    new_node.remove(v)
                    new_node.add(_copy_node(v) if collection else v.copy())
    elif not any(_is(v, Collection) or hasattr(v, "copy") for v in node):
        new_node = node
    elif isinstance(node, tuple):
        new_node = tuple(_copy_node(list(node), True))
    elif isinstance(node, frozenset):
        new_node = frozenset(_copy_node(set(node), True))
    else:
        new_node = cp.deepcopy(node)
    return new_node


def _copy_any(value, deep: bool = False):
    """Creates a copy of value. If deep is set, a deep copy is returned, otherwise a shallow copy is returned"""
    if deep:
        return cp.deepcopy(value)
    elif _is(value, Collection):
        return _copy_node(value)
    return cp.copy(value)


def _is(value, *args, is_not: Union[tuple, type] = None):
    """Override of isinstance, making sure that Sequence, Iterable or Collection doesn't match on str or bytearray

    Args:
        value: Value whose instance shall be checked
        *args: types to compare against

    Returns:
        whether the value is instance of one of the types in args (but not str, bytes or bytearray)"""
    if is_not is None:
        return not isinstance(value, FagusMeta.no_node) and isinstance(value, args)
    if isinstance(is_not, type):
        return not isinstance(value, FagusMeta.no_node + (is_not,)) and isinstance(value, args)
    return not isinstance(value, FagusMeta.no_node + is_not) and isinstance(value, args)
