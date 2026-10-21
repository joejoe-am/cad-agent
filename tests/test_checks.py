import unittest

from cad_agent.verification.reference import check_reference_pocket_vertices


class PocketChecks(unittest.TestCase):
    def setUp(self):
        self.outer = [(x, y, z) for x in (-0.05, 0.05) for y in (-0.03, 0.03) for z in (0.0, 0.01)]
        self.pocket = [(x, y, z) for x in (-0.02, 0.02) for y in (-0.01, 0.01) for z in (0.005, 0.01)]

    def test_correct(self):
        self.assertTrue(check_reference_pocket_vertices(self.outer + self.pocket))

    def test_shifted_pocket_with_same_volume(self):
        self.assertFalse(
            check_reference_pocket_vertices(self.outer + [(x + 0.001, y, z) for x, y, z in self.pocket])
        )

    def test_wrong_depth(self):
        self.assertFalse(
            check_reference_pocket_vertices(
                self.outer + [(x, y, 0.004 if z == 0.005 else z) for x, y, z in self.pocket]
            )
        )

    def test_missing_corner(self):
        self.assertFalse(check_reference_pocket_vertices((self.outer + self.pocket)[:-1]))


if __name__ == "__main__":
    unittest.main()
