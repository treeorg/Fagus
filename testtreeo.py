import copy
import json
import re
import unittest
from ipaddress import IPv6Address, IPv4Network, IPv6Network, ip_address
from treeo import TreeO, TFunc, TFilter, TCopy, TCheckFilter, TValueFilter
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
        TreeO.default_value = 7
        self.assertEqual(7, a["1 2 3"], "Returning default-value for class when unset for object")
        a.default_value = 3
        self.assertEqual(3, a["1 2 3"], "Returning default-value for object as it is now set")
        self.assertEqual(1, TreeO.get(self.a, ("1", 0, 0)), "Path existing, return value at path")
        self.assertEqual(1, a["1 0 0"], "Path existing, return value at path")
        self.assertIn("q", TreeO.get(self.a, ("1", 0, 3, 1)), "Path existing, return value at path")
        self.assertEqual(1, TreeO(self.a).get((1, 0, 0), 1), "Path not existing return default that comes from param")
        self.assertEqual(1, TreeO.get((((1, 0), 2), 3), "0 0 0"), "Successfully traversing tuples")
        del TreeO.default_value

    def test_iter(self):
        a = TreeO(self.a, copy=TCopy.SHALLOW)
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
        self.assertEqual([x for x in a.iter()], b, "Correctly iterating over dicts and lists")
        self.assertEqual([(0, 0, 3), (0, 1, 4), (1, "b", 1)], a.iter(-1, "a"), "Correct iterator when path is given")
        for i, l in enumerate(b):
            b[i] = (*l, *((None,) * (7 - len(l))))
        self.assertEqual(
            b, a.iter(7, iter_fill=None), "Correctly filling up when intended count in tuples is constant, here 7"
        )
        b = [
            ("1", 0, [1, True, "a", ("f", {"q", "a"})]),
            ("1", 1, {"a": False, "1": (1,)}),
            ("a", 0, [3, 4]),
            ("a", 1, {"b": 1}),
        ]
        self.assertEqual(b, a.iter(3), "Iterating correctly when max_items is limited to three")
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
        self.assertEqual(b, a.iter(5), "Iterating correctly when max_items is limited to five. Some tuples are < 5")
        self.assertEqual([(0, [3, 4]), (1, {"b": 1})], a.items("a"), "Items gives keys and values")
        b = [
            ("1", 0, TreeO([1, True, "a", ("f", {"q", "a"})])),
            ("1", 1, TreeO({"a": False, "1": (1,)})),
            ("a", 0, TreeO([3, 4])),
            ("a", 1, TreeO({"b": 1})),
        ]
        self.assertEqual(b, a.iter(3, return_node=True), "Returning nodes as TreeO-objects when return_value=True")
        self.assertTrue(
            all(isinstance(e, TreeO) for e in a.iter(3, return_node=True, reduce=-1)),
            "return_node actually returns back nodes if the nodes at the end are suitable to be converted",
        )
        self.assertEqual(
            a.iter(4, "", filter_=TFilter("a", 1, lambda x: x % 2 != 0, inexclude="---")),
            a.iter(4, "", filter_=TFilter("1", 0, lambda x: x % 2 == 0)),
            "Two opposite filters giving the same results on the data",
        )
        self.assertEqual(
            ["a"],
            a.iter(path=("1", 0, 3), filter_=TFilter(1, ..., "q", inexclude="++-"), reduce=-1),
            "Correctly filtering a set in the end",
        )
        self.assertEqual(
            [(3, [{"q"}])],
            a.iter(2, ("1", 0), TFilter(3, 1, ..., "q", inexclude="++-")),
            "Correctly putting a filtered last node in the end when combining filter_ and max_items",
        )
        with open("test-data.json") as fp:
            a = TreeO(json.load(fp))
        self.assertEqual(
            [(0, "source", "id", 889), (1, "source", "id", 5662), (4, "source", "id", 301)],
            a.iter(-1, "data", TFilter(..., "source", "id", lambda x: x > 300)),
            "Iterating over all source-ids that are > 300, testing lambda and true and default",
        )
        self.assertEqual(
            [2, 1, 3],
            a.iter(
                -1,
                "data",
                TFilter(
                    ...,
                    (TCheckFilter("source", "id", lambda x: x > 300), "state"),
                ),
                reduce=-1,
            ),
            "Getting the states for all sources who's id is > 300 using reduce and a check-filter",
        )
        self.assertEqual(
            [],
            a.iter(path="data", filter_=TFilter((TValueFilter(lambda x: len(x) < 1), ...))),
            "Verifying that a value-filter actually returns an empty list if its condition isn't met",
        )
        self.assertEqual(
            160,
            len(a.iter(path="data", filter_=TFilter((TValueFilter(lambda x: len(x) == 10), ...)))),
            "Verifying that a value-filter actually returns an empty list if its condition isn't met",
        )
        self.assertEqual(
            160,
            len(a.iter(filter_=TFilter("data", TValueFilter(lambda x: len(x) > 1)))),
            "Verifying that a value-filter also works if it comes as a standalone argument, then including all the "
            "subnodes the filter matches (in this case all).",
        )
        self.assertEqual(
            [],
            a.iter(filter_=TFilter("data", (TValueFilter(lambda x: len(x) < 1),))),
            "A value-filter actually returns an empty list even at the bottom if its condition isn't met",
        )
        self.assertEqual(
            160,
            len(a.iter(path="data", filter_=TFilter((TValueFilter(lambda x: len(x) > 1),)))),
            "If the only member in a tuple is TValue- and TCheck-filters and they're all removed, put ... at that"
            "argument to make sure these check-filters can match anything",
        )
        self.assertEqual(
            [(0, "role", "id", 182), (0, "role", "name", "Intel from sandbox runs"), (0, "state", 2)],
            a.iter(
                path="data",
                filter_=TFilter(
                    ...,
                    (
                        TCheckFilter(
                            (
                                TValueFilter(lambda x: len(x) == 3, lambda x: bool(x)),
                                TCheckFilter("alias", "file-analyzer-domain"),
                                "source",
                            ),
                            "id",
                            889,
                        ),
                        TFilter("state", 1, inexclude="+-"),
                        "role",
                    ),
                    "alias",
                    inexclude="++-",
                ),
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
        b = a.iter(
            filter_=TFilter("responseCode|limit|data", ..., ("role.*", re.compile("source.*")), string_as_re=True)
        )
        self.assertTrue(all(e in b for e in c), "Checking if it works to convert str to regex when requested")
        filter_args = ["a|c", ("abc", "a.*")]
        self.assertEqual(filter_args, TFilter(*filter_args).args, "No str args are changed if string_as_re=False")
        self.assertEqual(
            [re.compile(filter_args[0]), [filter_args[1][0], re.compile(filter_args[1][1])]],
            TFilter(*filter_args, string_as_re=True).args,
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
            a.iter(3, filter_=TFilter(({"responseCode", "limit", "offset"}, TFilter("data", 4, {"comment", "state"})))),
            "Using sets to accelerate filtering, both as a standalone argument and with other args in a tuple",
        )

    def test_filter(self):
        with open("test-data.json") as fp:
            a = TreeO(json.load(fp))
        self.assertEqual(
            {'responseCode': 200, 'limit': 10000, 'size': 10000},
            a.filter(TFilter({"responseCode", "limit", "size"}), copy=TCopy.SHALLOW),
            "Simplest ever filtering at base-level"
        )
        self.assertEqual(
            {'responseCode': 200, 'limit': 10000, 'offset': 0, 'count': 0, 'size': 10000},
            a.filter(TFilter("data", inexclude="-"), copy=TCopy.SHALLOW),
            "Using inexclude to turn around the filter and give everything except data at base-level"
        )


        # må få testa spesialtilfellene, men hva er det
        # inne i en sti
        # med og uten kopiering
        # invert filter både for value og checkfilter
        pass

    def test_set(self):
        a = TreeO(self.a, copy=TCopy.SHALLOW)
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
        a = TreeO(self.a, copy=TCopy.SHALLOW)
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
        self.assertRaisesRegex(TypeError, "TreeO can't set in a set.", TreeO({frozenset()}).set, 5, "1 3")
        self.assertRaisesRegex(TypeError, "TreeO can't set in a set.", TreeO(({"0": {5, 6}}, [4, 3])).set, 5, "0 0 0")

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

    def test_add(self):
        a = TreeO(self.a, copy=TCopy.SHALLOW)
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
        a = TreeO(self.a, copy=TCopy.SHALLOW)
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
        a = TreeO(self.a, copy=TCopy.SHALLOW)
        b = copy.deepcopy(self.a)
        self.assertEqual(a.setdefault("a 0 0", 5), 3, "Setdefault returns existing value")
        self.assertEqual(a(), b, "SetDefault doesn't change if the value is already there")
        self.assertEqual(a.setdefault("a 7 7", 5, "dll"), 5, "SetDefault returns default value")
        b["a"].append([5])
        self.assertEqual(a(), b, "SetDefault has added the value to the list")

    def test_mod_function(self):
        a = TreeO(self.a, copy=TCopy.SHALLOW)
        b = copy.deepcopy(self.a)
        b["1"][0][0] += 4
        a.mod(lambda x: x + 4, "1 0 0", 6)
        self.assertEqual(a(), b, "Modifying existing number")
        b["1"][0].insert(0, 2)
        a.mod(lambda x: x + 4, "1 0 0", 2, list_insert=2)
        self.assertEqual(a(), b, "Setting default value")

        def fancy_mod1(old_value):
            return old_value * 2

        b["1"][0][0] = fancy_mod1(b["1"][0][0])
        a.mod(fancy_mod1, "1 0 0")
        self.assertEqual(b, a(), "Using function pointer that works like a lambda - one param, one arg")
        b["1"][0][0] = fancy_mod1(b["1"][0][0])
        a.mod((fancy_mod1,), "1 0 0")
        self.assertEqual(b, a(), "Function pointer in tuple with only default param")

        def fancy_mod2(old_value, arg1, arg2, arg3, **kwargs):
            return sum([old_value, arg1, arg2, arg3, *kwargs.values()])

        b["1"][0][0] += 1 + 2 + 3 + 4 + 5
        a.mod(TFunc(fancy_mod2, 1, 1, 2, 3, kwarg1=4, kwarg2=5), "1 0 0")
        self.assertEqual(b, a(), "Complex function taking keyword-arguments and ordinary arguments")
        self.assertRaisesRegex(TypeError, "Valid types for mod_function: lambda", a.mod, (fancy_mod2, "hei"), "1 0 0")

    def test_pop(self):
        a = TreeO(self.a, copy=TCopy.SHALLOW)
        b = copy.deepcopy(self.a)
        self.assertEqual(a.pop("1 0 2"), b["1"][0].pop(2), "Pop correctly drops the value at the position")
        a.pop("8 9 10")
        self.assertEqual(a(), b, "Pop did not modify the object as path doesn't exist")
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

    def test_serialize(self):
        test_obj = {date(2021, 3, 6): [time(6, 45, 22), datetime(2021, 6, 23, 5, 45, 22)], ("hei", "du"): {3, 4, 5}}
        a = TreeO(test_obj, copy=TCopy.SHALLOW)
        self.assertRaisesRegex(
            TypeError,
            "Can't modify base-object self having the immutable type",
            TreeO((1, 2, 3, [4, 5, 6], {6, 5})).serialize,
        )
        self.assertRaisesRegex(
            ValueError, "Dicts with composite keys \\(tuples\\) are not supported in", a.serialize, copy=TCopy.SHALLOW
        )
        b = {"2021-03-06": ["06:45:22", "2021-06-23 05:45:22"], "hei du": [3, 4, 5]}
        self.assertEqual(a.serialize({"tuple_keys": lambda x: " ".join(x)}), b, "Serialized datetime and tuple-key")
        self.assertEqual(a.serialize(), b, "Nothing changes if there is nothing to change")
        a = TreeO(test_obj, copy=TCopy.SHALLOW)
        a[("hei du",)] = a.pop((("hei", "du"),))
        self.assertEqual(a.serialize(), b, "Also works when no mod-functions are defined in the parameter")
        a = TreeO(TreeO(self.a, copy=TCopy.SHALLOW).serialize())
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
            a.serialize(copy=TCopy.SHALLOW),
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
                copy=TCopy.SHALLOW,
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
        b = TreeO(a, copy=TCopy.SHALLOW)
        self.assertEqual(a, b(), "Shallow-copy is actually equal to the original object if it isn't changed")
        b.pop("a")
        self.assertNotEqual(a, b(), "Can pop at base-level without affecting the original object")
        b = TreeO(a, copy=TCopy.SHALLOW)
        b["f"] = 2
        self.assertNotEqual(a, b(), "Can add at base-level without affecting the original object")
        b = TreeO(a).copy()
        b["1 0 0"] = 100
        self.assertNotEqual(a, b(), "Can change node deeply in the original object without affecting original object")
        b = TreeO(a, copy=TCopy.SHALLOW)
        b.pop("1 0 3")
        self.assertNotEqual(a, b(), "Can pop deeply in the object without affecting the original object")


if __name__ == "__main__":
    unittest.main()
