"""
Jenkins CI server interface file.

"""


import sys
import time
import datetime
import json
import pprint
import logging as log
import pytz

from google.appengine.ext import ndb

from jenkinsapi.jenkins import Jenkins
from jenkinsapi.custom_exceptions import NoBuildData

from config import user_name, access_token, job_names, jenkins_url
from utils import get_localized_timestamp_str, get_current_timestamp_str
from utils import send_email, exception_catcher


class DataOverview(ndb.Model):
    data = ndb.JsonProperty(required=True)


class ActivitySummary(ndb.Model):
    summary_id_key = 1
    overview_update_counter_total = ndb.IntegerProperty(default=0)
    # since last summary email
    overview_update_counter = ndb.IntegerProperty(default=0)
    sent_emails_counter_total = ndb.IntegerProperty(default=0)
    # since last summary email
    sent_emails_counter = ndb.IntegerProperty(default=0)
    stopped_builds_counter_total = ndb.IntegerProperty(default=0)

    @staticmethod
    @ndb.transactional()
    def reset():
        data = ActivitySummary.get_by_id(ActivitySummary.summary_id_key)
        data.overview_update_counter = 0
        data.sent_emails_counter = 0
        data.put()

    @staticmethod
    @ndb.transactional()
    def increase_overview_update_counter():
        data = ActivitySummary.get_by_id(ActivitySummary.summary_id_key)
        data.overview_update_counter += 1
        data.overview_update_counter_total += 1
        data.put()

    @staticmethod
    @ndb.transactional()
    def increase_sent_emails_counter():
        data = ActivitySummary.get_by_id(ActivitySummary.summary_id_key)
        data.sent_emails_counter += 1
        data.sent_emails_counter_total += 1
        data.put()

    @staticmethod
    @ndb.transactional()
    def increase_stopped_builds_counter():
        data = ActivitySummary.get_by_id(ActivitySummary.summary_id_key)
        data.stopped_builds_counter_total += 1
        data.put()

    @staticmethod
    @ndb.transactional()
    def get_data():
        data = ActivitySummary.get_by_id(ActivitySummary.summary_id_key)
        r = dict(overview_update_counter_total=data.overview_update_counter_total,
                 overview_update_counter=data.overview_update_counter,
                 sent_emails_counter_total=data.sent_emails_counter_total,
                 sent_emails_counter=data.sent_emails_counter,
                 stopped_builds_counter_total=data.stopped_builds_counter_total)
        return r


class JenkinsInterface(object):

    overview_id_key = 1
    # 30mins - email will be send
    current_build_duration_threshold_soft = 30  # minutes
    # 50mins - the build is really getting canceled
    current_build_duration_threshold_hard = 50  # minutes

    def __init__(self,
                 jenkins_url=None,
                 user_name=None,
                 access_token=None,
                 job_names=None):
        self.jenkins_url = jenkins_url
        self.user_name = user_name
        # jenkins job names we're concerned about
        self.job_names = job_names
        self.server = Jenkins(jenkins_url, username=user_name, password=access_token)
        # doesn't seem to have any effect, in order to remove HTTP connection
        # problem had to patch jenkinsapi adn requests (timeout and max retries)
        self.server.RETRY_ATTEMPTS = 5

    def get_total_queued_jobs(self):
        return len(self.server.get_queue())

    def check_running_builds(self,
                             job_name=None,
                             build=None,
                             build_timestamp=None,
                             current_build_id=-1):
        """
        Check duration of the build build.
        Dictionary resp is updated about actions performed in this method.

        """
        resp = {}
        console_url = "%s/job/%s/%s/console" % (self.jenkins_url, job_name, current_build_id)
        now = datetime.datetime.utcnow()  # there is no timezone info, putting UTC
        duration = pytz.utc.localize(now) - build_timestamp
        duration_str = str(duration).split('.')[0]
        resp["duration"] = duration_str
        resp["stop_threshold_minutes"] = self.current_build_duration_threshold_hard
        resp["email_notification"] = False
        if duration.total_seconds() > self.current_build_duration_threshold_hard * 60:
            ret = build.stop()
            ActivitySummary.increase_stopped_builds_counter()
            time.sleep(10)
            status = build.get_status()
            msg = (("Build '%s' has been running for more than %s minutes.\n"
                    "duration: %s\nconsole output: %s\nstopping ... current status: %s") %
                    (build,
                     self.current_build_duration_threshold_hard,
                     duration_str,
                     console_url,
                     status))
            resp["stop_call_response"] = ret
            resp["current_status"] = status
            resp["email_notification"] = True

        if duration.total_seconds() > self.current_build_duration_threshold_soft * 60:
            msg = (("Build '%s' has been running for more than %s minutes.\n"
                    "duration: %s\nconsole output: %s\n[soft threshold, no action taken]") %
                    (build,
                     self.current_build_duration_threshold_soft,
                     duration_str,
                     console_url))
            resp["email_notification"] = True

        if resp["email_notification"]:
            log.warn(msg)
            formatted_data = pprint.pformat(resp)
            log.debug(formatted_data)
            subject = "too long build %s" % build
            result = send_email(subject=subject, body=msg + "\n\n" + formatted_data)
            if result:
                ActivitySummary.increase_sent_emails_counter()

        return resp

    def get_running_jobs_info(self):
        resp = []
        for job_name in self.job_names:
            log.info("Checking '%s' job ..." % job_name)
            job = self.server.get_job(job_name)
            if job.is_running():
                r = dict()
                log.info("'%s' job is running." % job_name)
                r["job_name"] = job_name
                last_build_id = job.get_last_buildnumber()
                r["last_build_id"] = last_build_id
                build = job.get_build(last_build_id)
                # get_timestamp returns this type of data, is in UTC:
                # datetime.datetime(2015, 3, 3, 19, 41, 56, tzinfo=<UTC>) (is not JSON serializable)
                ts = build.get_timestamp()
                r["start_timestamp"] = get_localized_timestamp_str(ts)
                result = self.check_running_builds(job_name=job_name,
                                                   build=build,
                                                   build_timestamp=ts,
                                                   current_build_id=last_build_id)
                r.update(result)
                resp.append(r)
        return resp

    @ndb.transactional()
    def _update_data_store(self, data):
        # just the update has to be separated from the refresh method,
        # the transaction fails there since it takes too long
        overview = DataOverview(id=self.overview_id_key, data=data)
        overview.put()

    @exception_catcher
    def refresh_overview_data(self):
        log.info("Start refresh overview data task: '%s'" % get_current_timestamp_str())
        data = dict(total_queued_jobs=self.get_total_queued_jobs(),
                    running_jobs=self.get_running_jobs_info())
        data["data_retrieved_at"] = get_current_timestamp_str()
        self._update_data_store(data)
        data_formatted = pprint.pformat(data)
        log.debug("Data updated under key id: '%s'\n%s" % (self.overview_id_key, data_formatted))
        ActivitySummary.increase_overview_update_counter()
        log.debug("Finished refresh overview data task: '%s'" % get_current_timestamp_str())

    @staticmethod
    @ndb.transactional()
    def get_overview_data():
        overview = DataOverview.get_by_id(JenkinsInterface.overview_id_key)
        # is already a Python object
        return overview.data


def get_jenkins_interface():
    jenkins = JenkinsInterface(jenkins_url=jenkins_url,
                               user_name=user_name,
                               access_token=access_token,
                               job_names=job_names)
    return jenkins


def refresh():
    jenkins_iface = get_jenkins_interface()
    jenkins_iface.refresh_overview_data()