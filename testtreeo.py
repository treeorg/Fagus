import copy
import unittest

from treeo import TreeO
from copy import deepcopy


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
        b = [('1', 0, 0, 1), ('1', 0, 1, True), ('1', 0, 2, 'a'), ('1', 0, 3, 0, 'f'), ('1', 0, 3, 1, aq[0]),
             ('1', 0, 3, 1, aq[1]), ('1', 1, 'a', False), ('1', 1, '1', 0, 1), ('a', 0, 0, 3), ('a', 0, 1, 4),
             ('a', 1, 'b', 1)]
        self.assertEqual([x for x in a], b, "Correctly iterating over dicts and lists")
        self.assertEqual([(0, 0, 3), (0, 1, 4), (1, "b", 1)], a.items("a"), "Correct iterator when path is given")

    def test_set(self):
        a = TreeO(self.a, mod=False)
        b = copy.deepcopy(self.a)
        b["1"][0][1] = False
        self.assertEqual(b, TreeO.set(a, False, "1 0 1"), "Correctly traversing dicts and lists with numeric "
                                                          "indices when the node type is not given explicitly.")
        # verify that base object is writable for set
        self.assertRaisesRegex(ValueError, "Can't modify base object self having the immutable type ", TreeO.set,
                               (((1, 0), 2), 3), 7, "0 0 0")
        # new nodes can only either be lists or dicts, expressed by l's and
        self.assertRaisesRegex(ValueError, "The only allowed characters in .*", TreeO.set, a["1"], "f", "0", "pld")
        # Due to limitations on how references work in Python, the base-object can't be changed. So if the base-object
        # is a list, it can't be converted into a dict. These kind of changes are possible at the lower levels.
        self.assertRaisesRegex(ValueError, "Your base object is a (.*|see comment)", TreeO.set, a, "f", "0", "lld")
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
        self.assertEqual(a, b, "Add to list at beginning / end by using indexes higher than length / lower than - len"
                               "")

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
        self.assertEqual(a, b, "appending to set (converting to list first, both sets must be sorted for the test not "
                               "to fail)")
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
        self.assertEqual(a, b, "extending set (converting to list first, both sets must be sorted for the test not "
                               "to fail)")
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
        self.assertEqual(a, b, "extending set (converting to list first, both sets must be sorted for the test not "
                               "to fail)")
        b["1"][0][0] = [5, 1]
        self.assertEqual(TreeO.insert(a, -3, 5, "1 0 0"), b, "Creating list from singleton value and appending to it")
        b["q"] = [5]
        self.assertEqual(TreeO.insert(a, -9, 5, "q"), b, "Create new list for value at a path that didn't exist before")

    def test_add(self):
        a = TreeO(self.a, False)
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
        a = TreeO(self.a, False)
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
        b["k"]={"a": 1}
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

    def test_pop(self):
        a = TreeO(self.a, mod=False)
        b = copy.deepcopy(self.a)
        self.assertEqual(a.pop("1 0 3"), b["1"][0].pop(3), "Pop correctly drops the value at the position")
        self.assertEqual(a, b, "Pop has correctly modified the object")
        a.pop("8 9 10")
        self.assertEqual(a, b, "Pop did not modify the object as path doesn't exist")

    def test_serialize(self):
        pass

    def test_mul(self):
        a = TreeO(self.a["1"])
        # print(1 * a)
        a = TreeO([3, 2, 1])
        b = TreeO([5, 4, 3])
        # print(a - 3)
        #b.get(1, krzpk=1, hanswurst=7)


if __name__ == '__main__':
    unittest.main()
