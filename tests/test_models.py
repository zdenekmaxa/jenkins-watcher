"""
Unittests for data models classes.

"""

# sets up paths, do before any GAE or project specific imports
import setup

import datetime

from google.appengine.ext import testbed
from google.appengine.api import memcache

from contrib.jenkins import JenkinsInterface, get_jenkins_instance, initialization
from contrib.models import OverviewModel, ActivitySummaryModel, BuildsStatisticsModel
from contrib.models import ACTIVITY_SUMMARY_MODEL_ID_KEY

from tests.base import TestBase
from tests.base import Build

class TestModels(TestBase):

    def test_overview_model(self):
       d = {"total_queued_jobs": 3, "current_time": "2015-04-03 21:15:19", "running_jobs":
            [{"email_notification": False, "start_timestamp": "2015-04-03 20:54:43",
              "stop_threshold_minutes": 60, "retrieved_at": "2015-04-03 21:06:09",
              "last_build_id": 327, "duration": "0:11:26", "job_name": "Selenium_Portal_master_public"},
              {"email_notification": False, "start_timestamp": "2015-04-03 21:03:35",
               "stop_threshold_minutes": 60, "retrieved_at": "2015-04-03 21:06:23",
               "last_build_id": 301,
               "duration": "0:02:48", "job_name": "Selenium_Portal_MTV_staging_sandbox"}]}
       OverviewModel.update_overview_data(d)
       data = OverviewModel.get_overview_data()
       assert len(data["running_jobs"]) == 2
       assert data["total_queued_jobs"] == 3

    def test_activity_summary_model(self):
        asm = ActivitySummaryModel(id=ACTIVITY_SUMMARY_MODEL_ID_KEY,
                                   overview_update_counter=72,
                                   sent_emails_counter=4,
                                   stopped_builds_counter=1,
                                   overview_update_counter_total=3448,
                                   sent_emails_counter_total=593,
                                   stopped_builds_counter_total=134,
                                   builds_stats_update_counter=65,
                                   builds_stats_update_counter_total=165)
        asm.put()
        ActivitySummaryModel.reset()
        asm = ActivitySummaryModel.get_data()
        assert asm["overview_update_counter"] == 0
        assert asm["sent_emails_counter"] == 0
        assert asm["builds_stats_update_counter"] == 0
        assert asm["overview_update_counter_total"] == 3448
        assert asm["stopped_builds_counter_total"] == 134
        assert asm["builds_stats_update_counter_total"] == 165

        ActivitySummaryModel.increase_counters(which_counters=["overview_update_counter"])

        asm = ActivitySummaryModel.get_data()
        assert asm["overview_update_counter"] == 1
        assert asm["overview_update_counter_total"] == 3449

        ActivitySummaryModel.increase_counters(which_counters=["sent_emails_counter",
                                                               "stopped_builds_counter",
                                                               "builds_stats_update_counter"])
        asm = ActivitySummaryModel.get_data()
        assert asm["sent_emails_counter"] == 1
        assert asm["sent_emails_counter_total"] == 594
        assert asm["stopped_builds_counter_total"] == 135
        assert asm["stopped_builds_counter"] == 1
        assert asm["builds_stats_update_counter_total"] == 166
        assert asm["builds_stats_update_counter"] == 1

    def test_builds_statistics_model_get_builds_data(self):
        initialization()
        b = BuildsStatisticsModel.get_builds_data()
        assert len(b["builds"]) == 0
        assert b["num_builds"] == 0

    def test_builds_statistics_model_correct_order(self):
        """
        The data are sorted according to the key which is constructed
        as follows:
        job_name-build_id

        Later on datastore retrieval, build id 99 comes after 100, which
        is wrong.

        """
        def store_build(job_name, build_id):
            # just helper mock object
            build = Build()
            key_id = BuildsStatisticsModel.construct_datastore_key_id(job_name, build_id)
            builds_stats = BuildsStatisticsModel(id=key_id,
                                                 name=job_name,
                                                 bid=build_id,
                                                 ts=build.get_timestamp().replace(tzinfo=None))
            builds_stats.put()

        initialization()
        job_name = "Selenium_Portal_MTV_topic_selenium_sandbox"
        # store one build
        build_id = 99
        store_build(job_name, build_id)
        # store another build
        build_id = 100
        store_build(job_name, build_id)
        # retrieve
        data = BuildsStatisticsModel.get_builds_data()
        # since the build go on the page in reverse order
        # builds[job_name][0].build_id 100 must be
        # before build_id 99
        assert data["builds"][job_name][0]["build_id"] == 100
        assert data["builds"][job_name][1]["build_id"] == 99