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

    def test_iter(self):
        a = TreeO(self.a, mod=False)
        aq = tuple(a["1 0 3 1"])  # have to create this tuple of the set because it's unpredictable what order
        # a and q will have in the set. Using this tuple, I make sure the test still works (the order will be sthe same)
        b = [('1', 0, 0, 1), ('1', 0, 1, True), ('1', 0, 2, 'a'), ('1', 0, 3, 0, 'f'), ('1', 0, 3, 1, aq[0]),
             ('1', 0, 3, 1, aq[1]), ('1', 1, 'a', False), ('1', 1, '1', 0, 1), ('a', 0, 0, 3), ('a', 0, 1, 4),
             ('a', 1, 'b', 1)]
        self.assertEqual([x for x in a], b, "Correctly iterating over dicts and lists")
        self.assertEqual([(0, 0, 3), (0, 1, 4), (1, "b", 1)], a.items("a"), "Correct iterator when path is given")

    def test_mod_function(self):
        a = TreeO(self.a, mod=False)
        b = copy.deepcopy(self.a)
        b["1"][0][0] += 4
        a.mod(lambda x: x + 4, "1 0 0", 6)
        self.assertEqual(a, b, "Modifying existing number")
        b["1"][0].insert(0, 2)
        a.mod(lambda x: x + 4, "1 0 0", 2, list_insert=2)
        self.assertEqual(a, b, "Setting default value")

    def test_mul(self):
        a = TreeO(self.a["1"])
        # print(1 * a)
        a = TreeO([3, 2, 1])
        b = TreeO([5, 4, 3])
        # print(a - 3)
        #b.get(1, krzpk=1, hanswurst=7)


if __name__ == '__main__':
    unittest.main()
