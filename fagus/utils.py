"""This module contains classes and functions used across the Fagus-library that didn't fit in another module"""

import copy as cp
import re
import sys
from abc import ABCMeta
import collections.abc as c_abc
from typing import (
    Union,
    Optional,
    TYPE_CHECKING,
    Any,
    cast,
    Callable,
    Tuple,
    Dict,
    Collection,
)

if sys.version_info < (3, 10):
    from typing_extensions import TypeAlias
else:
    from typing import TypeAlias


__all__ = ("INF", "FagusOption", "EllipsisType", "OptStr", "OptBool", "OptInt", "OptAny")


if TYPE_CHECKING:
    from .filters import KFil

INF = sys.maxsize


class _None:
    """Dummy type used internally in TFilter and Fagus to represent non-existing while allowing None as a value"""

    pass


EllipsisType: TypeAlias = type(...)  # type: ignore
"""TypeAlias to represent type(...), which cannot be done in a nicer way prior to Python 3.10"""

OptStr: TypeAlias = Union[str, EllipsisType]
"""TypeAlias for FagusOption requiring a str. Specify custom value as str, or keep ... to use FagusOption default."""
OptBool: TypeAlias = Union[bool, EllipsisType]
"""TypeAlias for FagusOption requiring a bool. Specify custom value as bool, or keep ... to use FagusOption default."""
OptInt: TypeAlias = Union[int, EllipsisType]
"""TypeAlias for FagusOption requiring an int. Specify custom value as int, or keep ... to use FagusOption default."""
OptAny: TypeAlias = Any
"""TypeAlias for FagusOption taking any object. Specify custom value, or keep ... to use FagusOption default."""


class FagusOption:
    """Helper class to facilitate Fagus options."""

    def __init__(
        self,
        name: str,
        default: Any,
        type_: type = type(Any),
        verify_function: Callable[[Any], bool] = lambda x: True,
        verify_error_msg: Optional[str] = None,
    ) -> None:
        """Initializes FagusOption with the given parameters

        Args:
            name (str): The name of the option.
            default (Any): The default value for the option if it hasn't been set explicitly at class- or instance
                level or in the function.
            type_ (type): The expected type for the input to the option. Defaults to Any. In case the provided
                input to the option doesn't have the type indicated here, an error-message is thrown.
            verify_function (Callable[[Any], bool]): A function to verify the input value to the option. Returns a bool
                whether the input was valid or not. An error is thrown if the input isn't valid with the error message
                defined in verify_error_message. Defaults to `lambda x: True`, meaning that any input is valid
            verify_error_msg (Optional[str]): An error message to display when the verify_function returns False.
                Defaults to f"{value} is not a valid value for {self.name}"

        Returns:
            None
        """
        self.name = name
        self.default = default
        self.type_ = type_
        self.verify_function = verify_function
        self.verify_error_msg = verify_error_msg

    def verify(self, value: Any) -> Any:
        """Verifies if the input value to the option has the correct type and passes the validation function.

        Args:
            value (Any): The option input value to be verified.

        Raises:
            TypeError: If the input value is not of the expected type.
            ValueError: If the input value does not pass the custom validation function.

        Returns:
            Any: The input value if it meets the requirements.
        """
        if not isinstance(value, object if self.type_ is type(Any) else self.type_):
            raise TypeError(
                f"Can't apply {self.name} because {self.name} needs to be a {self.type_.__name__}, "
                f"got {type(value).__name__}."
            )
        if not self.verify_function(value):
            raise ValueError(
                self.verify_error_msg if self.verify_error_msg else f"{value} is not a valid value for {self.name}"
            )
        return value


