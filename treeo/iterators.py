"""This module contains iterator-classes that are used to iterate over TreeO-objects"""
from collections.abc import Collection, Sequence, Mapping, Iterable
from typing import Union, TYPE_CHECKING

from treeo.utils import _is, END, _None, _filter_r, _copy_node, _copy_any

if TYPE_CHECKING:
    from treeo.filters import TFil
    from treeo.treeo import TreeO


class TFilteredIterator:
    """Iterator class that gives keys and values for any Collection (use optimal_iterator() to initialize it)"""

    @staticmethod
    def optimal_iterator(
        obj: Collection,
        filter_value: bool = False,
        filter_: "TFil" = None,
        filter_index: int = 0,
    ):
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
            return TFilteredIterator(obj, filter_value, filter_, filter_index)

    def __init__(
        self,
        obj: Collection,
        filter_value: bool,
        filter_: "TFil",
        filter_index: int = 0,
    ):
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
            if _is(v, Collection):  # filter v if it is a leaf, either because it is a set or because
                if self.filter_value if isinstance(v, (Mapping, Sequence)) else True:  # of the limiting max_items
                    v = _filter_r(v, False, filter_, index)
            elif filter_ and not filter_.match(v, index)[0]:
                continue
            return k, v, filter_, index


class TreeOIterator:
    """Iterator-class for TreeO to facilitate the complex iteration with filtering etc. in the tree-object

    Internal - use TreeO.iter() to use this iterator on your object"""

    def __init__(
        self,
        obj: "TreeO",
        max_depth: int = END,
        filter_: "TFil" = None,
        treeo: bool = False,
        iter_fill=_None,
        reduce: Union[int, Iterable] = None,
        iter_nodes: bool = False,
        copy: bool = False,
        filter_ends: bool = False,
    ):
        """Internal function. Recursively iterates through TreeO-object

        Initiate this iterator through TreeO.iter(), there the parameters are discussed as well."""
        self.obj = obj
        self.max_depth = END if max_depth < 0 else max_depth
        self.treeo = treeo
        self.iter_fill = iter_fill
        self.filter_ends = filter_ends
        self.copy = copy
        if not (
            reduce is None
            or isinstance(reduce, int)
            or isinstance(reduce, Iterable)
            and all(isinstance(e, int) for e in reduce)
        ):
            raise TypeError(
                "Invalid type %s for reduce parameter. Must be int or list of ints." % type(reduce).__name__
            )
        self.reduce = reduce
        self.iter_nodes = iter_nodes
        self.iter_keys = [obj if treeo else obj()]
        self.iterators = [TFilteredIterator.optimal_iterator(obj(), filter_ends and not max_depth, filter_)]
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
                if len(self.iterators) - 1 < self.max_depth and v and _is(v, Collection):
                    self.iter_keys.extend((k, self.obj.child(v) if self.treeo else v))
                    self.iterators.append(
                        TFilteredIterator.optimal_iterator(
                            v, self.filter_ends and len(self.iterators) - 2 < self.max_depth, *filter_
                        )
                    )
                else:
                    if self.treeo and _is(v, Collection):
                        v = self.obj.child(v)
                    iter_list = (
                        *(self.iter_keys if self.iter_nodes else self.iter_keys[1::2]),
                        k,
                        _copy_any(v) if self.copy else v,
                        *(
                            (self.iter_fill,) * (self.max_depth - len(self.iterators) + 1)
                            if self.iter_fill is not _None and self.max_depth < END
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
        if isinstance(self.iterators[-1], TFilteredIterator):
            node = _filter_r(
                node,
                copy,
                self.iterators[level].filter_,
                self.iterators[level].filter_index,
            )
        else:
            node = _copy_node(node)
        del self.iterators[level:]
        del self.iter_keys[level * 2 - 1 :]
        return node
