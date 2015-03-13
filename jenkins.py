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
import copy

from google.appengine.ext import ndb

from jenkinsapi.jenkins import Jenkins
from jenkinsapi.custom_exceptions import NoBuildData

from config import user_name, access_token, job_names, jenkins_url
from utils import get_localized_timestamp_str, get_current_timestamp_str
from utils import send_email


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

    def to_dict(self):
        r = dict(job_name=self.name,
                 build_id=self.bid,
                 status=self.status,
                 timestamp=get_localized_timestamp_str(self.ts),
                 duration=self.duration,
                 passed=self.passed,
                 failed=self.failed,
                 skipped=self.skipped,
                 error=self.error)
        return r

    @staticmethod
    # raise _ToDatastoreError(err) BadRequestError: queries inside transactions must have ancestors
    #@ndb.transactional()
    def get_builds_data(days_limit=1):
        cond = datetime.datetime.utcnow() - datetime.timedelta(days=days_limit)
        # order should be the same as BuildsStatistics.name, BuildsStatistics.ts
        # this will already be ordered by job name and then by build id (since keys are such)
        query = BuildsStatistics.query().order(BuildsStatistics.key)
        builds = query.fetch()  # returns list of builds, of BuildsStatistics objects

        # BadRequestError: The first sort property must be the same as the property to which the
        # inequality filter is applied.
        # In your query the first sort property is name but the inequality filter is on ts
        # -> do the timestamp filtering on my own ... (can't combine ordering and filtering
        # arbitrarily)

        data = dict(days_limit=days_limit,
                    num_builds=0,
                    builds={})
        # builds - dict keys - job names ; values: lists of all builds under that job name
        res_builds = {}
        for b in builds:
            # check if the build is not before days_limit days
            if b.ts < cond:
                continue
            res_build = copy.deepcopy(b.to_dict())
            del res_build["job_name"]
            try:
                res_builds[b.name].append(res_build)
            except KeyError:
                res_builds[b.name] = [res_build]
            finally:
                data["num_builds"] += 1
        data["builds"] = res_builds
        return data


class JenkinsInterface(object):

    overview_id_key = 1
    # 30mins - email will be send
    current_build_duration_threshold_soft = 30  # minutes
    # 60mins - the build is really getting canceled
    current_build_duration_threshold_hard = 60  # minutes
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
                ActivitySummary.increase_stopped_builds_counter()
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
                ActivitySummary.increase_sent_emails_counter()
        return resp

    def check_running_builds_get_info(self):
        resp = []
        for job_name in self.job_names:
            job = self.server.get_job(job_name)
            running = job.is_running()
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

    @staticmethod
    @ndb.transactional()
    def get_overview_data():
        overview = DataOverview.get_by_id(JenkinsInterface.overview_id_key)
        # is already a Python object
        return overview.data

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
                b = job.get_build(bid)
                ts = b.get_timestamp()
                if (utc_now - ts).total_seconds() > limit:
                    # not interested in builds older than history limit
                    log.debug("Hit too old build, going to another job type ...")
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
        log.info("Finished builds stats init at '%s'" % get_current_timestamp_str())

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
        log.info("Start update builds stats at '%s'" % get_current_timestamp_str())
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
        log.info("Finished update builds stats at '%s'" % get_current_timestamp_str())

    @ndb.transactional()
    def _update_overview_in_data_store(self, data):
        # just the update has to be separated from the refresh method,
        # the transaction fails there since it takes too long
        overview = DataOverview(id=self.overview_id_key, data=data)
        overview.put()

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
        self._update_overview_in_data_store(data)
        data_formatted = pprint.pformat(data)
        log.debug("Data updated under key id: '%s'\n%s" % (self.overview_id_key, data_formatted))
        ActivitySummary.increase_overview_update_counter()
        log.info("Finished update overview, check builds at '%s'" % get_current_timestamp_str())


def get_jenkins_instance():
    jenkins = JenkinsInterface(jenkins_url=jenkins_url,
                               user_name=user_name,
                               access_token=access_token,
                               job_names=job_names)
    return jenkins