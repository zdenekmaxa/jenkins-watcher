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
import re

from google.appengine.ext import ndb

from jenkinsapi.jenkins import Jenkins
from jenkinsapi.custom_exceptions import NoBuildData

from config import user_name, access_token, job_names, jenkins_url
from utils import get_localized_timestamp_str, get_localized_timestamp, get_current_timestamp_str
from utils import send_email, exception_catcher


# console output processing compiled regular expression patterns
# example lines to search for:
# =================== 28 passed, 5 skipped in 1078.49 seconds ====================
# ========== 1 failed, 27 passed, 5 skipped, 1 error in 996.52 seconds ===========
# don't do passed|failed|skipped - matches something else
first_iter_patterns = (re.compile("=+ .*[0-9]+ passed.* in .* seconds =+"),
                       re.compile("=+ .*[0-9]+ failed.* in .* seconds =+"),
                       re.compile("=+ .*[0-9]+ skipped.* in .* seconds =+"))
second_iter_patterns = ((re.compile("[0-9]+ passed"), "passed"),
                        (re.compile("[0-9]+ failed"), "failed"),
                        (re.compile("[0-9]+ skipped"), "skipped"),
                        (re.compile("[0-9]+ error"), "error"))


class DataOverview(ndb.Model):
    data = ndb.JsonProperty(required=True)


class ActivitySummary(ndb.Model):
    summary_id_key = 1
    # since last summary email
    overview_update_counter = ndb.IntegerProperty(default=0)
    sent_emails_counter = ndb.IntegerProperty(default=0)
    stopped_builds_counter = ndb.IntegerProperty(default=0)
    # total
    overview_update_counter_total = ndb.IntegerProperty(default=0)
    sent_emails_counter_total = ndb.IntegerProperty(default=0)
    stopped_builds_counter_total = ndb.IntegerProperty(default=0)

    @staticmethod
    @ndb.transactional()
    def reset():
        data = ActivitySummary.get_by_id(ActivitySummary.summary_id_key)
        data.overview_update_counter = 0
        data.sent_emails_counter = 0
        data.stopped_builds_counter = 0
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
        data.stopped_builds_counter += 1
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
                 stopped_builds_counter=data.stopped_builds_counter,
                 stopped_builds_counter_total=data.stopped_builds_counter_total)
        return r


class BuildsStatistics(ndb.Model):
    # key id will be job name (i.e. jenkins project name) + build id: 'build_name-build_id'
    name = ndb.StringProperty(default="")
    bid = ndb.IntegerProperty(default=0)
    status = ndb.StringProperty(default="")
    # time stamp of start of the build
    # DatetimeProperty ts can only support UTC.
    # NDB can only store UTC but no timezone specified (naive)
    ts = ndb.DateTimeProperty()
    duration = ndb.StringProperty(default="")
    # test cases counters
    passed = ndb.IntegerProperty(default=0)
    failed = ndb.IntegerProperty(default=0)
    skipped = ndb.IntegerProperty(default=0)
    error = ndb.IntegerProperty(default=0)