class FagusMeta(ABCMeta):
    """Metaclass for Fagus-objects to facilitate options at class-level"""

    @staticmethod
    def __verify_option__(option_name: str, option: Any) -> Any:
        """Verify Fagus-option using the functions / types in __default_options__

        Args:
            option_name: name of the option to verify
            option: the value to be verified

        Raises:
            ValueError: If the option name is not defined in Fagus.

        Returns:
            the option-value if it was valid (otherwise the function is left in an error)
        """
        if option_name in FagusMeta.__default_options__:
            return FagusMeta.__default_options__[option_name].verify(option)
        raise ValueError(f"The option named {option_name} is not defined in Fagus.")

    __default_options__: Dict[str, FagusOption] = dict(
        default=FagusOption(
            "default",
            None,
        ),
        default_node_type=FagusOption(
            "default_node_type",
            "d",
            str,
            lambda x: x in ("d", "l"),
            'default_node_type must be either "d" for dict or "l" for list.',
        ),
        fagus=FagusOption("fagus", False, bool),
        if_=FagusOption(
            "if_",
            _None,
        ),
        iter_fill=FagusOption(
            "iter_fill",
            _None,
        ),
        iter_nodes=FagusOption("iter_nodes", False, bool),
        list_insert=FagusOption(
            "list_insert",
            INF,
            int,
            lambda x: x >= 0,
            "list-insert must be a positive int. By default (list_insert == INF), all existing list-indices are "
            "traversed. If list-insert < maxsize, earliest at level n a new node is inserted if that node is a list",
        ),
        node_types=FagusOption(
            "node_types",
            "",
            str,
            lambda x: bool(re.fullmatch("[dl ]*", x)),
            'The only allowed characters in node_types are d (for dict), l (for list) or " " for don\'t care. For " ", '
            "existing nodes are used if possible, and default_node_type is used to create new nodes. That is the "
            "default if ~ hasn't been explicitly specified for a key in path",
        ),
        path_split=FagusOption(
            "path_split", " ", str, lambda x: bool(x), 'path_split can\'t be "", as a string can\'t be split by "".'
        ),
    )
    """Default values for all options used in Fagus"""

    no_node: Tuple[type, ...] = (str, bytes, bytearray)  # if this is changed in class, change in __delattr__ as well
    """Every type of Collection in no_node will not be treated as a node, but as a single value"""

    _cls_options: Dict[str, FagusOption] = {}

    def options(
        cls, options: Optional[Dict[str, FagusOption]] = None, get_default_options: bool = False, reset: bool = False
    ) -> Dict[str, FagusOption]:
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
            return {k: cls._cls_options.get(k, v.default) for k, v in cls.__default_options__.items()}
        return {k: cls._cls_options[k] for k in cls.__default_options__ if k in cls._cls_options}

    def __setattr__(cls, attr: str, value: Any) -> None:
        if attr == "no_node":
            if not (isinstance(value, tuple) and all(isinstance(e, type) for e in value)):
                raise ValueError(
                    "no_node must be a tuple of types. These are not treated as nodes, default (str, bytes, bytearray)."
                )
            FagusMeta.no_node = value
        elif attr in cls.__default_options__:
            FagusMeta._cls_options[attr] = cls.__verify_option__(attr, value)
        elif attr in ("__abstractmethods__", "__annotations__", "__parameters__") or attr.startswith("_abc_"):
            super(FagusMeta, cls).__setattr__(attr, value)
        else:
            raise AttributeError(attr)

    def __getattr__(cls, attr: str) -> Any:
        if attr in cls._cls_options:
            return cls._cls_options[attr]
        elif attr in cls.__default_options__:
            return cls.__default_options__[attr].default
        return getattr(FagusMeta, attr)

    def __delattr__(cls, attr: str) -> None:
        if attr == "no_node":
            FagusMeta.no_node = (str, bytes, bytearray)
        elif attr in cls._cls_options:
            FagusMeta._cls_options.pop(attr)
        else:
            raise AttributeError(attr)


def _filter_r(node: Collection[Any], copy: bool, filter_: Optional["KFil"], index: int = 0) -> Collection[Any]:
    """Internal recursive method that facilitates filtering

    Args:
        node: the node to filter
        copy: creates copies instead of directly referencing nodes included in the filter
        filter_: TFilter-nodeect in which the filtering-criteria are specified
        index: index in the current filter-nodeect

    Returns:
        the filtered node
    """
    new_node: Collection[Any]
    action: Optional[str]
    match_key: Optional[Callable[[Any], Any]]
    if isinstance(node, c_abc.Mapping):
        new_node, action, match_key = {}, None, filter_.match if filter_ else None
    elif isinstance(node, c_abc.Sequence):
        new_node, action, match_key = [], "append", filter_.match_list if filter_ else None
    else:
        new_node, action, match_key = set(), "add", None
    for k, v in node.items() if isinstance(node, c_abc.Mapping) else enumerate(node):
        match_k: Tuple[bool, Optional[KFil], int] = (
            match_key(k, index, len(node)) if callable(match_key) else (True, filter_, index + 1)
        )
        if match_k[0]:
            if match_k[1] is None:
                match_v = True
            elif _is(v, c_abc.Collection):
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
                    new_node[k] = _copy_any(v) if copy else v  # type: ignore
    return new_node


def _copy_node(node: Collection[Any], recursive: bool = False) -> Collection[Any]:
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
        if isinstance(node, (c_abc.Mapping, c_abc.Sequence)):
            for k, v in node.items() if isinstance(node, c_abc.Mapping) else enumerate(node):
                collection = _is(v, c_abc.Collection)
                if collection or hasattr(v, "copy"):
                    new_node[k] = _copy_node(v) if collection else v.copy()
        elif isinstance(new_node, c_abc.MutableSet):  # must be a set or similar
            for v in node:
                collection = _is(v, c_abc.Collection)
                if collection or hasattr(v, "copy"):
                    new_node.remove(v)
                    new_node.add(_copy_node(v) if collection else v.copy())
    elif not any(_is(v, c_abc.Collection) or hasattr(v, "copy") for v in node):
        new_node = node
    elif isinstance(node, tuple):
        new_node = tuple(_copy_node(list(node), True))
    elif isinstance(node, frozenset):
        new_node = frozenset(_copy_node(set(node), True))
    else:
        new_node = cp.deepcopy(node)
    return cast(Collection[Any], new_node)


def _copy_any(value: Any, deep: bool = False) -> Any:
    """Creates a copy of value. If deep is set, a deep copy is returned, otherwise a shallow copy is returned"""
    if deep:
        return cp.deepcopy(value)
    elif _is(value, c_abc.Collection):
        return _copy_node(value)
    return cp.copy(value)


def _is(value: Any, *args: type, is_not: Optional[Union[Tuple[type], type]] = None) -> bool:
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
