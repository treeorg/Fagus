import copy
import unittest
from ipaddress import IPv6Address, IPv4Network, IPv6Network, ip_address
from treeo import TreeO, Funk
from datetime import datetime, date, time


class TestTreeO(unittest.TestCase):
    def setUp(self) -> None:
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

    def test_iter(self):
        a = TreeO(self.a, mod=False)
        aq = tuple(a["1 0 3 1"])  # have to create this tuple of the set because it's unpredictable what order
        # a and q will have in the set. Using this tuple, I make sure the test still works (the order will be sth same)
        b = [
            ("1", 0, 0, 1),
            ("1", 0, 1, True),
            ("1", 0, 2, "a"),
            ("1", 0, 3, 0, "f"),
            ("1", 0, 3, 1, aq[0]),
            ("1", 0, 3, 1, aq[1]),
            ("1", 1, "a", False),
            ("1", 1, "1", 0, 1),
            ("a", 0, 0, 3),
            ("a", 0, 1, 4),
            ("a", 1, "b", 1),
        ]
        self.assertEqual([x for x in a.iter()], b, "Correctly iterating over dicts and lists")
        self.assertEqual([(0, 0, 3), (0, 1, 4), (1, "b", 1)], a.iter(-1, "a"), "Correct iterator when path is given")
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

    def test_set(self):
        a = TreeO(self.a, mod=False)
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
            "Can't modify base object self having the immutable type ",
            TreeO.set,
            (((1, 0), 2), 3),
            7,
            "0 0 0",
        )
        # new nodes can only either be lists or dicts, expressed by l's and
        self.assertRaisesRegex(ValueError, "The only allowed characters in .*", TreeO.set, a["1"], "f", "0", "pld")
        # Due to limitations on how references work in Python, the base-object can't be changed. So if the base-object
        # is a list, it can't be converted into a dict. These kind of changes are possible at the lower levels.
        self.assertRaisesRegex(TypeError, "Your base object is a (.*|see comment)", TreeO.set, a, "f", "0", "lld")
        # if the user defines that he wants a list, but it's not possible to parse numeric index from t_path raise error
        self.assertRaisesRegex(ValueError, "Can't parse numeric list-index from.*", TreeO.set, a, "f", "1 f", "dl")
        a[("1", 1)] = "hei"
        b["1"][1] = "hei"
        self.assertEqual(b, a, "Using __set_item__ to set a value")
        a.value_split = "_"
        a.a_1_b = 2
        b["a"][1]["b"] = 2
        self.assertEqual(a, b, "Using another path separator and __setattr__")
        b["1"] = {"0": {"0": {"g": [9, 5]}}}
        self.assertEqual(b, a.set({"g": [9, 5]}, "1øæ0øæ0", "ddd", value_split="øæ"), "Replace list with dict")
        self.assertEqual([[["a"]]], TreeO.set([], "a", "1 1 1", default_node_type="l"), "Only create lists")
        a = TreeO(self.a, mod=False)
        b = copy.deepcopy(a())
        b["1"][0].insert(2, [["q"]])
        a.set("q", ("1", 0, 2, 0, 0), list_insert=2, default_node_type="l")
        self.assertEqual(a, b, "Insert into list")
        b["1"][0].append("hans")
        b["1"].insert(0, ["wurst"])
        a.default_node_type = "l"
        a.set("hans", "1 0 100")
        a.set("wurst", "1 -40 5")
        self.assertEqual(a, b, "Add to list at beginning / end by using indexes higher than length / lower than - len")

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
        a = TreeO(self.a, mod=False)
        b = copy.deepcopy(self.a)
        b["1"][0][3] = list(b["1"][0][3])
        b["1"][0][3][0] = {"f", "q"}
        a.add("q", "1 0 3 0")
        self.assertEqual(a, b, "Converting single value to set, adding value to it")
        b["1"][0][3][1].add("hans")
        a.add("hans", "1 0 3 1")
        self.assertEqual(a, b, "Adding value to existing set")
        b["a"][1]["c"] = {5}
        a.add(5, "a 1 c")
        self.assertEqual(a, b, "Creating new empty set at position where no value has been before")

    def test_update(self):
        # update set
        a = TreeO(self.a, mod=False)
        b = copy.deepcopy(self.a)
        b["1"][0][3] = list(b["1"][0][3])
        b["1"][0][3][0] = {"f", "q", "t", "p"}
        a.update("qtp", "1 0 3 0")
        self.assertEqual(a, b, "Converting single value to set, adding new values to it")
        b["1"][0][3][1].update("hans")
        a.update("hans", "1 0 3 1")
        self.assertEqual(a, b, "Adding new values to existing set")
        b["a"][1]["c"] = {5}
        a.add(5, "a 1 c")
        self.assertEqual(a, b, "Creating new empty set at position where no value has been before")
        # update dict
        b.update({"hei": 1, "du": "wurst"})
        a.update({"hei": 1, "du": "wurst"})
        self.assertEqual(a, b, "Updating base dict")
        b["a"][1].update({"hei": 1, "du": "wurst"})
        a.update({"hei": 1, "du": "wurst"}, "a 1")
        self.assertEqual(a, b, "Updating dict further inside the object")
        b["k"] = {"a": 1}
        a.update({"a": 1}, "k")
        self.assertEqual(a, b, "Updating dict at node that is not existing yet")
        self.assertRaisesRegex(ValueError, "Can't update dict with value of type .*", a.update, {"hans", "wu"}, "a 1")

    def test_setdefault(self):
        a = TreeO(self.a, mod=False)
        b = copy.deepcopy(self.a)
        self.assertEqual(a.setdefault(5, "a 0 0"), 3, "Setdefault returns existing value")
        self.assertEqual(a, b, "SetDefault doesn't change if the value is already there")
        self.assertEqual(a.setdefault(5, "a 7 7", "dll"), 5, "SetDefault returns default value")
        b["a"].append([5])
        self.assertEqual(a, b, "SetDefault has added the value to the list")

    def test_mod_function(self):
        a = TreeO(self.a, mod=False)
        b = copy.deepcopy(self.a)
        b["1"][0][0] += 4
        a.mod(lambda x: x + 4, "1 0 0", 6)
        self.assertEqual(a, b, "Modifying existing number")
        b["1"][0].insert(0, 2)
        a.mod(lambda x: x + 4, "1 0 0", 2, list_insert=2)
        self.assertEqual(a, b, "Setting default value")

        def fancy_mod1(old_value):
            return old_value * 2

        b["1"][0][0] = fancy_mod1(b["1"][0][0])
        a.mod(fancy_mod1, "1 0 0")
        self.assertEqual(b, a, "Using function pointer that works like a lambda - one param, one arg")
        b["1"][0][0] = fancy_mod1(b["1"][0][0])
        a.mod((fancy_mod1,), "1 0 0")
        self.assertEqual(b, a, "Function pointer in tuple with only default param")

        def fancy_mod2(old_value, arg1, arg2, arg3, **kwargs):
            return sum([old_value, arg1, arg2, arg3, *kwargs.values()])

        b["1"][0][0] += 1 + 2 + 3 + 4 + 5
        a.mod(Funk(fancy_mod2, 1, 1, 2, 3, kwarg1=4, kwarg2=5), "1 0 0")
        self.assertEqual(b, a, "Complex function taking keyword-arguments and ordinary arguments")
        self.assertRaisesRegex(TypeError, "Valid types for mod_function: lambda.*", a.mod, (fancy_mod2, "hei"), "1 0 0")

    def test_pop(self):
        a = TreeO(self.a, mod=False)
        b = copy.deepcopy(self.a)
        self.assertEqual(a.pop("1 0 3"), b["1"][0].pop(3), "Pop correctly drops the value at the position")
        self.assertEqual(a, b, "Pop has correctly modified the object")
        a.pop("8 9 10")
        self.assertEqual(a, b, "Pop did not modify the object as path doesn't exist")

    def test_serialize(self):
        test_obj = {date(2021, 3, 6): [time(6, 45, 22), datetime(2021, 6, 23, 5, 45, 22)], ("hei", "du"): {3, 4, 5}}
        a = TreeO(test_obj, mod=False)
        self.assertRaisesRegex(
            TypeError,
            "Can't modify base-object self having the immutable type.*",
            TreeO((1, 2, 3, [4, 5, 6], {6, 5})).serialize,
        )
        self.assertRaisesRegex(
            ValueError, "Dicts with composite keys \\(tuples\\) are not supported in.*", a.serialize, mod=False
        )
        b = {"2021-03-06": ["06:45:22", "2021-06-23 05:45:22"], "hei du": [3, 4, 5]}
        self.assertEqual(a.serialize({"tuple_keys": lambda x: " ".join(x)}), b, "Serialized datetime and tuple-key")
        self.assertEqual(a.serialize(), b, "Nothing changes if there is nothing to change")
        a = TreeO(test_obj, mod=False)
        a[("hei du",)] = a.pop((("hei", "du"),))
        self.assertEqual(a.serialize(), b, "Also works when no mod-functions are defined in the parameter")
        a = TreeO(TreeO(self.a, mod=False).serialize())
        a["1 0 3 1"].sort()
        self.assertEqual(
            {"1": [[1, True, "a", ["f", ["a", "q"]]], {"a": False, "1": [1]}], "a": [[3, 4], {"b": 1}]},
            a,
            "Removing tuples / sets in complex dict / list tree",
        )
        a = TreeO(default_node_type="l")
        a["a 1"] = ip_address("::1")
        a.append(ip_address("127.0.0.1"), "a 0")
        a["a -8"] = IPv4Network("192.168.178.0/24")
        a["a 6"] = IPv6Network("2001:0db8:85a3::/80")
        self.assertEqual(
            {"a": ["192.168.178.0/24", ["::1", "127.0.0.1"], "2001:db8:85a3::/80"]},
            a.serialize(mod=False),
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
                    (IPv4Network, IPv6Network): Funk(
                        fancy_network_mask,
                        1,
                        "The network %s with the netmask %s",
                        broadcast=" and the broadcast-address ",
                    ),
                },
                mod=False,
            ),
            "Complex mod-functions with function pointer, args, kwargs, lambdas and tuple-types, overriding default",
        )

    def test_count(self):
        self.assertEqual(4, TreeO.count(self.a, "1 0"), "Counting an existing list")
        self.assertEqual(2, TreeO.count(self.a, "1 1"), "Counting an existing dict")
        self.assertEqual(2, TreeO.count(self.a, "1 0 3 1"), "Counting an existing set")
        self.assertEqual(0, TreeO.count(self.a, "Hei god morgen"), "When the node doesn't exist, return 0")
        self.assertEqual(1, TreeO.count(self.a, "1 0 1"), "When the node is a simple value, return 1")

    def test_mul(self):
        a = TreeO(self.a["1"])
        # print(1 * a)
        a = TreeO([3, 2, 1])
        b = TreeO([5, 4, 3])
        # print(a - 3)
        # b.get(1, krzpk=1, hanswurst=7)


if __name__ == "__main__":
    unittest.main()