class JenkinsInterface(object):

    overview_id_key = 1
    # 30mins - email will be send
    current_build_duration_threshold_soft = 30  # minutes
    # 60mins - the build is really getting canceled
    current_build_duration_threshold_hard = 60  # minutes
    # wait this timeout when stopping a build
    stop_build_timeout = 1  # minute
    # builds statistics history, go back this history on builds init
    builds_history_init_limit = 1 * 24 * 60  # 2 days in minutes

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

    def stop_running_build(self, build=None):
        stop_call_response = build.stop()
        for _ in range((self.stop_running_build * 60) / 10):
            time.sleep(self.stop_running_build * 10)
            status = build.get_status()
            if status == "ABORTED":
                ActivitySummary.increase_stopped_builds_counter()
                break
        else:
            status = "%s - after 1 minute, should be ABORTED"
        return stop_call_response, status

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
            stop_call_response, status = self.stop_running_build(build)
            msg = (("Build '%s' has been running for more than %s minutes.\n"
                    "duration: %s\nconsole output: %s\nstopping ... current status: %s") %
                    (build,
                     self.current_build_duration_threshold_hard,
                     duration_str,
                     console_url,
                     status))
            resp["stop_call_response"] = stop_call_response
            resp["current_status"] = status
            resp["email_notification"] = True
        elif duration.total_seconds() > self.current_build_duration_threshold_soft * 60:
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
            subject = "long #%s %s" % (current_build_id, job_name)
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
    def update_overview(self):
        log.info("Start update_overview data task: '%s'" % get_current_timestamp_str())
        data = dict(total_queued_jobs=self.get_total_queued_jobs(),
                    running_jobs=self.get_running_jobs_info())
        data["data_retrieved_at"] = get_current_timestamp_str()
        self._update_data_store(data)
        data_formatted = pprint.pformat(data)
        log.debug("Data updated under key id: '%s'\n%s" % (self.overview_id_key, data_formatted))
        ActivitySummary.increase_overview_update_counter()
        log.info("Finished update_overview data task: '%s'" % get_current_timestamp_str())

    @staticmethod
    @ndb.transactional()
    def get_overview_data():
        overview = DataOverview.get_by_id(JenkinsInterface.overview_id_key)
        # is already a Python object
        return overview.data

    @exception_catcher
    def builds_stats_init(self):
        """
        Build is one running test suite on jenkins for a given
        job type (project type)
        iterate over projects and retrieve info on all builds
        going back to history

        """
        log.info("Start builds_stats_init task: '%s'" % get_current_timestamp_str())
        # there is no timezone info, putting UTC
        limit = self.builds_history_init_limit * 60  # get seconds from minutes
        utc_now = pytz.utc.localize(datetime.datetime.utcnow())
        for job_name in self.job_names:
            job = self.server.get_job(job_name)
            # returns iterator of available build id numbers in
            # reverse order, most recent first
            bids = job.get_build_ids()
            count = 0
            for bid in bids:
                count += 1
                if count == 1:
                    # not interested in the very last one, may be running
                    continue
                log.debug("Retrieving data on %s #%s (counter: %s) ..." % (job_name, bid, count))
                b = job.get_build(bid)
                ts = b.get_timestamp()
                if (utc_now - ts).total_seconds() > limit:
                    # not interested in builds older than history limit
                    break
                status = b.get_status()
                # get rid of decimal point 0:18:19.931000 at build duration
                duration = str(b.get_duration()).split('.')[0]
                # TODO
                # extract this for reuse - this store part
                console_output = b.get_console()
                result = self.process_console_output(console_output)
                key_id = "%s-%s" % (job_name, bid)
                builds_stats = BuildsStatistics(id=key_id,
                                                name=job_name,
                                                bid=bid,
                                                status=status,
                                                # naive datetime (no timezone)
                                                ts=ts.replace(tzinfo=None),
                                                duration=duration)
                if result:
                    for item in ("passed", "failed", "skipped", "error"):
                        setattr(builds_stats, item, result[item])
                log.debug("Storing %s ..." % builds_stats)
                builds_stats.put()
        log.info("Finished builds_stats_init task: '%s'" % get_current_timestamp_str())

    def process_console_output(self, console_output):
        """
        Process Jenkins job console output.
        Iterate over the first type patterns to identify the result status line.
        The iterate over the second pass expressions to derive
        number of passed, skipped, failed and error test cases.

        """
        for cp in first_iter_patterns:
            result_line = cp.findall(console_output)
            if result_line:
                assert len(result_line) == 1
                # get  1) passed  2) failed  3) skipped  4) error  5) duration
                result = {}
                for cp2, what in second_iter_patterns:
                    result_item = cp2.findall(result_line[0])
                    if result_item:
                        assert len(result_item) == 1
                        item_num = int(result_item[0].replace(" %s" % what, ''))
                        result[what] = item_num
                    else:
                        result[what] = 0
                break
            else:
                result = None
        return result

    def update_builds_stats(self):
        log.info("Start update_builds_stats task: '%s'" % get_current_timestamp_str())
        for job_name in self.job_names:
            job = self.server.get_job(job_name)
            # returns iterator of available build id numbers in
            # reverse order, most recent first
            bids = job.get_build_ids()
            for bid in bids:
                log.debug("Retrieving data on %s #%s ..." % (job_name, bid))
                b = job.get_build(bid)
                status = b.get_status()
                if not status:
                    log.debug("%s #%s has not finished, status: %s, going to "
                              "another build ..." % (job_name, bid, status))
                    continue
                # this build considered finished now
                # check if we have not hit a build which is already stored
                key_id = "%s-%s" % (job_name, bid)
                if BuildsStatistics.get_by_id(key_id) is not None:
                    log.debug("%s #%s is already stored, going to the "
                              "next job type ..." % (job_name, bid))
                    break
                ts = b.get_timestamp()
                # get rid of decimal point 0:18:19.931000 at build duration
                duration = str(b.get_duration()).split('.')[0]
                console_output = b.get_console()
                result = self.process_console_output(console_output)
                # TODO
                # extract this for reuse - this store part
                builds_stats = BuildsStatistics(id=key_id,
                                                name=job_name,
                                                bid=bid,
                                                status=status,
                                                # naive datetime (no timezone)
                                                ts=ts.replace(tzinfo=None),
                                                duration=duration)
                if result:
                    for item in ("passed", "failed", "skipped", "error"):
                        setattr(builds_stats, item, result[item])
                log.debug("Storing %s ..." % builds_stats)
                builds_stats.put()
        log.info("Finished update_builds_stats task: '%s'" % get_current_timestamp_str())


def get_jenkins_interface():
    jenkins = JenkinsInterface(jenkins_url=jenkins_url,
                               user_name=user_name,
                               access_token=access_token,
                               job_names=job_names)
    return jenkins


def update_overview():
    get_jenkins_interface().update_overview()

def update_builds_stats():
    get_jenkins_interface().update_builds_stats()

def builds_stats_init():
    get_jenkins_interface().builds_stats_init()