"""
Unittests for jenkins-watcher, jenkins.py module.

"""

import os
import sys

# sets up paths, do before any GAE or project specific imports
import setup

from google.appengine.ext import testbed, deferred
from google.appengine.api import memcache

from contrib.jenkins import JenkinsInterface


class TestBase(object):
    pass


class TestJenkins(TestBase):

    @classmethod
    def setup_class(cls):
        """
        Setup any state specific to the execution of the given module.

        """
        pass

    def setup_method(self, method):
        """
        Base method called before every test case method is called.

        """
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_memcache_stub()
        self.testbed.init_mail_stub()
        self.testbed.init_taskqueue_stub()
        self.tasks = self.testbed.get_stub('taskqueue')
        self.mailer = self.testbed.get_stub('mail')

    def teardown_method(self, _):
        """
        Base method called always after the test case method was
        performed regardless of its result.

        """
        pass

    def test_get_overview_data(self):
        resp = JenkinsInterface.get_overview_data()
        # TODO
        # check type
        # check some content attributes
        print resp

    def test_initialization(self):
        # msg = initialization()
        # TODO
        # check the message
        # check the datastore
        # this may need to be done on setup_method level
        # with fake data to inialize with (builds stats)
        # this is probably silly to test this directly
        pass

    def test_activity_summary(self):
        # TODO
        # test get, reset, values, all API
        # ActivitySummary.get_data()
        # resp = ActivitySummary.get_data()
        # ActivitySummary.reset()
        pass

    def test_upate_overview(self):
        # get_jenkins_instance().update_overview_check_running_builds
        pass

    def test_update_builds(self):
        # get_jenkins_instance().update_builds_stats
        pass

    def test_get_builds_stats(self):
        # resp = BuildsStatistics.get_builds_data(days_limit=days_limit)
        pass

    def test_send_activity_summary(self):
        # possible with GAE mockup email thing
        pass