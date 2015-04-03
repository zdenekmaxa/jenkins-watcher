"""
Unittests for jenkins-watcher, jenkins.py module.

"""

import os
import datetime

# sets up paths, do before any GAE or project specific imports
import setup

from google.appengine.ext import testbed, deferred
from google.appengine.api import memcache

from contrib.jenkins import JenkinsInterface, get_jenkins_instance, initialization
from contrib.models import OverviewModel, ActivitySummaryModel, BuildsStatisticsModel
from contrib.models import ACTIVITY_SUMMARY_MODEL_ID_KEY

from tests.base import TestBase, Build


class TestJenkins(TestBase):

    def test_initialization(self):
        initialization()
        d = ActivitySummaryModel.get_data()
        items = ('sent_emails_counter_total',
                 'stopped_builds_counter',
                 'sent_emails_counter',
                 'stopped_builds_counter_total',
                 'overview_update_counter_total',
                 'overview_update_counter')
        for i in items:
            assert d[i] == 0
        b = BuildsStatisticsModel.get_builds_data()
        assert b["num_builds"] == 0
        assert b["builds"] == {}

    def test_update_overview_check_running_builds(self):
        # put some data into datastore
        asm = ActivitySummaryModel(id=ACTIVITY_SUMMARY_MODEL_ID_KEY,
                                   overview_update_counter=72,
                                   sent_emails_counter=4,
                                   stopped_builds_counter=1,
                                   overview_update_counter_total=3448,
                                   sent_emails_counter_total=593,
                                   stopped_builds_counter_total=134)
        asm.put()
        self.jenkins.update_overview_check_running_builds()
        asm = ActivitySummaryModel.get_data()
        assert asm["overview_update_counter"] == 73
        assert asm["overview_update_counter_total"] == 3449

    def test_update_builds_stats(self):
        # since the mock classes return empty values, this method
        # is tested only partially
        self.jenkins.update_builds_stats()

    def test_process_console_output(self):
        correct_results = {
            "Selenium_Portal_MTV_development_sandbox-51-console.txt": {'failed': 1, 'skipped': 12, 'passed': 20, 'error': 0},
            "Selenium_Portal_MTV_development_sandbox-83-console.txt": {'failed': 0, 'skipped': 8, 'passed': 14, 'error': 11},
            "Selenium_Portal_MTV_master_public-1-console.txt": {'failed': 0, 'skipped': 10, 'passed': 25, 'error': 0},
            "Selenium_Portal_MTV_master_public-10-console.txt": {'failed': 1, 'skipped': 10, 'passed': 24, 'error': 0},
            "Selenium_Portal_MTV_master_sandbox-113-console.txt": {'failed': 1, 'skipped': 15, 'passed': 9, 'error': 8},
            "Selenium_Portal_MTV_topic_selenium_sandbox-309-console.txt": {'failed': 3, 'skipped': 5, 'passed': 25, 'error': 0},
            "Selenium_Portal_master_public-135-console.txt": None,
            "Selenium_Portal_master_public-150-console.txt": {'failed': 0, 'skipped': 5, 'passed': 28, 'error': 0},
            "Selenium_Portal_topic_selenium_public-330-console.txt": None,
            "Selenium_Portal_topic_selenium_public-339-console.txt": {'failed': 1, 'skipped': 5, 'passed': 27, 'error': 1},
            "Selenium_Portal_topic_selenium_public-346-console.txt": {'failed': 6, 'skipped': 5, 'passed': 22, 'error': 0},
            "Selenium_Portal_topic_selenium_public-364-console.txt": {'failed': 1, 'skipped': 5, 'passed': 27, 'error': 1},
            "Selenium_Portal_topic_selenium_public-371-console.txt": {'failed': 0, 'skipped': 5, 'passed': 28, 'error': 0}
        }
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        for console in os.listdir(data_dir):
            f = open(os.path.join(data_dir, console), 'r')
            r = self.jenkins.process_console_output(f.read())
            f.close()
            assert correct_results[console] == r

    def test_process_build_info_and_store(self):
        self.jenkins.process_build_info_and_store(build=Build(),
                                                  job_name="Selenium_Portal_MTV_development_sandbox",
                                                  timestamp=datetime.datetime.now(),
                                                  build_id=51,
                                                  status="FAILED")
        builds = BuildsStatisticsModel.get_builds_data()
        assert builds["num_builds"]
        assert len(builds["builds"]["Selenium_Portal_MTV_development_sandbox"]) == 1
        assert builds["builds"]["Selenium_Portal_MTV_development_sandbox"][0]["status"] == "FAILED"
        assert builds["builds"]["Selenium_Portal_MTV_development_sandbox"][0]["build_id"] == 51
        assert builds["builds"]["Selenium_Portal_MTV_development_sandbox"][0]["duration"] == "0:18:19"
        assert builds["builds"]["Selenium_Portal_MTV_development_sandbox"][0]["failed"] == 1
        assert builds["builds"]["Selenium_Portal_MTV_development_sandbox"][0]["skipped"] == 12
        assert builds["builds"]["Selenium_Portal_MTV_development_sandbox"][0]["passed"] == 20
        assert builds["builds"]["Selenium_Portal_MTV_development_sandbox"][0]["error"] == 0

    def test_check_running_build(self):
        self.jenkins.check_running_build(job_name="Selenium_Portal_MTV_development_sandbox",
                                         current_build_id=66)