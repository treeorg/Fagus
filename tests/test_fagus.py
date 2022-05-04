import copy
import json
import os.path
import re
import unittest
from ipaddress import IPv6Address, IPv4Network, IPv6Network, ip_address
from fagus import __version__, Fagus, Func, Fil, FCFil, VFil
from datetime import datetime, date, time


def test_version():
    assert __version__ == "0.1.0"


class HashableDict(dict):
    def __hash__(self):
        return hash(frozenset(self.items()))


class TestFagus(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.a = None
        self.test_data_path = f"{os.path.dirname(__file__) or '.'}/test-data.json"

    def setUp(self) -> None:
        setattr(self, "a", {"1": [[1, True, "a", ("f", {"a", "q"})], {"a": False, "1": (1,)}], "a": [[3, 4], {"b": 1}]})

    def test_get(self):
        a = Fagus(self.a)
        Fagus.default = 7
        self.assertEqual(7, a["1 2 3"], "Returning default-value for class when unset for object")
        a.default = 3
        self.assertEqual(3, a["1 2 3"], "Returning default-value for object as it is now set")
        self.assertEqual(1, Fagus.get(self.a, ("1", 0, 0)), "Path existing, return value at path")
        self.assertEqual(1, a["1 0 0"], "Path existing, return value at path")
        self.assertIn("q", Fagus.get(self.a, ("1", 0, 3, 1)), "Path existing, return value at path")
        self.assertEqual(1, Fagus(self.a).get((1, 0, 0), 1), "Path not existing return default that comes from param")
        self.assertEqual(1, Fagus.get((((1, 0), 2), 3), "0 0 0"), "Successfully traversing tuples")
        self.assertEqual([[3, 4], {"b": 1}], a.a, "Using dot-notation to get value from Fagus")
        a.value_split = "_"
        self.assertEqual(1, a.a_1_b, "Using dot-notation with value_split as _ to get value from Fagus")
        a.c_e = {"a_haa_k": 72}
        a.value_split = "__"
        self.assertEqual(72, a.c__e__a_haa_k, "Using dot-notation with __ as value_split to get keys with _ inside")
        del Fagus.default

    def test_iter(self):
        a = Fagus(self.a, copy=True)
        aq = tuple(a["1 0 3 1"])  # have to create this tuple of the set because it's unpredictable what order
        # a and q will have in the set. Using this tuple, I make sure the test still works (the order will be sth same)
        b = [
            ("1", 0, 0, 1),
            ("1", 0, 1, True),
            ("1", 0, 2, "a"),
            ("1", 0, 3, 0, "f"),
            ("1", 0, 3, 1, ..., aq[0]),
            ("1", 0, 3, 1, ..., aq[1]),
            ("1", 1, "a", False),
            ("1", 1, "1", 0, 1),
            ("a", 0, 0, 3),
            ("a", 0, 1, 4),
            ("a", 1, "b", 1),
        ]
        self.assertEqual(b, [x for x in a.iter()], "Correctly iterating over dicts and lists")
        self.assertEqual(
            [(0, 0, 3), (0, 1, 4), (1, "b", 1)], list(a.iter(-1, "a")), "Correct iterator when path is given"
        )
        for i, l in enumerate(b):
            b[i] = (*l, *((None,) * (7 - len(l))))
        self.assertEqual(
            b, list(a.iter(5, iter_fill=None)), "Correctly filling up when intended traversal depth is constant, here 5"
        )
        b = [
            ("1", 0, [1, True, "a", ("f", {"q", "a"})]),
            ("1", 1, {"a": False, "1": (1,)}),
            ("a", 0, [3, 4]),
            ("a", 1, {"b": 1}),
        ]
        self.assertEqual(b, list(a.iter(1)), "Iterating correctly when max_depth is limited to one")
        b = [
            ("1", 0, 0, 1),
            ("1", 0, 1, True),
            ("1", 0, 2, "a"),
            ("1", 0, 3, 0, "f"),
            ("1", 0, 3, 1, {"q", "a"}),
            ("1", 1, "a", False),
            ("1", 1, "1", 0, 1),
            ("a", 0, 0, 3),
            ("a", 0, 1, 4),
            ("a", 1, "b", 1),
        ]
        self.assertEqual(
            b, list(a.iter(3)), "Iterating correctly when max_items is limited to five. Some tuples are < 5"
        )
        self.assertEqual([(0, [3, 4]), (1, {"b": 1})], list(a.items("a")), "Items gives keys and values")
        b = [
            ("1", 0, Fagus([1, True, "a", ("f", {"q", "a"})])),
            ("1", 1, Fagus({"a": False, "1": (1,)})),
            ("a", 0, Fagus([3, 4])),
            ("a", 1, Fagus({"b": 1})),
        ]
        self.assertEqual(b, list(a.iter(1, fagus=True)), "Returning nodes as Fagus-objects when return_value=True")
        self.assertTrue(
            all(isinstance(e, Fagus) for e in a.iter(1, fagus=True, select=-1)),
            "fagus actually returns back nodes if the nodes at the end are suitable to be converted",
        )
        self.assertEqual(
            tuple(a.iter(4, "", filter_=Fil("a", 1, lambda x: x % 2 != 0, inexclude="---"))),
            tuple(a.iter(4, "", filter_=Fil("1", 0, lambda x: x % 2 == 0))),
            "Two opposite filters giving the same results on the data",
        )
        self.assertEqual(
            ["a"],
            list(a.iter(path=("1", 0, 3), filter_=Fil(1, ..., "q", inexclude="++-"), select=-1)),
            "Correctly filtering a set in the end",
        )
        self.assertEqual(
            [(3, [{"a"}])],
            list(a.iter(0, ("1", 0), Fil(3, 1, ..., "q", inexclude="+++-"), filter_ends=True)),
            "Correctly putting a filtered last node in the end when combining filter_ and max-depth",
        )
        self.assertEqual(
            [
                (Fagus([[3, 4], {"b": 1}]), 0, Fagus([3, 4]), 0, 3),
                (Fagus([[3, 4], {"b": 1}]), 0, Fagus([3, 4]), 1, 4),
                (Fagus([[3, 4], {"b": 1}]), 1, Fagus({"b": 1}), "b", 1),
            ],
            list(a.iter(path="a", fagus=True, iter_nodes=True)),
            "Using iter_nodes to get references to all the nodes that have been traversed on the way",
        )
        self.assertEqual(
            {"1": [{"a": False, "1": (1,)}], "a": [{"b": 1}]},
            a.iter(filter_=Fil(..., 1)).skip(0),
            "Using iterator.skip() actually filters the skipped node if necessary",
        )
        with open(self.test_data_path) as fp:
            a = Fagus(json.load(fp))
        self.assertEqual(
            [(0, "source", "id", 889), (1, "source", "id", 5662), (4, "source", "id", 301)],
            list(a.iter(-1, "data", Fil(..., "source", "id", lambda x: x > 300))),
            "Iterating over all source-ids that are > 300, testing lambda and true and default",
        )
        self.assertEqual(
            (2, 1, 3),
            tuple(
                a.iter(
                    -1,
                    "data",
                    Fil(
                        ...,
                        (FCFil("source", "id", lambda x: x > 300), "state"),
                    ),
                    select=-1,
                )
            ),
            "Getting the states for all sources who's id is > 300 using reduce and a check-filter",
        )
        self.assertEqual(
            [],
            list(a.iter(path="data", filter_=Fil((VFil(lambda x: len(x) < 1), ...)))),
            "Verifying that a value-filter actually returns an empty list if its condition isn't met",
        )
        self.assertEqual(
            160,
            len(list(a.iter(path="data", filter_=Fil((VFil(lambda x: len(x) == 10), ...))))),
            "Verifying that a value-filter actually returns the node if it's condition is met",
        )
        self.assertEqual(
            160,
            len(list(a.iter(filter_=Fil("data", VFil(lambda x: len(x) > 1))))),
            "Verifying that a value-filter also works if it comes as a standalone argument, then including all the "
            "subnodes the filter matches (in this case all).",
        )
        self.assertEqual(
            [],
            list(a.iter(filter_=Fil("data", (VFil(lambda x: len(x) < 1),)))),
            "A value-filter actually returns an empty list even at the bottom if its condition isn't met",
        )
        self.assertEqual(
            160,
            len(list(a.iter(path="data", filter_=Fil((VFil(lambda x: len(x) > 1),))))),
            "If the only member in a tuple is TValue- and TCheck-filters and they're all removed, put ... at that"
            "argument to make sure these check-filters can match anything",
        )
        self.assertEqual(
            [(0, "role", "id", 182), (0, "role", "name", "Intel from sandbox runs"), (0, "state", 2)],
            list(
                a.iter(
                    path="data",
                    filter_=Fil(
                        ...,
                        (
                            FCFil(
                                (
                                    VFil(lambda x: len(x) == 3, lambda x: bool(x)),
                                    FCFil("alias", "file-analyzer-domain"),
                                    "source",
                                ),
                                "id",
                                889,
                            ),
                            Fil("state", 1, inexclude="+-"),
                            "role",
                        ),
                        "alias",
                        inexclude="++-",
                    ),
                )
            ),
            "Combining tons of filters to additionally verify and filter the result",
        )
        c = (
            ("responseCode", 200),
            ("limit", 10000),
            ("data", 0, "sourceId", 889),
            ("data", 6, "source", "alias", "et_iqrisk_blackhole-c3"),
            ("data", 1, "role", "alias", "malware-server"),
            ("data", 4, "roleId", 33),
        )
        b = tuple(
            a.iter(filter_=Fil("responseCode|limit|data", ..., ("role.*", re.compile("source.*")), str_as_re=True))
        )
        self.assertTrue(all(e in b for e in c), "Checking if it works to convert str to regex when requested")
        filter_args = ["a|c", ("abc", "a.*")]
        self.assertEqual(filter_args, Fil(*filter_args).args, "No str args are changed if string_as_re=False")
        self.assertEqual(
            [re.compile(filter_args[0]), [filter_args[1][0], re.compile(filter_args[1][1])]],
            Fil(*filter_args, str_as_re=True).args,
            "The correct str's are replaced with re-patterns if string_as_re=False",
        )
        b = {
            (..., ..., 0, 8),
            (..., ..., 1, 7),
            (..., ..., ..., 5),
            (..., ..., ..., 6),
            (..., 0, "a"),
            (..., 1, "q"),
            (..., ..., 0, 5),
            (..., ..., 1, "h", "M"),
            (..., ..., 0, "l"),
            (..., ..., 1, "q"),
        }
        f = {("a", "q"), frozenset(((5, HashableDict({"h": "M"})), ("l", "q"))), frozenset((frozenset((5, 6)), (8, 7)))}
        self.assertEqual(b, set(Fagus.iter(f)), "Iterating through sets, some sets stacked in sets")
        self.assertEqual(
            [("responseCode", 200), ("limit", 10000), ("offset", 0), ("data", 4, {"state": 3, "comment": None})],
            list(
                a.iter(
                    1,
                    filter_=Fil(({"responseCode", "limit", "offset"}, Fil("data", 4, {"comment", "state"}))),
                    filter_ends=True,
                )
            ),
            "Using sets to accelerate filtering, both as a standalone argument and with other args in a tuple",
        )

    def test_filter(self):
        self.assertEqual(
            {"1": [{"a": False, "1": (1,)}], "a": [{"b": 1}]},
            Fagus.filter(self.a, filter_=Fil(..., lambda x: x % 2), copy=True),
            "Filtering using a lambda on the default test-datastructure",
        )
        self.assertEqual(
            {"1": [[1, True, "a", ("f", {"q", "a"})]], "a": [[3, 4]]},
            Fagus.filter(self.a, filter_=Fil(..., lambda x: x % 2, inexclude="--"), copy=True),
            "Filtering using a lambda on the default test-datastructure",
        )
        with open(self.test_data_path) as fp:
            a = Fagus(json.load(fp))
        self.assertEqual(
            {"responseCode": 200, "limit": 10000, "size": 10000},
            a.filter(Fil({"responseCode", "limit", "size"}), copy=True),
            "Simplest ever filtering at base-level",
        )
        self.assertEqual(
            dict(responseCode=200, limit=10000, messages=[], metaData={}, offset=0, count=0, size=10000),
            a.filter(Fil("data", inexclude="-"), copy=True),
            "Using inexclude to turn around the filter and give everything except data at base-level",
        )
        self.assertEqual(
            [
                {"sourceId": 889, "roleId": 182, "firstSeen": 1548169200000, "lastSeen": 1561951800000},
                {"sourceId": 5662, "roleId": 33, "firstSeen": 1548169200000, "lastSeen": 1552989600000},
            ],
            a.filter(
                Fil(..., (FCFil("state", 3, invert=True), ".*(Seen|Id)"), str_as_re=True),
                "data",
                copy=True,
            ),
            "Testing invert on a TCheckFilter, getting all the nodes that have a state unlike 3",
        )
        b = Fagus(a, copy=True)
        b.filter(
            path="data",
            filter_=Fil(
                ...,
                (
                    FCFil(
                        (
                            VFil(lambda x: len(x) == 3, lambda x: bool(x)),
                            FCFil("alias", "file-analyzer-domain"),
                            "source",
                        ),
                        "id",
                        889,
                    ),
                    Fil("state", 1, inexclude="+-"),
                    "role",
                ),
                "alias",
                inexclude="++-",
            ),
        ),
        self.assertEqual(
            Fagus(
                {
                    "responseCode": 200,
                    "limit": 10000,
                    "offset": 0,
                    "count": 0,
                    "metaData": {},
                    "messages": [],
                    "data": [{"role": {"id": 182, "name": "Intel from sandbox runs"}, "state": 2}],
                    "size": 10000,
                }
            ),
            b,
            "A lot of check- and ordinary filters stacked into each other. Filtering at path, comparing the whole obj",
        )
        self.assertEqual(
            [],
            a.filter(path="data", filter_=Fil((VFil(lambda x: len(x) < 1), ...)), copy=True),
            "Verifying that a value-filter actually returns an empty list if its condition isn't met",
        )
        self.assertEqual(
            a["data"],
            a.filter(path="data", filter_=Fil((VFil(lambda x: len(x) == 10), ...)), copy=True),
            "Verifying that a value-filter actually returns the whole node if its condition is met",
        )
        self.assertEqual(
            {"data": a["data"]},
            a.filter(filter_=Fil("data", VFil(lambda x: len(x) > 1)), copy=True),
            "Verifying that a value-filter also works if it comes as a standalone argument, then including all the "
            "subnodes the filter matches (in this case all).",
        )
        self.assertEqual(
            {"data": a["data"]},
            a.filter(filter_=Fil("data", VFil(lambda x: len(x) < 10, invert=True)), copy=True),
            "Verifying that a value-filter also works if it comes as a standalone argument, then including all the "
            "subnodes the filter matches (in this case all).",
        )

    def test_split(self):
        split_res = (
            {"1": [{"a": False, "1": (1,)}], "a": [{"b": 1}]},
            {"1": [[1, True, "a", ("f", {"a", "q"})]], "a": [[3, 4]]},
        )
        self.assertEqual(
            (
                {"1": [{"a": False, "1": (1,)}], "a": [{"b": 1}]},
                {"1": [[1, True, "a", ("f", {"a", "q"})]], "a": [[3, 4]]},
            ),
            Fagus.split(self.a, Fil(..., lambda x: x % 2), copy=True),
            "Splitting using a lambda on the default test-datastructure",
        )
        self.assertEqual(
            (
                Fagus.filter(self.a, Fil(..., lambda x: x % 2), copy=True),
                Fagus.filter(self.a, Fil(..., lambda x: not x % 2), copy=True),
            ),
            Fagus.split(self.a, Fil(..., lambda x: x % 2), copy=True),
            "Splitting gives the same result as applying the filter two times, opposite ways on copies",
        )
        self.assertEqual(
            split_res[::-1],
            Fagus.split(self.a, Fil(..., lambda x: x % 2, inexclude="--"), copy=True),
            "Splitting using a lambda on the default test-datastructure, and with inexclude",
        )
        q = {"a": "b", "f": {"g", "q", "d"}, "g": {1: 3, 2: 4}}
        self.assertEqual(
            q,
            Fagus.merge(*Fagus.split(q, Fil(lambda x: ord(x) % 2, "g", inexclude="----"), copy=True)),
            "Splitting and remerging dicts and sets works as if they were never separated",
        )
        with open(self.test_data_path) as fp:
            a = Fagus(json.load(fp))
        in_, out = a.split(Fil(..., FCFil("state", 3)), path="data", copy=True, fagus=True)
        self.assertIsInstance(in_, Fagus, "fagus is on, so in_ must be a Fagus")
        self.assertIsInstance(out, Fagus, "fagus is on, so out must be a Fagus")
        self.assertEqual({3}, set(in_.iter(filter_=Fil(..., "state"), select=-1)), "all items in in_ match the filter")
        self.assertNotEqual({3}, set(out.iter(filter_=Fil(..., "state"), select=-1)), "no items in out match filter")
        self.assertEqual((662, 762), tuple(out.iter(filter_=Fil(..., "id"), select=-1)), "correct ids in out")
        self.assertEqual(len(a["data"]), len(in_) + len(out), "All elements are either in in our out")
        in_, out = a.split(Fil(), path="data", copy=True)
        self.assertEqual(a["data"], in_, "If the filter matches everything, in_ must be equal to the original node")
        self.assertEqual([], out, "If the filter matches everything, out must be an empty list")
        in_, out = a.split(Fil("a"), copy=True)
        self.assertEqual({}, in_, "If the filter matches nothing, in_ must be an empty list")
        self.assertEqual(a(), out, "If the filter matches nothing, in_ must be equal to the original node")
        self.assertEqual(
            ("a", "a"), a.split(Fil(), "a", default="a"), "Default is returned for in_ and out if path doesn't exist"
        )

    def test_set(self):
        a = Fagus(self.a, copy=True)
        b = copy.deepcopy(self.a)
        b["1"][0][1] = False
        self.assertEqual(
            b,
            Fagus.set(a, False, "1 0 1"),
            "Correctly traversing dicts and lists with numeric indices when the node type is not given explicitly.",
        )
        # verify that base object is writable for set
        self.assertRaisesRegex(
            TypeError,
            "Can't modify base-object self having the immutable type",
            Fagus.set,
            (((1, 0), 2), 3),
            7,
            "0 0 0",
        )
        # new nodes can only either be lists or dicts, expressed by l's and
        self.assertRaisesRegex(ValueError, "The only allowed characters in ", Fagus.set, a["1"], "f", "0", "pld")
        # Due to limitations on how references work in Python, the base-object can't be changed. So if the base-object
        # is a list, it can't be converted into a dict. This kind of changes are possible at the lower levels.
        self.assertRaisesRegex(TypeError, "Your base object is a (.*|see comment)", Fagus.set, a, "f", "0", "lld")
        # if the user defines that he wants a list, but it's not possible to parse numeric index from t_path raise error
        self.assertRaisesRegex(ValueError, "Can't parse numeric list-index from", Fagus.set, a, "f", "1 f", "dl")
        a[("1", 1)] = "hei"
        b["1"][1] = "hei"
        self.assertEqual(b, a(), "Using __set_item__ to set a value")
        a.value_split = "_"
        a.a_1_b = 2
        b["a"][1]["b"] = 2
        self.assertEqual(a(), b, "Using another path separator and __setattr__")
        b["1"] = {"0": {"0": {"g": [9, 5]}}}
        self.assertEqual(b, a.set({"g": [9, 5]}, "1øæ0øæ0", "ddd", value_split="øæ"), "Replace list with dict")
        self.assertEqual([[["a"]]], Fagus.set([], "a", "1 1 1", default_node_type="l"), "Only create lists")
        a = Fagus(self.a, copy=True)
        b = copy.deepcopy(a())
        b["1"][0].insert(2, [["q"]])
        a.set("q", ("1", 0, 2, 0, 0), list_insert=2, default_node_type="l")
        self.assertEqual(a(), b, "Insert into list")
        b["1"][0].append("hans")
        b["1"].insert(0, ["wurst"])
        a.default_node_type = "l"
        a.set("hans", "1 0 100")
        a.set("wurst", "1 -40 5")
        self.assertEqual(a(), b, "Add to list at beginning / end by using indexes higher than len / lower than - len")
        a = Fagus((((1, 0), 2), (3, 4, (5, (6, 7)), 8)))
        self.assertRaisesRegex(TypeError, "Can't modify base-object self having the immutable typ", a.set, 5, "1 2 1 1")
        a = Fagus(list(a))
        self.assertEqual([((1, 0), 2), [3, 4, [5, [6, 5]], 8]], a.set(5, "1 2 1 1"), "Converting right tuples to lists")
        a = Fagus((((1, 0), 2), [3, 4, (5, (6, 7)), 8]))
        a["1 2 1 1"] = 5
        self.assertEqual((((1, 0), 2), [3, 4, [5, [6, 5]], 8]), a(), "Keeping tuples below if possible, testing []")
        a = Fagus(self.a, copy=True)
        self.assertNotEqual(a(), a.set(False, "1 1", copy=True), "The source object is not modified when copy is used")
        self.assertEqual(
            {"1": [{"b": [False]}, {"a": False, "1": (1,)}], "a": [[3, 4], {"b": 1}]},
            a.set(False, "1 0 b 1", node_types="   l", copy=True),
            "space does not enforce node_types in path - dicts and lists are traversed as long as the keys allow it",
        )
        self.assertEqual(self.a, Fagus.set(a, "", "a", if_=bool), "If the condition is not met, a isn't modified")
        self.assertEqual({"5": 9, "c": (1, 2)}, Fagus.set({"5": 9}, (1, 2), "c", if_=bool), "if_ with bool")
        self.assertEqual({"5": 9, "c": (1, 2)}, Fagus.set({"5": 9}, (1, 2), "c", if_=((1, 2),)), "if_ iterable value")
        self.assertEqual({"5": 9, "c": 27}, Fagus.set({"5": 9}, 27, "c", if_=range(29)), "if_ with range")
        self.assertEqual(self.a, Fagus.set(a, 27, "c", if_=range(3)), "if_ with range")

    def test_append(self):
        a = copy.deepcopy(self.a)
        b = copy.deepcopy(self.a)
        b["a"][0].append(5)
        self.assertEqual(Fagus.append(a, 5, "a 0"), b, "appending to existing list")
        b["1"][0][3] = list(b["1"][0][3])
        b["1"][0][3][1] = list(b["1"][0][3][1])
        b["1"][0][3][1].append("f")
        b["1"][0][3][1].sort()
        Fagus.append(a, "f", "1 0 3 1")
        Fagus.get(a, "1 0 3 1").sort()
        self.assertEqual(
            a, b, "appending to set (converting to list first, both sets must be sorted for the test not to fail)"
        )
        b["1"][0][0] = [1, 5]
        self.assertEqual(Fagus.append(a, 5, "1 0 0"), b, "Creating list from singleton value and appending to it")
        b["q"] = [6]
        self.assertEqual(Fagus.append(a, 6, "q"), b, "Create new list for value at a path that didn't exist before")

    def test_extend(self):
        a = copy.deepcopy(self.a)
        b = copy.deepcopy(self.a)
        b["a"][0].extend((5, 6))
        self.assertEqual(Fagus.extend(a, (5, 6), "a 0"), b, "appending to existing list")
        b["1"][0][3] = list(b["1"][0][3])
        b["1"][0][3][1] = list(b["1"][0][3][1])
        b["1"][0][3][1].extend("fg")
        b["1"][0][3][1].sort()
        Fagus.extend(a, "fg", "1 0 3 1")
        Fagus.get(a, "1 0 3 1").sort()
        self.assertEqual(
            a, b, "extending set (converting to list first, both sets must be sorted for the test not to fail)"
        )
        b["1"][0][0] = [1, 5, 6]
        self.assertEqual(Fagus.extend(a, [5, 6], "1 0 0"), b, "Creating list from singleton value and appending to it")
        b["q"] = [6, 7]
        self.assertEqual(Fagus.extend(a, [6, 7], "q"), b, "Create new list for value at a path not existing before")
        self.assertRaisesRegex(TypeError, "Can't extend value in base-dict", Fagus().extend, [3, 4])

    def test_insert(self):
        a = copy.deepcopy(self.a)
        b = copy.deepcopy(self.a)
        b["a"][0].insert(2, "hei")
        self.assertEqual(Fagus.insert(a, 2, "hei", "a 0"), b, "appending to existing list")
        b["1"][0][3] = list(b["1"][0][3])
        b["1"][0][3][1] = list(b["1"][0][3][1])
        b["1"][0][3][1].insert(5, "fg")
        b["1"][0][3][1].sort()
        Fagus.insert(a, 5, "fg", "1 0 3 1")
        Fagus.get(a, "1 0 3 1").sort()
        self.assertEqual(
            a, b, "extending set (converting to list first, both sets must be sorted for the test not to fail)"
        )
        b["1"][0][0] = [5, 1]
        self.assertEqual(Fagus.insert(a, -3, 5, "1 0 0"), b, "Creating list from singleton value and appending to it")
        b["q"] = [5]
        self.assertEqual(Fagus.insert(a, -9, 5, "q"), b, "Create new list for value at a path that didn't exist before")
        Fagus.insert(a, 2, 4, "1"),
        Fagus.set(b, 4, "1 2", list_insert=1),
        self.assertEqual(
            a, b, "Inserting into the list at level 1 does the same as setting with list_insert at the right level"
        )

    def test_add(self):
        a = Fagus(self.a, copy=True)
        b = copy.deepcopy(self.a)
        b["1"][0][3] = list(b["1"][0][3])
        b["1"][0][3][0] = {"f", "q"}
        a.add("q", "1 0 3 0")
        self.assertEqual(a(), b, "Converting single value to set, adding value to it")
        b["1"][0][3][1].add("hans")
        a.add("hans", "1 0 3 1")
        self.assertEqual(a(), b, "Adding value to existing set")
        b["a"][1]["c"] = {5}
        a.add(5, "a 1 c")
        self.assertEqual(a(), b, "Creating new empty set at position where no value has been before")
        self.assertEqual({5, 6}, Fagus({5}).add(6), "Adding to set that is the base-object")

    def test_update(self):
        # update set
        a = Fagus(self.a, copy=True)
        b = copy.deepcopy(self.a)
        b["1"][0][3] = list(b["1"][0][3])
        b["1"][0][3][0] = {"f", "q", "t", "p"}
        a.update("qtp", "1 0 3 0")
        self.assertEqual(a(), b, "Converting single value to set, adding new values to it")
        b["1"][0][3][1].update("hans")
        a.update("hans", "1 0 3 1")
        self.assertEqual(a(), b, "Adding new values to existing set")
        b["a"][1]["c"] = {5}
        a.add(5, "a 1 c")
        self.assertEqual(a(), b, "Creating new empty set at position where no value has been before")
        # update dict
        b.update({"hei": 1, "du": "wurst"})
        a.update({"hei": 1, "du": "wurst"})
        self.assertEqual(a(), b, "Updating base dict")
        b["a"][1].update({"hei": 1, "du": "wurst"})
        a.update({"hei": 1, "du": "wurst"}, "a 1")
        self.assertEqual(a(), b, "Updating dict further inside the object")
        b["k"] = {"a": 1}
        a.update({"a": 1}, "k")
        self.assertEqual(a(), b, "Updating dict at node that is not existing yet")
        self.assertRaisesRegex(ValueError, "Can't update dict with value of type ", a.update, {"hans", "wu"}, "a 1")

    def test_setdefault(self):
        a = Fagus(self.a, copy=True)
        b = copy.deepcopy(self.a)
        self.assertEqual(a.setdefault("a 0 0", 5), 3, "Setdefault returns existing value")
        self.assertEqual(a(), b, "SetDefault doesn't change if the value is already there")
        self.assertEqual(a.setdefault("a 7 7", 5, node_types="dll"), 5, "SetDefault returns default value")
        b["a"].append([5])
        self.assertEqual(a(), b, "SetDefault has added the value to the list")

    def test_mod(self):
        a = Fagus(self.a, copy=True)
        b = copy.deepcopy(self.a)
        b["1"][0][0] += 4
        a.mod(lambda x: x + 4, "1 0 0", 6)
        self.assertEqual(b, a(), "Modifying existing number")
        b["1"][0].insert(0, 2)
        a.mod(lambda x: x + 4, "1 0 0", 2, list_insert=2)
        self.assertEqual(b, a(), "Setting default value where it doesn't exist due to list_insert at the last list")
        b["1"].insert(0, [2])
        a.mod(lambda x: x + 4, "1 0 0", 2, list_insert=1, default_node_type="l")
        self.assertEqual(b, a(), "Setting default value where it doesn't exist due to list_insert at an earlier list")

        def fancy_mod1(old_value):
            return old_value * 2

        b["1"][0][0] = fancy_mod1(b["1"][0][0])
        a.mod(fancy_mod1, "1 0 0")
        self.assertEqual(b, a(), "Using function pointer that works like a lambda - one param, one arg")
        b["1"][0][0] = fancy_mod1(b["1"][0][0])
        a.mod(fancy_mod1, "1 0 0")
        self.assertEqual(b, a(), "Mod can be a function pointer (and not a lambda) as well")

        def fancy_mod2(old_value, arg1, arg2, arg3, **kwargs):
            return sum([old_value, arg1, arg2, arg3, *kwargs.values()])

        b["1"][0][0] += 1 + 2 + 3 + 4 + 5
        a.mod(Func(fancy_mod2, 1, 1, 2, 3, kwarg1=4, kwarg2=5), "1 0 0")
        self.assertEqual(b, a(), "Complex function taking keyword-arguments and ordinary arguments")

    def test_mod_all(self):
        with open(self.test_data_path) as fp:
            a = Fagus(json.load(fp))
        date_filter = Fil(..., {"firstSeen", "lastSeen", "lastModified"})
        b = Fagus.mod_all(a, lambda x: datetime.fromtimestamp(x / 1000), date_filter, "data", copy=True)
        self.assertTrue(
            all(isinstance(e[-1], datetime) for e in Fagus.iter(b, filter_=date_filter))
            and Fagus.get(b, "0 lastSeen") == datetime(2019, 7, 1, 5, 30)
            and isinstance(Fagus.get(a, "data 0 lastSeen"), int),
            "Made all dates in test-data human readable (converted from timestamp) while not touching original",
        )
        Fagus.mod_all(a, lambda x: x.pop("lastModified"), path="data", replace_value=False, max_depth=0)
        self.assertTrue(all("lastModified" not in e for e in a["data"]), "Modifying nodes without replacing them")
        a = [([(0, 0), 0], ([0, (0, 0, frozenset((0,))), (((0,),),)],))]
        self.assertEqual(
            [([[1, 1], 1], ([1, [1, 1, {1}], [[[1]]]],))],
            Fagus.mod_all(a, lambda x: x + 1, copy=True),
            "Only necessary modifications when nodes are transformed from immodifyable to modifyable. Also testing set",
        )

    def test_serialize(self):
        test_obj = {date(2021, 3, 6): [time(6, 45, 22), datetime(2021, 6, 23, 5, 45, 22)], ("hei", "du"): {3, 4, 5}}
        a = Fagus(test_obj, copy=True)
        self.assertRaisesRegex(
            TypeError,
            "Can't modify base-object self having the immutable type",
            Fagus((1, 2, 3, [4, 5, 6], {6, 5})).serialize,
        )
        self.assertRaisesRegex(
            ValueError, "Dicts with composite keys \\(tuples\\) are not supported in", a.serialize, copy=True
        )
        b = {"2021-03-06": ["06:45:22", "2021-06-23 05:45:22"], "hei du": [3, 4, 5]}
        self.assertEqual(a.serialize({"tuple_keys": lambda x: " ".join(x)}), b, "Serialized datetime and tuple-key")
        self.assertEqual(a.serialize(), b, "Nothing changes if there is nothing to change")
        a = Fagus(test_obj, copy=True)
        a[("hei du",)] = a.pop((("hei", "du"),))
        self.assertEqual(a.serialize(), b, "Also works when no mod-functions are defined in the parameter")
        a = Fagus(Fagus(self.a, copy=True).serialize())
        a["1 0 3 1"].sort()
        self.assertEqual(
            {"1": [[1, True, "a", ["f", ["a", "q"]]], {"a": False, "1": [1]}], "a": [[3, 4], {"b": 1}]},
            a(),
            "Removing tuples / sets in complex dict / list tree",
        )
        a = Fagus(default_node_type="l")
        a["a 1"] = ip_address("::1")
        a.append(ip_address("127.0.0.1"), "a 0")
        a["a -8"] = IPv4Network("192.168.178.0/24")
        a["a 6"] = IPv6Network("2001:0db8:85a3::/80")
        self.assertEqual(
            {
                "a": [
                    "IPv4Network('192.168.178.0/24')",
                    ["IPv6Address('::1')", "IPv4Address('127.0.0.1')"],
                    "IPv6Network('2001:db8:85a3::/80')",
                ]
            },
            a.serialize(copy=True),
            "Only using default function with str on IP-objects",
        )

        def fancy_network_mask(network, format_string: str, **kwargs):
            if type(network) == IPv4Network:
                return (
                    format_string % (network, network.netmask)
                    + kwargs.get("broadcast", " and the bc-address ")
                    + str(network.broadcast_address)
                )
            return format_string % (network, network.netmask)

        self.assertEqual(
            {
                "a": [
                    "The network 192.168.178.0/24 with the netmask 255.255.255.0 and the broadcast-address "
                    "192.168.178.255",
                    ["::1 0000:0000:0000:0000:0000:0000:0000:0001", "local"],
                    "The network 2001:db8:85a3::/80 with the netmask ffff:ffff:ffff:ffff:ffff::",
                ]
            },
            a.serialize(
                {
                    IPv6Address: lambda x: f"{x.compressed} {x.exploded}",
                    "default": lambda x: "global" if x.is_global else "local",
                    (IPv4Network, IPv6Network): Func(
                        fancy_network_mask,
                        1,
                        "The network %s with the netmask %s",
                        broadcast=" and the broadcast-address ",
                    ),
                },
                copy=True,
            ),
            "Complex mod-functions with function pointer, args, kwargs, lambdas and tuple-types, overriding default",
        )

    def test_merge(self):
        b = {"a": {"b": {"c": 5}}, "d": "e"}
        c = {"a": {"b": {"k": 1, "l": 2, "m": 3}, "t": 5}, "u": {"v": {"w": "x"}}, "d": 4}
        bc = b.copy()
        self.assertTrue(
            b == Fagus.merge(bc, bc.copy(), "d q") and {"a": {"b": {"c": 5}}, "d": {"q": b}} == bc,
            "The path exists that is supposed to be merged, but it is not a node. Returning obj, original obj modified",
        )
        bc = b.copy()
        self.assertTrue(
            b == Fagus.merge(bc, bc.copy(), "c d") and {"a": {"b": {"c": 5}}, "d": "e", "c": {"d": b}} == bc,
            "The path that is supposed to be merged, does not exist. Create path and return obj, original obj modified",
        )
        bc = b.copy()
        self.assertTrue(
            b == Fagus.merge(bc, bc.copy(), "c d", copy=True) and b == bc,
            "Using copy the original object is not modified, obj is just returned and that's it",
        )
        self.assertEqual(
            {"a": {"b": {"c": 5, "k": 1, "l": 2, "m": 3}, "t": 5}, "d": 4, "u": {"v": {"w": "x"}}},
            Fagus.merge(b, c, copy=True),
            "Merging only dicts in default settings, where a value that exists in both places is replaced",
        )
        self.assertEqual(
            {"a": {"b": {"c": 5, "k": 1, "l": 2, "m": 3}, "t": 5}, "d": "e", "u": {"v": {"w": "x"}}},
            Fagus.merge(b, c, copy=True, new_value_action="i"),
            "Merging only dicts in default settings, where a value that exists in both objs is kept as it was",
        )
        self.assertEqual(
            {"a": {"b": {"c": [5, 5], "k": 1, "l": 2, "m": 3}, "t": 5}, "d": ["e", 4, "e"], "u": {"v": {"w": "x"}}},
            Fagus.merge(Fagus.merge(b, c, copy=True, new_value_action="a"), b, copy=True, new_value_action="a"),
            "Merging only dicts in default settings, where old and new value existing in both places are put in a list",
        )
        self.assertEqual(
            {"a": {"b": {"k": 1, "l": 2, "m": 3}, "t": 5}, "d": 4, "u": {"v": {"w": "x"}}},
            Fagus.merge(b, c, copy=True, update_from=1),
            "Merging only dicts in default settings, with simple dict update isf full path traversal from level 1",
        )
        self.assertEqual(
            {"1": [[1, True, "a", ["f", {"a", "q"}]], {"a": False, "1": [1]}], "a": [[3, 4], {"b": 1}]},
            Fagus.merge(self.a, self.a, copy=True),
            "Merging the test-object self.a with it self only makes every node in self.a editable",
        )
        self.assertEqual(
            self.a,
            Fagus.merge(self.a, self.a, copy=True, update_from=0),
            "Merging the test-object self.a with itself only makes every node in self.a editable",
        )
        self.assertEqual(
            {"1": [2 * Fagus.get(self.a, "1 0"), {"a": False, "1": [1]}], "a": [[3, 4], {"b": 1}]},
            Fagus.merge(self.a, self.a, copy=True, extend_from=2),
            "Merging self.a with itself, now with extend_from at level 2, so only that inner list is doubled",
        )
        self.assertEqual(
            list(range(1, 7)), Fagus.merge([1, 2, 3], [4, 5, 6], copy=True, extend_from=0), "extend_from at level 0"
        )
        self.assertEqual({"a", "b", "c", "e"}, Fagus.merge({"a"}, ("b", "c", "e")), "Updating set with Sequence, lvl 0")
        self.assertEqual({"a", "b", "c", "e"}, Fagus.merge({"a"}, {"b", "c", "e"}), "Updating set with set, lvl 0")
        self.assertRaisesRegex(TypeError, "Unsupported operand types", Fagus.merge, set(), {})
        self.assertRaisesRegex(TypeError, "Unsupported operand types", Fagus.merge, [1, 2, 3], {})
        self.assertRaisesRegex(TypeError, "Unsupported operand types", Fagus.merge, {}, [1, 2, 3])
        with open(self.test_data_path) as fp:
            a = Fagus(json.load(fp))
        self.assertEqual(
            a["data"][5:],
            Fagus.merge(a["data"][:5], a["data"][5:], copy=True),
            "Overriding the first five records in the test-data with the last",
        )
        self.assertEqual(
            a["data"][5:],
            Fagus.merge([], a["data"][5:], copy=True),
            "Overriding the first five records in the test-data with the last",
        )
        self.assertEqual(
            {
                "id": 9922401,
                "lastModified": 1385016682000,
                "sourceId": 301,
                "source": {"id": 301, "alias": "joxeankoret-c4", "name": "Joxeankoret (diff)"},
                "roleId": 33,
                "role": {"id": 33, "alias": "malware-server", "name": "Malware server"},
                "firstSeen": 1385016663000,
                "lastSeen": 1385664000000,
                "numObservations": 1,
                "state": 3,
                "comment": None,
                "domainName": {"fqdn": "dlp.dlsofteclipse.com"},
                "responseCode": 200,
                "limit": 10000,
                "offset": 0,
                "count": 0,
                "size": 10000,
            },
            Fagus.merge(a["data 4"], Fagus.iter(a, filter_=Fil(..., VFil(lambda x: isinstance(x, int))), copy=True)),
            "Merging with filtered iterator, without touching the original object",
        )
        self.assertEqual([1, 2, 3], Fagus([{"a": 1}]) + [1, 2, 3], "Testing the plus (+) operator")
        self.assertEqual([{"a": 1}, 2, 3], [1, 2, 3] + Fagus([{"a": 1}]), "Testing the plus (+) operator from right")

    def test_pop(self):
        a = Fagus(self.a, copy=True)
        b = copy.deepcopy(self.a)
        self.assertEqual(a.pop("1 0 2"), b["1"][0].pop(2), "Pop correctly drops the value at the position")
        a.pop("8 9 10")
        self.assertEqual(a(), b, "Pop did not modify the object as path doesn't exist")
        self.assertIsNone(a.pop("8"), "When pop fails because the Key didn't exist in the node, default is returned")
        b["1"][0][2][1].remove("a")
        self.assertEqual("a", a.pop("1 0 2 1 a"), "Correctly popping from set (internally calling remove)")
        self.assertEqual(b.pop("a"), a.pop("a"), "Correctly popping from dict at base-level")
        self.assertEqual(a(), b, "Pop has correctly modified the object")
        a = Fagus((((1, 0), 2), (3, 4, (5, (6, 7)), 8)))
        self.assertRaisesRegex(TypeError, "Can't modify base-object self having the immutable type", a.pop, "1 2 1 1")
        a = Fagus(list(a))
        self.assertEqual(7, a.pop("1 2 1 1"), "Correctly popping when all tuples on the way must be converted to lists")
        self.assertEqual([((1, 0), 2), [3, 4, [5, [6]], 8]], a(), "The tuples were correctly converted to lists")
        self.assertEqual(Fagus((1, 0)), a.pop("0 0", fagus=True), "Returning Fagus-object if return_value is set")
        a = Fagus((((1, 0), 2), [3, 4, (5, (6, 7)), 8]))
        del a["1 2 1 1"]
        self.assertEqual((((1, 0), 2), [3, 4, [5, [6]], 8]), a(), "Keeping tuples below if possible, testing [] del")
        a = Fagus({"a": "b", "c": "d"})
        del a.c
        self.assertEqual({"a": "b"}, a(), "Using dot-notation for deleting")

    def test_discard(self):
        # implementation relies 90 % on pop, so most tests are there
        a = Fagus(self.a, copy=True)
        b = copy.deepcopy(self.a)
        b["1"][0].pop(2)
        a.discard("1 0 2")
        self.assertEqual(a(), b, "Discard correctly drops the value at the position")
        a.discard("8 9 10")
        self.assertEqual(a(), b, "Discard did not modify the object as path doesn't exist, and didn't throw an error")

    def test_remove(self):
        # implementation relies 90 % on pop, so most tests are there
        a = Fagus(self.a, copy=True)
        b = copy.deepcopy(self.a)
        b["1"][0].pop(2)
        a.remove("1 0 2")
        self.assertEqual(a(), b, "Remove correctly drops the value at the position")
        self.assertRaisesRegex(KeyError, "Couldn't remove .*: Does not exist", a.remove, "8 9 10")
        self.assertEqual(a(), b, "Remove did not modify the object as path doesn't exist, and didn't throw an error")

    def test_keys(self):
        self.assertEqual(("1", "a"), tuple(Fagus.keys(self.a)), "Getting dict-keys from base dict")
        self.assertIsInstance(Fagus.keys(self.a, "a 1"), type({}.keys()), "Dicts (also inside the node) give dict_keys")
        self.assertIsInstance(Fagus.keys(self.a, "1"), range, "A list returns a range")
        self.assertEqual((0, 1), tuple(Fagus.keys(self.a, "1")), "A list returns numeric indexes")
        self.assertEqual((..., ...), tuple(Fagus.keys(self.a, "1 0 3 1")), "A Set gives ... for each element")
        self.assertEqual((), Fagus.keys(self.a, "1 0 3 5"), "A nonexisting path gives empty keys (an empty tuple)")

    def test_values(self):
        with open(self.test_data_path) as fp:
            a = Fagus(json.load(fp))
        self.assertEqual(tuple(a.values()), tuple(a.values()), "The same dict-values if the base node is a dict")
        b = [
            9922401,
            1385016682000,
            301,
            Fagus({"id": 301, "alias": "joxeankoret-c4", "name": "Joxeankoret (diff)"}),
            33,
            Fagus({"id": 33, "alias": "malware-server", "name": "Malware server"}),
            1385016663000,
            1385664000000,
            1,
            3,
            None,
            Fagus({"fqdn": "dlp.dlsofteclipse.com"}),
        ]
        self.assertEqual(b, list(a.values("data 4", fagus=True)), "Correctly returning dict values, with Fagus's")
        b = (200, 10000, 0, 0, Fagus({}), Fagus([]), a.get("data", fagus=True), 10000)
        self.assertEqual(b, tuple(a.values(fagus=True)), "Correctly returning nodes in a dict")
        self.assertEqual((), a.values("data 12"), "Returning empty tuple for a path that doesn't exist")
        self.assertEqual((10000,), a.values("size"), "Singleton value is returned alone in a tuple")

    def test_items(self):
        self.assertIsInstance(Fagus.items(self.a), type({}.items()), "Dict gives dict-items")
        self.assertIsInstance(Fagus.items(self.a, "1"), enumerate, "List gives enumerate-obj")
        self.assertTrue(all(isinstance(v, Fagus) for _, v in Fagus.items(self.a, fagus=True)), "fagus ok")
        self.assertEqual({(..., "a"), (..., "q")}, set(Fagus.items(self.a, "1 0 3 1")), "(..., e) for elements set")
        self.assertEqual(tuple(Fagus.iter(self.a, 0)), tuple(Fagus.items(self.a)), "items at base = iter at base")

    def test_index(self):
        self.assertIsNone(Fagus.index(self.a, 1, path="hallo"), "Return None if there is no node at path")
        self.assertEqual(("", 6), tuple(Fagus.index({2: 7, "": 3, 6: 3, 4: 9}, 3, all_=True)), "All matching dict-keys")
        self.assertFalse(Fagus.index(self.a, "p", path="1 0 3 1"), "True if the element exists in set")
        self.assertTrue(Fagus.index(self.a, "q", path="1 0 3 1"), "True if the element exists in set")
        self.assertEqual("b", Fagus.index(self.a, 1, path="a 1"), "Getting index from dict")
        self.assertIsNone(Fagus.index(self.a, 8, path="a 1"), "Getting None because 8 doesn't exist in dict")
        self.assertEqual(1, Fagus.index([2, 5, 6, 5, 4, 3, 5, 1], 5), "Gives the first index in the list")
        self.assertIsNone(Fagus.index([2, 5, 6, 5, 4, 3, 5, 1], 9), "The element is not in list - None")
        self.assertEqual([1, 3, 6], Fagus.index([2, 5, 6, 5, 4, 3, 5, 1], 5, all_=True), "All list indices")
        self.assertEqual([3], Fagus.index([2, 5, 6, 5, 4, 3, 5, 1], 5, -6, -3, all_=True), "All list indices")
        self.assertEqual([3], Fagus.index([2, 5, 6, 5, 4, 3, 5, 1], 5, 2, -3, all_=True), "All list indices")
        self.assertEqual([1, 3, 6], Fagus.index([2, 5, 6, 5, 4, 3, 5, 1], 5, -10, 20, all_=True), "All list indices")
        self.assertEqual([6], Fagus.index([2, 5, 6, 5, 4, 3, 5, 1], 5, -2, -1, all_=True), "All list indices")
        self.assertEqual(6, [2, 5, 6, 5, 4, 3, 5, 1].index(5, -2, -1), "For reference to see if it is called right")

    def test_clear(self):
        self.assertEqual({}, Fagus.clear(self.a, copy=True), "Emptying at base level gives an empty dict")
        self.assertEqual({"1": [], "a": [[3, 4], {"b": 1}]}, Fagus.clear(self.a, "1", copy=True), "clear a list inside")
        self.assertEqual(
            {"1": [[1, True, "a", []], {"a": False, "1": (1,)}], "a": [[3, 4], {"b": 1}]},
            Fagus.clear(self.a, "1 0 3", copy=True),
            "Clearing a tuple (giving an empty list)",
        )
        self.assertEqual(self.a, Fagus.clear(self.a, "a b c", copy=True), "No change if node doesn't exist")
        self.assertEqual(self.a, Fagus.clear(self.a, "a 0 1", copy=True), "No change if node can't be cleared")

    def test_contains(self):
        self.assertTrue(Fagus.contains(self.a, True, "1 0"), "path exists, and value is in node at path")
        self.assertFalse(Fagus.contains(self.a, False, "1 0"), "path exists, but value doesn't exist in node at path")
        self.assertTrue(Fagus.contains(self.a, "a", "1 0 2"), "If it is not a node but just a value, compare that")
        self.assertFalse(Fagus.contains(self.a, "q", "1 0 2"), "If it is not a node but just a value, compare that")
        self.assertFalse(Fagus.contains(self.a, "q", "1 0 ha"), "False if path doesn̈́'t exist")

    def test_count(self):
        self.assertEqual(4, Fagus.count(self.a, "1 0"), "Counting an existing list")
        self.assertEqual(2, Fagus.count(self.a, "1 1"), "Counting an existing dict")
        self.assertEqual(2, Fagus.count(self.a, "1 0 3 1"), "Counting an existing set")
        self.assertEqual(0, Fagus.count(self.a, "Hei god morgen"), "When the node doesn't exist, return 0")
        self.assertEqual(1, Fagus.count(self.a, "1 0 1"), "When the node is a simple value, return 1")

    def test_isdisjoint(self):
        self.assertFalse(Fagus.isdisjoint(self.a, {"a"}), "check dict keys (which is the default)")
        self.assertRaisesRegex(ValueError, "dict_ attribute must bei either k", Fagus.isdisjoint, {}, {}, dict_="hansi")
        self.assertTrue(Fagus.isdisjoint({2: 1, 4: 3}, {2, 4}, dict_="values"), "check dict values")
        self.assertFalse(Fagus.isdisjoint({2: 1, 4: 3}, ((5, 6), (8, 9), (2, 1)), dict_="items"), "check dict items")
        self.assertTrue(Fagus.isdisjoint(self.a, {"a"}, "hubert"), "must be True if the path doesn't exist")
        self.assertFalse(Fagus.isdisjoint(self.a, {"a"}, "1 0 3 1"), "check if it works for a set deeply inside")
        self.assertFalse(Fagus.isdisjoint((1, 2, 3, 4), [3, 4]), "check if it works for tuples and lists")

    def test_reversed(self):
        self.assertEqual(
            (
                [[3, 4], {"b": 1}],
                [[1, True, "a", ("f", {"a", "q"})], {"a": False, "1": (1,)}],
            ),
            tuple(Fagus.reversed(self.a)),
            "Reversing dict-values works, gives lifo-ordering instead of default fifo",
        )
        self.assertEqual((("f", {"a", "q"}), "a", True, 1), tuple(Fagus.reversed(self.a, "1 0")), "Reversing list")
        self.assertTrue(
            all(isinstance(e, Fagus) for e in Fagus.reversed(self.a, "a", fagus=True)), "fagus does its job"
        )
        self.assertEqual((), tuple(Fagus.reversed(self.a, "hei og hopp")), "Return empty tuple if noed doesn't exist")
        self.assertEqual((3, 2, 1), tuple(reversed(Fagus((1, 2, 3)))), "Testing if __reversed__ also works")

    def test_reverse(self):
        self.assertRaisesRegex(TypeError, "Cannot reverse base node of type", Fagus.reverse, set())
        self.assertRaisesRegex(TypeError, "Cannot reverse base node of type", Fagus.reverse, self.a["1"][0][3])
        self.assertRaisesRegex(TypeError, "Cannot reverse node of type", Fagus.reverse, self.a, "1 0 3 1", copy=True)
        self.assertEqual({"a": self.a["a"], "1": self.a["1"]}, Fagus.reverse(self.a, copy=True), "Reversing base dict")
        a = Fagus(self.a, copy=True)
        b = Fagus.copy(self.a)
        b["1"][0].reverse()
        self.assertEqual(b, a.reverse("1 0"), "Reversing list inside tree")
        b["1"][0][0] = list(reversed(b["1"][0][0]))
        self.assertEqual(b, a.reverse("1 0 0"), "Reversing tuple (which converts it to a list)")
        b["1"].reverse()
        self.assertEqual(b["1"], Fagus.reverse(a["1"]), "Reversing base list")
        a = {"a": {"b": 1, "c": {"f": 4, "g": 3}}, "d": 3}
        self.assertEqual(a, Fagus.reverse(Fagus.reverse(a, "a"), "a"), "Double reversing a dict inside a tree")
        b = Fagus.copy(a)
        b["a"]["c"] = {"g": 3, "f": 4}
        self.assertEqual(b, Fagus.reverse(a, "a c"), "Reversing a dict inside a tree")

    def test_child(self):
        a = Fagus(self.a, fagus=True, value_split="_")
        b = a.child({"1": 9, 3: 11})
        self.assertEqual(a._options, b._options, "a child has the same settings as its parent")

    def test_copy(self):
        a = copy.deepcopy(self.a)
        b = Fagus(a, copy=True)
        self.assertEqual(a, b(), "Shallow-copy is actually equal to the original object if it isn't changed")
        b.pop("a")
        self.assertNotEqual(a, b(), "Can pop at base-level without affecting the original object")
        b = Fagus(a, copy=True)
        b["f"] = 2
        self.assertNotEqual(a, b(), "Can add at base-level without affecting the original object")
        b = Fagus(a).copy()
        b["1 0 0"] = 100
        self.assertNotEqual(a, b(), "Can change node deeply in the original object without affecting original object")
        b = Fagus(a, copy=True)
        b.pop("1 0 3")
        self.assertNotEqual(a, b(), "Can pop deeply in the object without affecting the original object")

    def test_repr(self):
        a = Fagus({"a": 9, "c": [1, 2, False]}, value_split="_", fagus=True)
        b = eval(repr(a))
        self.assertEqual(a, b, "Able to create equivalent obj from repr")
        self.assertEqual(a._options, b._options, "Able to create equivalent obj from repr, even with settings")

    # tests for the + and +=-operators are in test_merge, test_add tests the add-function

    def test_sub(self):
        a = Fagus(self.a, copy=True)
        self.assertEqual({"a": [[3, 4], {"b": 1}]}, a - {"1"}, "Removing keys from base-dict")
        a.fagus = True
        self.assertEqual(Fagus({"a": [[3, 4], {"b": 1}]}), a - "1", "Removing key from base-dict, with fagus")
        self.assertEqual(self.a, a(), "a was not modified by these operations")
        b = Fagus(a["1 0"], copy=True)
        b -= [1, "a"]
        self.assertEqual([True, ("f", {"a", "q"})], b(), "isub removes items as it should")
        self.assertRaisesRegex(TypeError, "Unsupported operand types for -=", Fagus(("a", "b")).__isub__, ("a",))
        self.assertEqual([8, 9], (6, 8, 7, 9, 11) - Fagus({6, 7, 11}), "rsub with a set on a tuple gives a list")
        self.assertEqual({8, 9}, frozenset({6, 8, 7, 9}) - Fagus((6, 7)), "rsub with a tuple on a set gives a set")

    def test_mul(self):
        a = Fagus(self.a["1"][0], copy=True)
        self.assertEqual(3 * self.a["1"][0], 3 * a, "rmul works as intended on a list")
        self.assertEqual((3, 9, 3, 9, 3, 9, 3, 9), Fagus((3, 9)) * 4, "mul works as intended on a tuple")
        self.assertEqual(self.a["1"][0], a(), "A was not modified by mul and rmul")
        self.assertRaisesRegex(TypeError, "Unsupported operand types for", Fagus(self.a).__mul__, 3)
        a *= 2
        self.assertEqual(2 * self.a["1"][0], a(), "imul does what it's supposed to do")
        self.assertRaisesRegex(TypeError, "Unsupported operand types for", Fagus(self.a).__imul__, 3)
        self.assertRaisesRegex(TypeError, "Unsupported operand types for", a.__imul__, "a")
        self.assertRaisesRegex(TypeError, "Unsupported operand types for", a.__rmul__, "a")

    def test_tfunc(self):
        def f(*args, **kwargs):
            return args, kwargs

        self.assertEqual(((987,), {}), Func(f)(987), "Default puts only old value as argument")
        a = Func(f, 1, "hans", egil="snorkler")
        self.assertEqual((("wurst", "hans"), {"egil": "snorkler"}), a("wurst"), "default argument old_value first")
        a = Func(f, "kwarg", "henriette", klaus="wagner")
        self.assertEqual((("henriette",), {"kwarg": 72, "klaus": "wagner"}), a(72), "old_value comes as kwarg")
        a = Func(f, 2, "hans", "wurst", egil="snorkler")
        self.assertEqual((("hans", 0, "wurst"), {"egil": "snorkler"}), a(0), "old_value in the middle")
        a = Func(f, -2, "hans", "wurst", egil="snorkler")
        self.assertEqual((("hans", 0, "wurst"), {"egil": "snorkler"}), a(0), "old_value in the middle, negative index")
        a = Func(f, -1, "hans", "wurst", egil="snorkler")
        self.assertEqual((("hans", "wurst", 6), {"egil": "snorkler"}), a(6), "old_value in the end")
        a = Func(f, 599, "hans", "wurst")
        self.assertEqual((("hans", "wurst", 6), {}), a(6), "too large index goes to the end")
        a = Func(f, -599, "hans", "wurst")
        self.assertEqual(((7, "hans", "wurst"), {}), a(7), "too large negative index goes first")


if __name__ == "__main__":
    unittest.main()
