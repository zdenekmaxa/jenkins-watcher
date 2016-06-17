"""
Jenkins CI server interface file.

"""


import time
import datetime
import pprint
import logging as log
import re

import pytz
from jenkinsapi.jenkins import Jenkins
from jenkinsapi.custom_exceptions import UnknownJob

from google.appengine.ext import deferred
from google.appengine.api import memcache

from config import user_name, access_token, job_names, jenkins_url
from contrib.utils import get_localized_timestamp_str, get_current_timestamp_str
from contrib.utils import send_email
from contrib.models import OverviewModel, ActivitySummaryModel, BuildsStatisticsModel
from contrib.models import ACTIVITY_SUMMARY_MODEL_ID_KEY, MEMCACHE_BUILDS_KEY


# console output processing compiled regular expression patterns
# example lines to search for:
# =================== 28 passed, 5 skipped in 1078.49 seconds ====================
# ========== 1 failed, 27 passed, 5 skipped, 1 error in 996.52 seconds ===========
# don't do passed|failed|skipped - matches something else
FIRST_ITERATION_PATTERNS = (re.compile("=+ .*[0-9]+ passed.* in .* seconds =+"),
                            re.compile("=+ .*[0-9]+ failed.* in .* seconds =+"),
                            re.compile("=+ .*[0-9]+ skipped.* in .* seconds =+"))
SECOND_ITERATION_PATTERNS = ((re.compile("[0-9]+ passed"), "passed"),
                             (re.compile("[0-9]+ failed"), "failed"),
                             (re.compile("[0-9]+ skipped"), "skipped"),
                             (re.compile("[0-9]+ error"), "error"))


