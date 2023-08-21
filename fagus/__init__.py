"""Library to easily create, edit and traverse nested objects of dicts and lists in Python

The following objects can be imported directly from this module:
    * :obj:`~fagus.Fagus`: a wrapper-class for complex, nested objects of dicts and lists
    * :obj:`~fagus.filters.Fil`, :obj:`~fagus.filters.CFil` and :obj:`~fagus.filters.VFil` are filter-objects that can
      be used to filter :obj:`~fagus.Fagus`-objects
    * :obj:`~fagus.utils.INF`: alias for :obj:`sys.maxsize`, used e.g. to indicate that an element should be appended to
      a list

Submodules in :py:mod:`fagus`:
    * :py:mod:`~fagus.fagus`: Base-module that contains the :obj:`~fagus.Fagus`-class
    * :py:mod:`~fagus.filters`: filter-classes for filtering :obj:`~fagus.Fagus`-objects
    * :py:mod:`~fagus.iterators`: iterator-classes for iterating on :obj:`~fagus.Fagus`
    * :py:mod:`~fagus.utils`: helper classes and methods for :obj:`~fagus.Fagus`
"""

__version__ = "1.1.2"

from .fagus import Fagus
from .filters import Fil, CFil, VFil
from .utils import INF

__all__ = ("Fagus", "Fil", "CFil", "VFil", "INF")
