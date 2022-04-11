import copy
import json
import re
import unittest
from ipaddress import IPv6Address, IPv4Network, IPv6Network, ip_address
from treeo import TreeO, TFunc, TFil, TCFil, TVFil
from datetime import datetime, date, time


class HashableDict(dict):
    def __hash__(self):
        return hash(frozenset(self.items()))


class TestTreeO(unittest.TestCase):
    def setUp(self) -> None:
        self.a = None
        setattr(self, "a", {"1": [[1, True, "a", ("f", {"a", "q"})], {"a": False, "1": (1,)}], "a": [[3, 4], {"b": 1}]})

    def test_get(self):
        a = TreeO(self.a)
        TreeO.default = 7
        self.assertEqual(7, a["1 2 3"], "Returning default-value for class when unset for object")
        a.default = 3
        self.assertEqual(3, a["1 2 3"], "Returning default-value for object as it is now set")
        self.assertEqual(1, TreeO.get(self.a, ("1", 0, 0)), "Path existing, return value at path")
        self.assertEqual(1, a["1 0 0"], "Path existing, return value at path")
        self.assertIn("q", TreeO.get(self.a, ("1", 0, 3, 1)), "Path existing, return value at path")
        self.assertEqual(1, TreeO(self.a).get((1, 0, 0), 1), "Path not existing return default that comes from param")
        self.assertEqual(1, TreeO.get((((1, 0), 2), 3), "0 0 0"), "Successfully traversing tuples")
        del TreeO.default

    def test_iter(self):
        a = TreeO(self.a, copy=True)
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
            ("1", 0, TreeO([1, True, "a", ("f", {"q", "a"})])),
            ("1", 1, TreeO({"a": False, "1": (1,)})),
            ("a", 0, TreeO([3, 4])),
            ("a", 1, TreeO({"b": 1})),
        ]
        self.assertEqual(
            b, list(a.iter(1, return_node=True)), "Returning nodes as TreeO-objects when return_value=True"
        )
        self.assertTrue(
            all(isinstance(e, TreeO) for e in a.iter(1, return_node=True, reduce=-1)),
            "return_node actually returns back nodes if the nodes at the end are suitable to be converted",
        )
        self.assertEqual(
            tuple(a.iter(4, "", filter_=TFil("a", 1, lambda x: x % 2 != 0, inexclude="---"))),
            tuple(a.iter(4, "", filter_=TFil("1", 0, lambda x: x % 2 == 0))),
            "Two opposite filters giving the same results on the data",
        )
        self.assertEqual(
            ["a"],
            list(a.iter(path=("1", 0, 3), filter_=TFil(1, ..., "q", inexclude="++-"), reduce=-1)),
            "Correctly filtering a set in the end",
        )
        self.assertEqual(
            [(3, [{"a"}])],
            list(a.iter(0, ("1", 0), TFil(3, 1, ..., "q", inexclude="+++-"), filter_ends=True)),
            "Correctly putting a filtered last node in the end when combining filter_ and max-depth",
        )
        self.assertEqual(
            [
                (TreeO([[3, 4], {"b": 1}]), 0, TreeO([3, 4]), 0, 3),
                (TreeO([[3, 4], {"b": 1}]), 0, TreeO([3, 4]), 1, 4),
                (TreeO([[3, 4], {"b": 1}]), 1, TreeO({"b": 1}), "b", 1),
            ],
            list(a.iter(path="a", return_node=True, iter_nodes=True)),
            "Using iter_nodes to get references to all the nodes that have been traversed on the way",
        )
        self.assertEqual(
            {"1": [{"a": False, "1": (1,)}], "a": [{"b": 1}]},
            a.iter(filter_=TFil(..., 1)).skip(0),
            "Using iterator.skip() actually filters the skipped node if necessary",
        )
        with open("test-data.json") as fp:
            a = TreeO(json.load(fp))
        self.assertEqual(
            [(0, "source", "id", 889), (1, "source", "id", 5662), (4, "source", "id", 301)],
            list(a.iter(-1, "data", TFil(..., "source", "id", lambda x: x > 300))),
            "Iterating over all source-ids that are > 300, testing lambda and true and default",
        )
        self.assertEqual(
            (2, 1, 3),
            tuple(
                a.iter(
                    -1,
                    "data",
                    TFil(
                        ...,
                        (TCFil("source", "id", lambda x: x > 300), "state"),
                    ),
                    reduce=-1,
                )
            ),
            "Getting the states for all sources who's id is > 300 using reduce and a check-filter",
        )
        self.assertEqual(
            [],
            list(a.iter(path="data", filter_=TFil((TVFil(lambda x: len(x) < 1), ...)))),
            "Verifying that a value-filter actually returns an empty list if its condition isn't met",
        )
        self.assertEqual(
            160,
            len(list(a.iter(path="data", filter_=TFil((TVFil(lambda x: len(x) == 10), ...))))),
            "Verifying that a value-filter actually returns the node if it's condition is met",
        )
        self.assertEqual(
            160,
            len(list(a.iter(filter_=TFil("data", TVFil(lambda x: len(x) > 1))))),
            "Verifying that a value-filter also works if it comes as a standalone argument, then including all the "
            "subnodes the filter matches (in this case all).",
        )
        self.assertEqual(
            [],
            list(a.iter(filter_=TFil("data", (TVFil(lambda x: len(x) < 1),)))),
            "A value-filter actually returns an empty list even at the bottom if its condition isn't met",
        )
        self.assertEqual(
            160,
            len(list(a.iter(path="data", filter_=TFil((TVFil(lambda x: len(x) > 1),))))),
            "If the only member in a tuple is TValue- and TCheck-filters and they're all removed, put ... at that"
            "argument to make sure these check-filters can match anything",
        )
        self.assertEqual(
            [(0, "role", "id", 182), (0, "role", "name", "Intel from sandbox runs"), (0, "state", 2)],
            list(
                a.iter(
                    path="data",
                    filter_=TFil(
                        ...,
                        (
                            TCFil(
                                (
                                    TVFil(lambda x: len(x) == 3, lambda x: bool(x)),
                                    TCFil("alias", "file-analyzer-domain"),
                                    "source",
                                ),
                                "id",
                                889,
                            ),
                            TFil("state", 1, inexclude="+-"),
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
            a.iter(filter_=TFil("responseCode|limit|data", ..., ("role.*", re.compile("source.*")), str_as_re=True))
        )
        self.assertTrue(all(e in b for e in c), "Checking if it works to convert str to regex when requested")
        filter_args = ["a|c", ("abc", "a.*")]
        self.assertEqual(filter_args, TFil(*filter_args).args, "No str args are changed if string_as_re=False")
        self.assertEqual(
            [re.compile(filter_args[0]), [filter_args[1][0], re.compile(filter_args[1][1])]],
            TFil(*filter_args, str_as_re=True).args,
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
        self.assertEqual(b, set(TreeO.iter(f)), "Iterating through sets, some sets stacked in sets")
        self.assertEqual(
            [("responseCode", 200), ("limit", 10000), ("offset", 0), ("data", 4, {"state": 3, "comment": None})],
            list(
                a.iter(
                    1,
                    filter_=TFil(({"responseCode", "limit", "offset"}, TFil("data", 4, {"comment", "state"}))),
                    filter_ends=True,
                )
            ),
            "Using sets to accelerate filtering, both as a standalone argument and with other args in a tuple",
        )

    def test_filter(self):
        self.assertEqual(
            {"1": [{"a": False, "1": (1,)}], "a": [{"b": 1}]},
            TreeO.filter(self.a, filter_=TFil(..., lambda x: x % 2), copy=True),
            "Filtering using a lambda on the default test-datastructure",
        )
        self.assertEqual(
            {"1": [[1, True, "a", ("f", {"q", "a"})]], "a": [[3, 4]]},
            TreeO.filter(self.a, filter_=TFil(..., lambda x: x % 2, inexclude="--"), copy=True),
            "Filtering using a lambda on the default test-datastructure",
        )
        with open("test-data.json") as fp:
            a = TreeO(json.load(fp))
        self.assertEqual(
            {"responseCode": 200, "limit": 10000, "size": 10000},
            a.filter(TFil({"responseCode", "limit", "size"}), copy=True),
            "Simplest ever filtering at base-level",
        )
        self.assertEqual(
            dict(responseCode=200, limit=10000, messages=[], metaData={}, offset=0, count=0, size=10000),
            a.filter(TFil("data", inexclude="-"), copy=True),
            "Using inexclude to turn around the filter and give everything except data at base-level",
        )
        self.assertEqual(
            [
                {"sourceId": 889, "roleId": 182, "firstSeen": 1548169200000, "lastSeen": 1561951800000},
                {"sourceId": 5662, "roleId": 33, "firstSeen": 1548169200000, "lastSeen": 1552989600000},
            ],
            a.filter(
                TFil(..., (TCFil("state", 3, invert=True), ".*(Seen|Id)"), str_as_re=True),
                "data",
                copy=True,
            ),
            "Testing invert on a TCheckFilter, getting all the nodes that have a state unlike 3",
        )
        b = TreeO(a, copy=True)
        b.filter(
            path="data",
            filter_=TFil(
                ...,
                (
                    TCFil(
                        (
                            TVFil(lambda x: len(x) == 3, lambda x: bool(x)),
                            TCFil("alias", "file-analyzer-domain"),
                            "source",
                        ),
                        "id",
                        889,
                    ),
                    TFil("state", 1, inexclude="+-"),
                    "role",
                ),
                "alias",
                inexclude="++-",
            ),
        ),
        self.assertEqual(
            TreeO(
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
            a.filter(path="data", filter_=TFil((TVFil(lambda x: len(x) < 1), ...)), copy=True),
            "Verifying that a value-filter actually returns an empty list if its condition isn't met",
        )
        self.assertEqual(
            a["data"],
            a.filter(path="data", filter_=TFil((TVFil(lambda x: len(x) == 10), ...)), copy=True),
            "Verifying that a value-filter actually returns the whole node if its condition is met",
        )
        self.assertEqual(
            {"data": a["data"]},
            a.filter(filter_=TFil("data", TVFil(lambda x: len(x) > 1)), copy=True),
            "Verifying that a value-filter also works if it comes as a standalone argument, then including all the "
            "subnodes the filter matches (in this case all).",
        )
        self.assertEqual(
            {"data": a["data"]},
            a.filter(filter_=TFil("data", TVFil(lambda x: len(x) < 10, invert=True)), copy=True),
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
            TreeO.split(self.a, TFil(..., lambda x: x % 2), copy=True),
            "Splitting using a lambda on the default test-datastructure",
        )
        self.assertEqual(
            (
                TreeO.filter(self.a, TFil(..., lambda x: x % 2), copy=True),
                TreeO.filter(self.a, TFil(..., lambda x: not x % 2), copy=True),
            ),
            TreeO.split(self.a, TFil(..., lambda x: x % 2), copy=True),
            "Splitting gives the same result as applying the filter two times, opposite ways on copies",
        )
        self.assertEqual(
            split_res[::-1],
            TreeO.split(self.a, TFil(..., lambda x: x % 2, inexclude="--"), copy=True),
            "Splitting using a lambda on the default test-datastructure, and with inexclude",
        )
        q = {"a": "b", "f": {"g", "q", "d"}, "g": {1: 3, 2: 4}}
        self.assertEqual(
            q,
            TreeO.merge(*TreeO.split(q, TFil(lambda x: ord(x) % 2, "g", inexclude="----"), copy=True)),
            "Splitting and remerging dicts and sets works as if they were never separated",
        )
        with open("test-data.json") as fp:
            a = TreeO(json.load(fp))
        in_, out = a.split(TFil(..., TCFil("state", 3)), path="data", copy=True, return_node=True)
        self.assertIsInstance(in_, TreeO, "return_node is on, so in_ must be a TreeO")
        self.assertIsInstance(out, TreeO, "return_node is on, so out must be a TreeO")
        self.assertEqual({3}, set(in_.iter(filter_=TFil(..., "state"), reduce=-1)), "all items in in_ match the filter")
        self.assertNotEqual({3}, set(out.iter(filter_=TFil(..., "state"), reduce=-1)), "no items in out match filter")
        self.assertEqual((662, 762), tuple(out.iter(filter_=TFil(..., "id"), reduce=-1)), "correct ids in out")
        self.assertEqual(len(a["data"]), len(in_) + len(out), "All elements are either in in our out")
        in_, out = a.split(TFil(), path="data", copy=True)
        self.assertEqual(a["data"], in_, "If the filter matches everything, in_ must be equal to the original node")
        self.assertEqual([], out, "If the filter matches everything, out must be an empty list")
        in_, out = a.split(TFil("a"), copy=True)
        self.assertEqual({}, in_, "If the filter matches nothing, in_ must be an empty list")
        self.assertEqual(a(), out, "If the filter matches nothing, in_ must be equal to the original node")
        self.assertEqual(
            ("a", "a"), a.split(TFil(), "a", default="a"), "Default is returned for in_ and out if path doesn't exist"
        )

    def test_set(self):
        a = TreeO(self.a, copy=True)
        b = copy.deepcopy(self.a)
        b["1"][0][1] = False
        self.assertEqual(
            b,
            TreeO.set(a, False, "1 0 1"),
            "Correctly traversing dicts and lists with numeric indices when the node type is not given explicitly.",
        )
        # verify that base object is writable for set
        self.assertRaisesRegex(
            TypeError,
            "Can't modify base-object self having the immutable type",
            TreeO.set,
            (((1, 0), 2), 3),
            7,
            "0 0 0",
        )
        # new nodes can only either be lists or dicts, expressed by l's and
        self.assertRaisesRegex(ValueError, "The only allowed characters in ", TreeO.set, a["1"], "f", "0", "pld")
        # Due to limitations on how references work in Python, the base-object can't be changed. So if the base-object
        # is a list, it can't be converted into a dict. These kind of changes are possible at the lower levels.
        self.assertRaisesRegex(TypeError, "Your base object is a (.*|see comment)", TreeO.set, a, "f", "0", "lld")
        # if the user defines that he wants a list, but it's not possible to parse numeric index from t_path raise error
        self.assertRaisesRegex(ValueError, "Can't parse numeric list-index from", TreeO.set, a, "f", "1 f", "dl")
        a[("1", 1)] = "hei"
        b["1"][1] = "hei"
        self.assertEqual(b, a(), "Using __set_item__ to set a value")
        a.value_split = "_"
        a.a_1_b = 2
        b["a"][1]["b"] = 2
        self.assertEqual(a(), b, "Using another path separator and __setattr__")
        b["1"] = {"0": {"0": {"g": [9, 5]}}}
        self.assertEqual(b, a.set({"g": [9, 5]}, "1øæ0øæ0", "ddd", value_split="øæ"), "Replace list with dict")
        self.assertEqual([[["a"]]], TreeO.set([], "a", "1 1 1", default_node_type="l"), "Only create lists")
        a = TreeO(self.a, copy=True)
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
        a = TreeO((((1, 0), 2), (3, 4, (5, (6, 7)), 8)))
        self.assertRaisesRegex(TypeError, "Can't modify base-object self having the immutable typ", a.set, 5, "1 2 1 1")
        a = TreeO(list(a))
        self.assertEqual([((1, 0), 2), [3, 4, [5, [6, 5]], 8]], a.set(5, "1 2 1 1"), "Converting right tuples to lists")
        a = TreeO((((1, 0), 2), [3, 4, (5, (6, 7)), 8]))
        a.set(5, "1 2 1 1")
        self.assertEqual((((1, 0), 2), [3, 4, [5, [6, 5]], 8]), a(), "Keeping tuples below if possible")
        a = TreeO(self.a, copy=True)
        self.assertNotEqual(a(), a.set(False, "1 1", copy=True), "The source object is not modified when copy is used")
        self.assertEqual(
            {"1": [{"b": [False]}, {"a": False, "1": (1,)}], "a": [[3, 4], {"b": 1}]},
            a.set(False, "1 0 b 1", node_types="   l", copy=True),
            "space works to not enforce node_types in path - dicts and lists are traversed as long as the keys allow it",
        )

    def test_append(self):
        a = copy.deepcopy(self.a)
        b = copy.deepcopy(self.a)
        b["a"][0].append(5)
        self.assertEqual(TreeO.append(a, 5, "a 0"), b, "appending to existing list")
        b["1"][0][3] = list(b["1"][0][3])
        b["1"][0][3][1] = list(b["1"][0][3][1])
        b["1"][0][3][1].append("f")
        b["1"][0][3][1].sort()
        TreeO.append(a, "f", "1 0 3 1")
        TreeO.get(a, "1 0 3 1").sort()
        self.assertEqual(
            a, b, "appending to set (converting to list first, both sets must be sorted for the test not to fail)"
        )
        b["1"][0][0] = [1, 5]
        self.assertEqual(TreeO.append(a, 5, "1 0 0"), b, "Creating list from singleton value and appending to it")
        b["q"] = [6]
        self.assertEqual(TreeO.append(a, 6, "q"), b, "Create new list for value at a path that didn't exist before")

    def test_extend(self):
        a = copy.deepcopy(self.a)
        b = copy.deepcopy(self.a)
        b["a"][0].extend((5, 6))
        self.assertEqual(TreeO.extend(a, (5, 6), "a 0"), b, "appending to existing list")
        b["1"][0][3] = list(b["1"][0][3])

    def test_append(self):
        a = copy.deepcopy(self.a)
        b = copy.deepcopy(self.a)
        b["a"][0].append(5)
        self.assertEqual(TreeO.append(a, 5, "a 0"), b, "appending to existing list")
        b["1"][0][3] = list(b["1"][0][3])
        b["1"][0][3][1] = list(b["1"][0][3][1])
        b["1"][0][3][1].append("f")
        b["1"][0][3][1].sort()
        TreeO.append(a, "f", "1 0 3 1")
        TreeO.get(a, "1 0 3 1").sort()
        self.assertEqual(
            a, b, "appending to set (converting to list first, both sets must be sorted for the test not to fail)"
        )
        b["1"][0][0] = [1, 5]
        self.assertEqual(TreeO.append(a, 5, "1 0 0"), b, "Creating list from singleton value and appending to it")
        b["q"] = [6]
        self.assertEqual(TreeO.append(a, 6, "q"), b, "Create new list for value at a path that didn't exist before")

    def test_extend(self):
        a = copy.deepcopy(self.a)
        b = copy.deepcopy(self.a)
        b["a"][0].extend((5, 6))
        self.assertEqual(TreeO.extend(a, (5, 6), "a 0"), b, "appending to existing list")
        b["1"][0][3] = list(b["1"][0][3])
        b["1"][0][3][1] = list(b["1"][0][3][1])
        b["1"][0][3][1].extend("fg")
        b["1"][0][3][1].sort()
        TreeO.extend(a, "fg", "1 0 3 1")
        TreeO.get(a, "1 0 3 1").sort()
        self.assertEqual(
            a, b, "extending set (converting to list first, both sets must be sorted for the test not to fail)"
        )
        b["1"][0][0] = [1, 5, 6]
        self.assertEqual(TreeO.extend(a, [5, 6], "1 0 0"), b, "Creating list from singleton value and appending to it")
        b["q"] = [6, 7]
        self.assertEqual(TreeO.extend(a, [6, 7], "q"), b, "Create new list for value at a path not existing before")
        self.assertRaisesRegex(TypeError, "Can't extend value in base-dict", TreeO().extend, [3, 4])

    def test_insert(self):
        a = copy.deepcopy(self.a)
        b = copy.deepcopy(self.a)
        b["a"][0].insert(2, "hei")
        self.assertEqual(TreeO.insert(a, 2, "hei", "a 0"), b, "appending to existing list")
        b["1"][0][3] = list(b["1"][0][3])
        b["1"][0][3][1] = list(b["1"][0][3][1])
        b["1"][0][3][1].insert(5, "fg")
        b["1"][0][3][1].sort()
        TreeO.insert(a, 5, "fg", "1 0 3 1")
        TreeO.get(a, "1 0 3 1").sort()
        self.assertEqual(
            a, b, "extending set (converting to list first, both sets must be sorted for the test not to fail)"
        )
        b["1"][0][0] = [5, 1]
        self.assertEqual(TreeO.insert(a, -3, 5, "1 0 0"), b, "Creating list from singleton value and appending to it")
        b["q"] = [5]
        self.assertEqual(TreeO.insert(a, -9, 5, "q"), b, "Create new list for value at a path that didn't exist before")
        TreeO.insert(a, 2, 4, "1"),
        TreeO.set(b, 4, "1 2", list_insert=1),
        self.assertEqual(
            a, b, "Inserting into the list at level 1 does the same as setting with list_insert at the right level"
        )

    def test_add(self):
        a = TreeO(self.a, copy=True)
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
        self.assertEqual({5, 6}, TreeO({5}).add(6), "Adding to set that is the base-object")

    def test_update(self):
        # update set
        a = TreeO(self.a, copy=True)
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
        a = TreeO(self.a, copy=True)
        b = copy.deepcopy(self.a)
        self.assertEqual(a.setdefault("a 0 0", 5), 3, "Setdefault returns existing value")
        self.assertEqual(a(), b, "SetDefault doesn't change if the value is already there")
        self.assertEqual(a.setdefault("a 7 7", 5, node_types="dll"), 5, "SetDefault returns default value")
        b["a"].append([5])
        self.assertEqual(a(), b, "SetDefault has added the value to the list")

    def test_mod(self):
        a = TreeO(self.a, copy=True)
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
        a.mod(TFunc(fancy_mod2, 1, 1, 2, 3, kwarg1=4, kwarg2=5), "1 0 0")
        self.assertEqual(b, a(), "Complex function taking keyword-arguments and ordinary arguments")

    def test_mod_all(self):
        with open("test-data.json") as fp:
            a = TreeO(json.load(fp))
        date_filter = TFil(..., {"firstSeen", "lastSeen", "lastModified"})
        b = TreeO.mod_all(a, lambda x: datetime.fromtimestamp(x / 1000), date_filter, "data", copy=True)
        self.assertTrue(
            all(isinstance(e[-1], datetime) for e in TreeO.iter(b, filter_=date_filter))
            and TreeO.get(b, "0 lastSeen") == datetime(2019, 7, 1, 5, 30)
            and isinstance(TreeO.get(a, "data 0 lastSeen"), int),
            "Made all dates in test-data human readable (converted from timestamp) while not touching original",
        )
        TreeO.mod_all(a, lambda x: x.pop("lastModified"), path="data", replace_value=False, max_depth=0)
        self.assertTrue(all("lastModified" not in e for e in a["data"]), "Modifying nodes without replacing them")
        a = [([(0, 0), 0], ([0, (0, 0, frozenset((0,))), (((0,),),)],))]
        self.assertEqual(
            [([[1, 1], 1], ([1, [1, 1, {1}], [[[1]]]],))],
            TreeO.mod_all(a, lambda x: x + 1, copy=True),
            "Only necessary modifications when nodes are transformed from immodifyable to modifyable. Also testing set",
        )

    def test_pop(self):
        a = TreeO(self.a, copy=True)
        b = copy.deepcopy(self.a)
        self.assertEqual(a.pop("1 0 2"), b["1"][0].pop(2), "Pop correctly drops the value at the position")
        a.pop("8 9 10")
        self.assertEqual(a(), b, "Pop did not modify the object as path doesn't exist")
        self.assertIsNone(a.pop("8"), "When pop fails because the Key didn't exist in the node, default is returned")
        b["1"][0][2][1].remove("a")
        self.assertEqual("a", a.pop("1 0 2 1 a"), "Correctly popping from set (internally calling remove)")
        self.assertEqual(b.pop("a"), a.pop("a"), "Correctly popping from dict at base-level")
        self.assertEqual(a(), b, "Pop has correctly modified the object")
        a = TreeO((((1, 0), 2), (3, 4, (5, (6, 7)), 8)))
        self.assertRaisesRegex(TypeError, "Can't modify base-object self having the immutable type", a.pop, "1 2 1 1")
        a = TreeO(list(a))
        self.assertEqual(7, a.pop("1 2 1 1"), "Correctly popping when all tuples on the way must be converted to lists")
        self.assertEqual([((1, 0), 2), [3, 4, [5, [6]], 8]], a(), "The tuples were correctly converted to lists")
        self.assertEqual(TreeO((1, 0)), a.pop("0 0", return_node=True), "Returning TreeO-object if return_value is set")
        a = TreeO((((1, 0), 2), [3, 4, (5, (6, 7)), 8]))
        a.pop("1 2 1 1")
        self.assertEqual((((1, 0), 2), [3, 4, [5, [6]], 8]), a(), "Keeping tuples below if possible")

    def test_merge(self):
        b = {"a": {"b": {"c": 5}}, "d": "e"}
        c = {"a": {"b": {"k": 1, "l": 2, "m": 3}, "t": 5}, "u": {"v": {"w": "x"}}, "d": 4}
        bc = b.copy()
        self.assertTrue(
            b == TreeO.merge(bc, bc.copy(), "d q") and {"a": {"b": {"c": 5}}, "d": {"q": b}} == bc,
            "The path exists that is supposed to be merged, but it is not a node. Returning obj, original obj modified",
        )
        bc = b.copy()
        self.assertTrue(
            b == TreeO.merge(bc, bc.copy(), "c d") and {"a": {"b": {"c": 5}}, "d": "e", "c": {"d": b}} == bc,
            "The path that is supposed to be merged, does not exist. Create path and return obj, original obj modified",
        )
        bc = b.copy()
        self.assertTrue(
            b == TreeO.merge(bc, bc.copy(), "c d", copy=True) and b == bc,
            "Using copy the original object is not modified, obj is just returned and that's it",
        )
        self.assertEqual(
            {"a": {"b": {"c": 5, "k": 1, "l": 2, "m": 3}, "t": 5}, "d": 4, "u": {"v": {"w": "x"}}},
            TreeO.merge(b, c, copy=True),
            "Merging only dicts in default settings, where a value that exists in both places is replaced",
        )
        self.assertEqual(
            {"a": {"b": {"c": 5, "k": 1, "l": 2, "m": 3}, "t": 5}, "d": "e", "u": {"v": {"w": "x"}}},
            TreeO.merge(b, c, copy=True, new_value_action="i"),
            "Merging only dicts in default settings, where a value that exists in both objs is kept as it was",
        )
        self.assertEqual(
            {"a": {"b": {"c": [5, 5], "k": 1, "l": 2, "m": 3}, "t": 5}, "d": ["e", 4, "e"], "u": {"v": {"w": "x"}}},
            TreeO.merge(TreeO.merge(b, c, copy=True, new_value_action="a"), b, copy=True, new_value_action="a"),
            "Merging only dicts in default settings, where old and new value existing in both places are put in a list",
        )
        self.assertEqual(
            {"a": {"b": {"k": 1, "l": 2, "m": 3}, "t": 5}, "d": 4, "u": {"v": {"w": "x"}}},
            TreeO.merge(b, c, copy=True, update_from=1),
            "Merging only dicts in default settings, with simple dict update isf full path traversal from level 1",
        )
        self.assertEqual(
            {"1": [[1, True, "a", ["f", {"a", "q"}]], {"a": False, "1": [1]}], "a": [[3, 4], {"b": 1}]},
            TreeO.merge(self.a, self.a, copy=True),
            "Merging the test-object self.a with it self only makes every node in self.a editable",
        )
        self.assertEqual(
            self.a,
            TreeO.merge(self.a, self.a, copy=True, update_from=0),
            "Merging the test-object self.a with itself only makes every node in self.a editable",
        )
        self.assertEqual(
            {"1": [2 * TreeO.get(self.a, "1 0"), {"a": False, "1": [1]}], "a": [[3, 4], {"b": 1}]},
            TreeO.merge(self.a, self.a, copy=True, extend_from=2),
            "Merging self.a with itself, now with extend_from at level 2, so only that inner list is doubled",
        )
        self.assertEqual(
            list(range(1, 7)), TreeO.merge([1, 2, 3], [4, 5, 6], copy=True, extend_from=0), "extend_from at level 0"
        )
        self.assertEqual({"a", "b", "c", "e"}, TreeO.merge({"a"}, ("b", "c", "e")), "Updating set with Sequence, lvl 0")
        self.assertEqual({"a", "b", "c", "e"}, TreeO.merge({"a"}, {"b", "c", "e"}), "Updating set with set, lvl 0")
        self.assertRaisesRegex(TypeError, "Unsupported operand types", TreeO.merge, set(), {})
        self.assertRaisesRegex(TypeError, "Unsupported operand types", TreeO.merge, [1, 2, 3], {})
        self.assertRaisesRegex(TypeError, "Unsupported operand types", TreeO.merge, {}, [1, 2, 3])
        with open("test-data.json") as fp:
            a = TreeO(json.load(fp))
        self.assertEqual(
            a["data"][5:],
            TreeO.merge(a["data"][:5], a["data"][5:], copy=True),
            "Overriding the first five records in the test-data with the last",
        )
        self.assertEqual(
            a["data"][5:],
            TreeO.merge([], a["data"][5:], copy=True),
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
            TreeO.merge(a["data 4"], TreeO.iter(a, filter_=TFil(..., TVFil(lambda x: isinstance(x, int))), copy=True)),
            "Merging with filtered iterator, without touching the original object",
        )
        self.assertEqual([1, 2, 3], TreeO([{"a": 1}]) + [1, 2, 3], "Testing the plus (+) operator")
        self.assertEqual([{"a": 1}, 2, 3], [1, 2, 3] + TreeO([{"a": 1}]), "Testing the plus (+) operator from right")

    def test_serialize(self):
        test_obj = {date(2021, 3, 6): [time(6, 45, 22), datetime(2021, 6, 23, 5, 45, 22)], ("hei", "du"): {3, 4, 5}}
        a = TreeO(test_obj, copy=True)
        self.assertRaisesRegex(
            TypeError,
            "Can't modify base-object self having the immutable type",
            TreeO((1, 2, 3, [4, 5, 6], {6, 5})).serialize,
        )
        self.assertRaisesRegex(
            ValueError, "Dicts with composite keys \\(tuples\\) are not supported in", a.serialize, copy=True
        )
        b = {"2021-03-06": ["06:45:22", "2021-06-23 05:45:22"], "hei du": [3, 4, 5]}
        self.assertEqual(a.serialize({"tuple_keys": lambda x: " ".join(x)}), b, "Serialized datetime and tuple-key")
        self.assertEqual(a.serialize(), b, "Nothing changes if there is nothing to change")
        a = TreeO(test_obj, copy=True)
        a[("hei du",)] = a.pop((("hei", "du"),))
        self.assertEqual(a.serialize(), b, "Also works when no mod-functions are defined in the parameter")
        a = TreeO(TreeO(self.a, copy=True).serialize())
        a["1 0 3 1"].sort()
        self.assertEqual(
            {"1": [[1, True, "a", ["f", ["a", "q"]]], {"a": False, "1": [1]}], "a": [[3, 4], {"b": 1}]},
            a(),
            "Removing tuples / sets in complex dict / list tree",
        )
        a = TreeO(default_node_type="l")
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
                    (IPv4Network, IPv6Network): TFunc(
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

    def test_count(self):
        self.assertEqual(4, TreeO.count(self.a, "1 0"), "Counting an existing list")
        self.assertEqual(2, TreeO.count(self.a, "1 1"), "Counting an existing dict")
        self.assertEqual(2, TreeO.count(self.a, "1 0 3 1"), "Counting an existing set")
        self.assertEqual(0, TreeO.count(self.a, "Hei god morgen"), "When the node doesn't exist, return 0")
        self.assertEqual(1, TreeO.count(self.a, "1 0 1"), "When the node is a simple value, return 1")

    def test_values(self):
        with open("test-data.json") as fp:
            a = TreeO(json.load(fp))
        self.assertEqual(tuple(a.values()), tuple(a.values()), "The same dict-values if the base node is a dict")
        b = [
            9922401,
            1385016682000,
            301,
            TreeO({"id": 301, "alias": "joxeankoret-c4", "name": "Joxeankoret (diff)"}),
            33,
            TreeO({"id": 33, "alias": "malware-server", "name": "Malware server"}),
            1385016663000,
            1385664000000,
            1,
            3,
            None,
            TreeO({"fqdn": "dlp.dlsofteclipse.com"}),
        ]
        self.assertEqual(b, a.values("data 4", return_node=True), "Returning correctly nodes in a dict, with TreeO's")
        b = (200, 10000, 0, 0, TreeO({}), TreeO([]), a.get("data", return_node=True), 10000)
        self.assertEqual(b, tuple(a.values(return_node=True)), "Correctly returning nodes in a dict")
        self.assertEqual((), a.values("data 12"), "Returning empty tuple for a path that doesn't exist")
        self.assertEqual((10000,), a.values("size"), "Singleton value is returned alone in a tuple")

    def test_mul(self):
        a = TreeO(self.a["1"])
        # print(1 * a)
        a = TreeO([3, 2, 1])
        b = TreeO([5, 4, 3])
        # print(a - 3)
        # b.get(1, krzpk=1, hanswurst=7)

    def test_copy(self):
        a = copy.deepcopy(self.a)
        b = TreeO(a, copy=True)
        self.assertEqual(a, b(), "Shallow-copy is actually equal to the original object if it isn't changed")
        b.pop("a")
        self.assertNotEqual(a, b(), "Can pop at base-level without affecting the original object")
        b = TreeO(a, copy=True)
        b["f"] = 2
        self.assertNotEqual(a, b(), "Can add at base-level without affecting the original object")
        b = TreeO(a).copy()
        b["1 0 0"] = 100
        self.assertNotEqual(a, b(), "Can change node deeply in the original object without affecting original object")
        b = TreeO(a, copy=True)
        b.pop("1 0 3")
        self.assertNotEqual(a, b(), "Can pop deeply in the object without affecting the original object")


if __name__ == "__main__":
    unittest.main()