class JenkinsInterface(object):

    # soft threshold -  email will be send
    current_build_duration_threshold_soft = 60  # minutes
    # hard threshold - the build is really getting canceled
    current_build_duration_threshold_hard = 70  # minutes
    # wait this timeout when stopping a build
    stop_build_timeout = 10  # seconds
    # builds statistics history, go back this history on builds init
    builds_history_init_limit = 2 * 24 * 60  # 2 days in minutes

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

    def stop_running_build(self, job=None, build_id=-1):
        """
        Stop the build_id on the project type identified by the job
        reference (as returned by the .get_job(job_name) call.

        """
        build = job.get_build(build_id)
        log.warn("Stopping build %s ..." % build)
        stop_call_response = build.stop()
        for _ in range(self.stop_build_timeout):
            time.sleep(1)
            # when using the same build reference to check the current status,
            # even when jenkins page reports the build ABORTED, this call upon
            # the same reference of build will receive None
            # get a fresh build reference after the stop() call
            build = job.get_build(build_id)
            status = build.get_status()
            if status == "ABORTED":
                ActivitySummaryModel.increase_counters(which_counters=["stopped_builds_counter"])
                break
        else:
            status = ("status '%s' - after %s seconds timeout, should be 'ABORTED'" %
                      (status, self.stop_build_timeout))
        log.debug("Finished build stop method, result: %s" % status)
        return stop_call_response, status

    def check_running_build(self, job_name=None, current_build_id=-1):
        """
        Check duration of the build build.
        Dictionary resp is updated about actions performed in this method.

        """
        resp = {}
        job = self.server.get_job(job_name)
        build = job.get_build(current_build_id)
        # get_timestamp returns this type of data, is in UTC:
        # datetime.datetime(2015, 3, 3, 19, 41, 56, tzinfo=<UTC>) (is not JSON serializable)
        ts = build.get_timestamp()
        resp["start_timestamp"] = get_localized_timestamp_str(ts)
        resp["retrieved_at"] = get_current_timestamp_str()
        console_url = "%s/job/%s/%s/console" % (self.jenkins_url, job_name, current_build_id)
        now = datetime.datetime.utcnow()  # there is no timezone info, putting UTC
        duration = pytz.utc.localize(now) - ts
        duration_str = str(duration).split('.')[0]
        resp["duration"] = duration_str
        resp["stop_threshold_minutes"] = self.current_build_duration_threshold_hard
        resp["email_notification"] = False
        if duration.total_seconds() > self.current_build_duration_threshold_hard * 60:
            stop_call_response, status = self.stop_running_build(job=job,
                                                                 build_id=current_build_id)
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
            log.debug("build check response:\n%s" % formatted_data)
            subject = "long #%s %s" % (current_build_id, job_name)
            result = send_email(subject=subject, body=msg + "\n\n" + formatted_data)
            if result:
                ActivitySummaryModel.increase_counters(which_counters=["sent_emails_counter"])
        return resp

    def check_running_builds_get_info(self):
        """
        Iterate over all job types and if a job type is currently running
        (i.e. there is an active build for the job type), last build number
        is retrieved and duration of that is build is checked.

        """
        resp = []
        for job_name in self.job_names:
            try:
                job = self.server.get_job(job_name)
                running = job.is_running()
            except UnknownJob:
                log.warn("Jenkins project '%s' unknown by the server." % job_name)
                continue
            log.info("Checking job '%s', running: %s." % (job_name, running))
            if running:
                r = dict()
                r["job_name"] = job_name
                last_build_id = job.get_last_buildnumber()
                r["last_build_id"] = last_build_id
                result = self.check_running_build(job_name=job_name,
                                                  current_build_id=last_build_id)
                r.update(result)
                resp.append(r)
        return resp

    def builds_stats_init(self):
        """
        Build is one running test suite on jenkins for a given
        job type (project type)
        iterate over projects and retrieve info on all builds
        going back to history

        """
        log.info("Start builds stats init at '%s'" % get_current_timestamp_str())
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
                build = job.get_build(bid)
                ts = build.get_timestamp()
                status = build.get_status()
                if (utc_now - ts).total_seconds() > limit:
                    # not interested in builds older than history limit
                    log.debug("Hit too old build, going to another job type ...")
                    break
                self.process_build_info_and_store(build=build,
                                                  job_name=job_name,
                                                  timestamp=ts,
                                                  build_id=bid,
                                                  status=status)
        log.info("Finished builds stats init at '%s'" % get_current_timestamp_str())

    def process_build_info_and_store(self,
                                     build=None,
                                     job_name=None,
                                     timestamp=None,
                                     build_id=None,
                                     status=None):
        """
        Retrieve further details for a build including console output
        analysis and store the data into datastore.

        """
        # get rid of decimal point 0:18:19.931000 at build duration
        duration = str(build.get_duration()).split('.')[0]
        console_output = build.get_console()
        result = self.process_console_output(console_output)
        key_id = BuildsStatisticsModel.construct_datastore_key_id(job_name, build_id)
        builds_stats = BuildsStatisticsModel(id=key_id,
                                             name=job_name,
                                             bid=build_id,
                                             status=status,
                                             # naive datetime (no timezone)
                                             ts=timestamp.replace(tzinfo=None),
                                             duration=duration)
        if result:
            for item in ("passed", "failed", "skipped", "error"):
                setattr(builds_stats, item, result[item])
        log.debug("Storing %s ..." % builds_stats)
        builds_stats.put()

    def process_console_output(self, console_output):
        """
        Process Jenkins job console output.
        Iterate over the first type patterns to identify the result status line.
        The iterate over the second pass expressions to derive
        number of passed, skipped, failed and error test cases.

        """
        for cp in FIRST_ITERATION_PATTERNS:
            result_line = cp.findall(console_output)
            if result_line:
                if len(result_line) != 1:
                    # there is 0 or more these results lines (which are
                    # py.test format), in this case, don't calculate passed,
                    # failed, etc test cases
                    return None
                # get  1) passed  2) failed  3) skipped  4) error  5) duration
                result = {}
                for cp2, what in SECOND_ITERATION_PATTERNS:
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
        """
        Main task to run over job types and builds from the last one:
        retrieve information about a build and store into datastore
        if it has not been processed in the previous run of this
        routine.

        """
        log.info("Start update builds stats at '%s'" % get_current_timestamp_str())
        for job_name in self.job_names:
            try:
                job = self.server.get_job(job_name)
            except UnknownJob:
                log.warn("Jenkins project '%s' unknown by the server." % job_name)
                continue
            # returns iterator of available build id numbers in
            # reverse order, most recent first
            bids = job.get_build_ids()
            for bid in bids:
                log.debug("Retrieving data on %s #%s ..." % (job_name, bid))
                build = job.get_build(bid)
                status = build.get_status()
                if not status:
                    log.debug("%s #%s has not finished, status: %s, going to "
                              "another build ..." % (job_name, bid, status))
                    continue
                # this build considered finished now
                # check if we have not hit a build which is already stored
                key_id = BuildsStatisticsModel.construct_datastore_key_id(job_name, bid)
                if BuildsStatisticsModel.get_by_id(key_id) is not None:
                    log.debug("%s #%s is already stored, going to the "
                              "next job type ..." % (job_name, bid))
                    break
                ts = build.get_timestamp()
                self.process_build_info_and_store(build=build,
                                                  job_name=job_name,
                                                  timestamp=ts,
                                                  build_id=bid,
                                                  status=status)
        ActivitySummaryModel.increase_counters(which_counters=["builds_stats_update_counter"])
        memcache.set(MEMCACHE_BUILDS_KEY, None)
        log.info("Finished update builds stats at '%s'" % get_current_timestamp_str())

    # do not put exception catcher here, sometimes there are cancelled URL
    # calls due to Jenkins taking too long to return response. in such situation
    # the email quota could easily be consumed.
    def update_overview_check_running_builds(self):
        """
        Combines 2 actions - update overview data (info about currently
        running builds and checks them if they are not for too long
        in execution. Entry point.

        """
        log.info("Start update overview, check builds at '%s'" % get_current_timestamp_str())
        data = dict(total_queued_jobs=self.get_total_queued_jobs(),
                    running_jobs=self.check_running_builds_get_info())
        # if there is no date on running jobs, add timestamp, it would be there otherwise
        if len(data["running_jobs"]) == 0:
            data["retrieved_at"] = get_current_timestamp_str()
        OverviewModel.update_overview_data(data)
        log.debug("OverviewModel data updated:\n%s" % pprint.pformat(data))
        ActivitySummaryModel.increase_counters(which_counters=["overview_update_counter"])
        log.info("Finished update overview, check builds at '%s'" % get_current_timestamp_str())


def get_jenkins_instance():
    jenkins = JenkinsInterface(jenkins_url=jenkins_url,
                               user_name=user_name,
                               access_token=access_token,
                               job_names=job_names)
    return jenkins


def initialization():
    """
    Initialize datastore types.

    """
    msg = "Initialization run at %s ..." % get_current_timestamp_str()
    log.info(msg)
    if ActivitySummaryModel.get_data() is None:
        log.debug("ActivitySummaryModel initialization ...")
        activity = ActivitySummaryModel(id=ACTIVITY_SUMMARY_MODEL_ID_KEY)
        activity.put()
        log.debug("Finished ActivitySummaryModel initialization.")
    else:
        log.debug("ActivitySummaryModel is already initialized.")
    if len(BuildsStatisticsModel.query().fetch(keys_only=True)) == 0:
        deferred.defer(get_jenkins_instance().builds_stats_init)
        log.debug("Finished BuildsStatisticsModel initialization.")
    else:
        log.debug("BuildStatisticsModel is already initialized.")
    return msg
