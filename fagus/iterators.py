"""This module contains iterator-classes that are used to iterate over Fagus-objects"""
from typing import (
    TYPE_CHECKING,
    Union,
    Any,
    Optional,
    Callable,
    Iterator,
    cast,
    Collection,
    Iterable,
    Tuple,
)
import collections.abc as c_abc

from .utils import _filter_r, _None, INF, _copy_node, _copy_any, _is


__all__ = ("FilteredIterator", "FagusIterator")


if TYPE_CHECKING:
    from .filters import Fil, KFil
    from .fagus import Fagus


class FilteredIterator:
    """Iterator class that gives keys and values for any Collection (use optimal_iterator() to initialize it)"""

    @staticmethod
    def optimal_iterator(
        obj: Collection[Any],
        filter_value: bool = False,
        filter_: Optional["Fil"] = None,
        filter_index: int = 0,
    ) -> Iterator[Any]:
        """This method returns the simplest possible Iterator to loop through a given object.

        If no filter is present, either items or enumerate are called to loop through the keys, for sets ... is put
        as key for each value (as sets have no meaningful keys). If you additionally need filtering, this class is
        initialized to support iteration on only the keys and values that pass the filter"""
        if filter_ is None:
            if isinstance(obj, c_abc.Sequence):
                return iter(enumerate(obj))
            elif isinstance(obj, c_abc.Mapping):
                return iter(obj.items())
            else:
                return ((..., e) for e in obj)
        else:
            return FilteredIterator(obj, filter_value, filter_, filter_index)

    def __init__(self, obj: Collection[Any], filter_value: bool, filter_: "Fil", filter_index: int = 0) -> None:
        self.filter_ = filter_
        self.filter_index = filter_index
        self.filter_value = filter_value
        self.match_key: Callable[[Any, int, Any], Tuple[bool, Optional[KFil], int]]
        if isinstance(obj, c_abc.Mapping):
            self.match_key = self.filter_.match
        elif isinstance(obj, c_abc.Sequence):
            self.match_key = self.filter_.match_list
        else:
            self.match_key = lambda *_: (True, self.filter_, self.filter_index + 1)
        self.obj = obj
        self.iter = self.optimal_iterator(obj)

    def __iter__(self) -> "FilteredIterator":
        return self

    def __next__(self) -> Any:
        while True:
            k, v = next(self.iter)
            match_k, filter_, index = self.match_key(k, self.filter_index, len(self.obj))
            if not match_k:
                continue
            if filter_ is not None:
                if not filter_.match_extra_filters(v, index):
                    continue
            if _is(v, c_abc.Collection):  # filter v if it is a leaf, either because it is a set or because of the
                if self.filter_value if isinstance(v, (c_abc.Mapping, c_abc.Sequence)) else True:  # limiting max_items
                    v = _filter_r(v, False, filter_, index)
            elif filter_ and not filter_.match(v, index)[0]:
                continue
            return k, v, filter_, index


class FagusIterator:
    """Iterator-class for Fagus to facilitate the complex iteration with filtering etc. in the tree-object

    Internal - use Fagus.iter() to use this iterator on your object"""

    def __init__(
        self,
        obj: "Fagus",
        max_depth: int = INF,
        filter_: Optional["Fil"] = None,
        fagus: bool = False,
        iter_fill: Any = _None,
        select: Optional[Union[int, Iterable[Any]]] = None,
        iter_nodes: bool = False,
        copy: bool = False,
        filter_ends: bool = False,
    ) -> None:
        """Internal function. Recursively iterates through Fagus-object

        Initiate this iterator through Fagus.iter(), there the parameters are discussed as well."""
        self.obj = obj
        self.max_depth = INF if max_depth < 0 else max_depth
        self.fagus = fagus
        self.iter_fill = iter_fill
        self.filter_ends = filter_ends
        self.copy = copy
        if not (
            select is None
            or isinstance(select, int)
            or isinstance(select, c_abc.Iterable)
            and all(isinstance(e, int) for e in select)
        ):
            raise TypeError(
                "Invalid type %s for select parameter. Must be int or list of ints." % type(select).__name__
            )
        self.select = select
        self.iter_nodes = iter_nodes
        self.iter_keys = [obj if fagus else obj()]
        self.iterators = [FilteredIterator.optimal_iterator(obj(), filter_ends and not max_depth, filter_)]
        self.deepest_change = 0

    def __iter__(self) -> "FagusIterator":
        return self

    def __next__(self) -> Any:
        self.deepest_change = len(self.iterators) - 1
        while True:
            try:
                try:
                    k, v, *filter_ = next(self.iterators[-1])
                except IndexError:
                    raise StopIteration
                if len(self.iterators) - 1 < self.max_depth and v and _is(v, c_abc.Collection):
                    self.iter_keys.extend((k, self.obj.child(v) if self.fagus else v))
                    self.iterators.append(
                        FilteredIterator.optimal_iterator(
                            v,
                            self.filter_ends and len(self.iterators) - 2 < self.max_depth,
                            *filter_,
                        )
                    )
                else:
                    if self.fagus and _is(v, c_abc.Collection):
                        v = self.obj.child(v)
                    iter_list = (
                        *(self.iter_keys if self.iter_nodes else self.iter_keys[1::2]),
                        k,
                        _copy_any(v) if self.copy else v,
                        *(
                            (self.iter_fill,) * (self.max_depth - len(self.iterators) + 1)
                            if self.iter_fill is not _None and self.max_depth < INF
                            else ()
                        ),
                    )
                    if self.select is not None:
                        if isinstance(self.select, int):
                            return iter_list[self.select]
                        return tuple(iter_list[i] for i in self.select if -len(iter_list) <= i < len(iter_list))
                    return iter_list
            except StopIteration:
                try:
                    self.iterators.pop()
                    del self.iter_keys[-2:]
                    self.deepest_change = len(self.iterators) - 1
                except IndexError:
                    raise StopIteration

    def skip(self, level: int, copy: bool = False) -> Any:
        """Skip the remaining iterations of a node at a given level if you're done handling it

        Args:
            level (int): which node to skip. Level 0 is the root node, the next node is level 1 etc.
            copy (bool): Whether to skip a copy of the node. Can be useful when the tree is modified during iteration

        Returns:
            The node that was skipped
        """

        # """Skip the remaining iterations of a node at a given level if you're done handling it"""
        node = self.iter_keys[level * 2]
        if isinstance(self.iterators[-1], FilteredIterator):
            iterator = cast(FilteredIterator, self.iterators[level])
            node = _filter_r(
                node,
                copy,
                iterator.filter_,
                iterator.filter_index,
            )
        else:
            node = _copy_node(node)
        del self.iterators[level:]
        del self.iter_keys[level * 2 - 1 :]
        return node
