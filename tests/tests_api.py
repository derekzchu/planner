import os
import planner.views
import unittest
import tempfile

class FlaskTestCase(unittest.TestCase):

    def setUp(self):
        self.db_fd, planner.views.app.config['DATABASE'] = tempfile.mkstemp()
        self.app = planner.views.app.test_client()
        planner.models.init_db()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(planner.views.app.config['DATABASE'])

    def test_empty_db(self):
        rv = self.app.get('/inventory')
        print rv.data

if __name__ == '__main__':
    unittest.main()
