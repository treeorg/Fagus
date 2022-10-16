"""This module contains classes and functions used across the Fagus-library that didn't fit in another module"""
import copy as cp
import re
import sys
from abc import ABCMeta
from collections.abc import (
    Collection,
    Mapping,
    Sequence,
    MutableSet,
)
from typing import Union, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .filters import Fil

INF = sys.maxsize


class _None:
    """Dummy type used internally in TFilter and Fagus to represent non-existing while allowing None as a value"""

    pass


class FagusMeta(ABCMeta):
    """Metaclass for Fagus-objects to facilitate options at class-level"""

    @staticmethod
    def __verify_option__(option_name: str, option):
        """Verify Fagus-option using the functions / types in __default_options__

        Args:
            option_name: name of the option to verify
            option: the value to be verified

        Returns:
            the option-value if it was valid (otherwise the function is left in an error)
        """
        if option_name in FagusMeta.__default_options__:
            opt_cls = FagusMeta.__default_options__[option_name]
            if len(opt_cls) > 1 and not isinstance(option, opt_cls[1]):
                raise TypeError(
                    f"Can't apply {option_name} because {option_name} needs to be a {opt_cls[1].__name__}, "
                    f"got {option.__class__.__name__}."
                )
            if len(opt_cls) > 3 and not opt_cls[2](option):
                raise ValueError(opt_cls[3])
            return option
        raise ValueError(f"The option named {option_name} is not defined in Fagus.")

    __default_options__ = dict(
        default=(None,),
        default_node_type=(
            "d",
            str,
            lambda x: x in ("d", "l"),
            'default_node_type must be either "d" for dict or "l" for list.',
        ),
        fagus=(False, bool),
        if_=(_None,),
        iter_fill=(_None,),
        iter_nodes=(False, bool),
        list_insert=(
            INF,
            int,
            lambda x: x >= 0,
            "list-insert must be a positive int. By default (list_insert == INF), all existing list-indices are "
            "traversed. If list-insert < maxsize, earliest at level n a new node is inserted if that node is a list",
        ),
        node_types=(
            "",
            str,
            lambda x: bool(re.fullmatch("[dl ]*", x)),
            'The only allowed characters in node_types are d (for dict), l (for list) or " " for don\'t care. For " ", '
            "existing nodes are used if possible, and default_node_type is used to create new nodes. That is the "
            "default if ~ hasn't been explicitly specified for a key in path",
        ),
        path_split=(" ", str, lambda x: bool(x), 'path_split can\'t be "", as a string can\'t be split by "".'),
    )
    """Default values for all options used in Fagus"""

    no_node = (str, bytes, bytearray)  # if this is changed in class, change in __delattr__ as well
    """Every type of Collection in no_node will not be treated as a node, but as a single value"""

    _cls_options = {}

    def options(cls, options: dict = None, get_default_options: bool = False, reset: bool = False) -> dict:
        """Function to set multiple Fagus-options in one line

        Args:
            options: dict with options that shall be set
            get_default_options: return all options (include default-values). Default: only return options that are set
            reset: if ~ is set, all options are reset before options is set

        Returns:
            a dict of options that are set, or all options if get_default_options is set
        """
        if reset:
            cls._cls_options.clear()
        if options:
            cls._cls_options.update((k, cls.__verify_option__(k, v)) for k, v in options.items())
        if get_default_options:
            return {k: cls._cls_options.get(k, v[0]) for k, v in cls.__default_options__.items()}
        return {k: cls._cls_options[k] for k in cls.__default_options__ if k in cls._cls_options}

    def __setattr__(cls, attr, value):
        if attr == "no_node":
            if not (isinstance(value, tuple) and all(isinstance(e, type) for e in value)):
                raise ValueError(
                    "no_node must be a tuple of types. These are not treated as nodes, default (str, bytes, bytearray)."
                )
            FagusMeta.no_node = value
        elif attr in cls.__default_options__:
            FagusMeta._cls_options[attr] = cls.__verify_option__(attr, value)
        elif attr in ("__abstractmethods__", "__annotations__") or attr.startswith("_abc_"):
            super(FagusMeta, cls).__setattr__(attr, value)
        else:
            raise AttributeError(attr)

    def __getattr__(cls, attr):
        if attr in cls._cls_options:
            return cls._cls_options[attr]
        elif attr in cls.__default_options__:
            return cls.__default_options__[attr][0]
        return getattr(FagusMeta, attr)

    def __delattr__(cls, attr):
        if attr == "no_node":
            FagusMeta.no_node = (str, bytes, bytearray)
        elif attr in cls._cls_options:
            FagusMeta._cls_options.pop(attr)
        else:
            raise AttributeError(attr)


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

    This is needed as copy.copy() only creates a shallow copy at the root level, lower levels are just referenced.

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
