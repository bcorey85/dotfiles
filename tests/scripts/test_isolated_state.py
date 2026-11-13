import os
import sys
import unittest
import unittest.mock

import isolated_state
import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import reviewed_tree


class IsolatedStateTest(unittest.TestCase):
    def test_the_review_gate_folder_lies_under_the_temp_home_and_the_environment_is_restored(self):
        real_home = os.environ["HOME"]
        probe = unittest.TestCase()
        home = isolated_state.isolate_state_root(probe)
        self.assertEqual(os.environ["HOME"], str(home))
        self.assertTrue(reviewed_tree.review_gate_dir().is_relative_to(home))
        probe.doCleanups()
        self.assertEqual(os.environ["HOME"], real_home)
        self.assertFalse(home.exists())

    def test_a_state_folder_variable_set_outside_the_test_is_dropped_and_comes_back(self):
        with unittest.mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": "/real/store"}):
            probe = unittest.TestCase()
            isolated_state.isolate_state_root(probe)
            self.assertNotIn("HANDBACK_STORE_DIR", os.environ)
            probe.doCleanups()
            self.assertEqual(os.environ["HANDBACK_STORE_DIR"], "/real/store")


if __name__ == "__main__":
    unittest.main()
