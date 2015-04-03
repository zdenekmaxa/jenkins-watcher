"""
Unittest base, shared stuff.

"""

import os
import datetime
import pytz

# sets up paths, do before any GAE or project specific imports
import setup

from google.appengine.ext import testbed

from mock import Mock

import contrib.jenkins
from contrib.jenkins import JenkinsInterface


# mock classes to simulate interaction with Jenkins

class Build(object):
    def get_duration(self):
        return "0:18:19.931000"

    def get_console(self):
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        console_file = "Selenium_Portal_MTV_development_sandbox-51-console.txt"
        f = open(os.path.join(data_dir, console_file), 'r')
        d = f.read()
        f.close()
        return d

    def get_timestamp(self):
        ts = datetime.datetime.now()
        return pytz.utc.localize(ts)


class Job(object):
    def is_running(self):
        return False

    def get_build_ids(self):
        return []

    def get_build(self, build_id):
        return Build()


class JenkinsMock(Mock):
    def get_queue(self):
        return []

    def get_job(self, name):
        return Job()


class TestBase(object):
    @classmethod
    def setup_class(cls):
        """
        Setup any state specific to the execution of the given module.

        """
        # replace jenkinsapi.jenkins.Jenkins class with a Mock class
        contrib.jenkins.Jenkins = JenkinsMock

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
        self.tasks = self.testbed.get_stub("taskqueue")
        self.mailer = self.testbed.get_stub("mail")
        self.jenkins = JenkinsInterface()
        self.jenkins.job_names = ("job_name_1", "job_name_2", "job_name_3")
        self.jenkins_url = "jenkins_url"


    def teardown_method(self, _):
        """
        Base method called always after the test case method was
        performed regardless of its result.

        """
        self.testbed.deactivate()