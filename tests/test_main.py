"""
Simple high-level tests for stuff called from the main.py module.

"""

import pprint

# sets up paths, do before any GAE or project specific imports
import setup

from contrib.jenkins import JenkinsInterface, get_jenkins_instance, initialization
from contrib.models import OverviewModel, ActivitySummaryModel, BuildsStatisticsModel
from contrib.models import ACTIVITY_SUMMARY_MODEL_ID_KEY
from contrib.utils import send_email

from tests.base import TestBase


class TestMain(TestBase):

    def test_get_overview_data(self):
        resp = OverviewModel.get_overview_data()
        assert isinstance(resp, dict)
        assert "current_time" in resp

    def test_initialization(self):
        initialization()

    def test_send_activity_summary_no_data(self):
        data = ActivitySummaryModel.get_data()
        formatted_data = pprint.pformat(data)
        send_email(subject="activity summary",
                   body="activity summary: " + "\n\n" + formatted_data)
        # reset wil fail, there is no data
        # ActivitySummaryModel.reset()

    def test_send_activity_summary(self):
        # put some data into datastore
        ActivitySummaryModel(id=ACTIVITY_SUMMARY_MODEL_ID_KEY).put()
        data = ActivitySummaryModel.get_data()
        formatted_data = pprint.pformat(data)
        send_email(subject="activity summary",
                   body="activity summary: " + "\n\n" + formatted_data)
        ActivitySummaryModel.reset()

    def test_update_overview_check_running_builds(self):
        ActivitySummaryModel(id=ACTIVITY_SUMMARY_MODEL_ID_KEY).put()
        get_jenkins_instance().update_overview_check_running_builds()

    def test_update_builds(self):
        asm = ActivitySummaryModel(id=ACTIVITY_SUMMARY_MODEL_ID_KEY)
        asm.put()
        get_jenkins_instance().update_builds_stats()

    def test_get_builds_stats(self):
        BuildsStatisticsModel.get_builds_data(days_limit=1)