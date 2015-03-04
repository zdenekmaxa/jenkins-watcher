"""
https://pypi.python.org/pypi/jenkinsapi
    API could get/set jobs configuration (will be useful on a mass changes)

    other interesting API:
        self.server.build_job
        job = self.server.get_job(job_name)
        dir(job)
        job.get_build_ids() # returns iterator
        job.get_build_triggerurl()
        job.get_last_build()
        job.get_last_buildnumber()
        job.is_running()
        job.is_queued_or_running()
        job.poll() # return None if not running
        job.invoke(securitytoken=None, block=False, skip_if_running=False)
        job.get_build(275)
        job.get_last_buildnumber()
        job.get_last_completed_buildnumber()
        job.get_last_failed_buildnumber()
        job.get_last_good_buildnumber()
        job.get_last_stable_buildnumber()
        print job.get_config() - returns XML job configuration

JUST FOR REFERENCE

"""

from jenkinsapi.jenkins import Jenkins
from jenkinsapi.custom_exceptions import NoBuildData


def print_jobs_stats(self, config_query=False):
    """
    Print Jenkins job statistics:
        job name, last job status, last job id, last failed job id

    """
    config = {}
    fail, success = 0, 0
    pformat = "%-45s %-12s %-8s %-13s %s"
    print "Querying %s jobs:" % len(JOBS)
    print pformat % ("JOB NAME", "LAST STATUS", "LAST_ID", "LAST_FAIL_ID", "ENABLED")
    print 90 * '-'
    for job_name in JOBS:
        job = self.server.get_job(job_name)
        last_id = job.get_last_completed_buildnumber()
        try:
            last_success_id = job.get_last_good_buildnumber()
        except NoBuildData as ex:
            last_success_id = -1
        try:
            last_fail_id = job.get_last_failed_buildnumber()
        except NoBuildData as ex:
            last_fail_id = "N/A"

        print pformat % (job_name,
                         last_status,
                         "#%s" % last_id,
                         "#%s" % last_fail_id,
                         job.is_enabled())
    print "SUCCESS: %s" % success
    print "FAIL:    %s" % fail
    if config:
        print "\nCONFIG:"
        pprint.pprint(config)


def main():
    jenkins = JenkinsAccess(jenkins_url, user_name, access_token)
    start = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #print dir(jenkins.server.get_queue)  # useless
    print jenkins.server.get_queue()  # prints queue URL
    print len(jenkins.server.get_queue())  # good, returs total num of queued
    job_name = "Selenium_Portal_MTV_staging_sandbox"
    job_name = "Selenium_Portal_topic_selenium_public"
    job = jenkins.server.get_job(job_name)
    #print dir(job)
    print "\n\n"
    #print job.has_queued_build()
    #get_queue_item
    #print job.is_queued()
    #print job.is_queued_or_running()
    print job.is_running()
    print job.jenkins  # prints jenkins URL
    #print dir(job.jenkins)
    print job.get_last_buildnumber()
    last = job.get_last_buildnumber()
    b = job.get_build(last)
    print "build dir"
    print dir(b)
    print "build: %s" % b
    # print b.get_data() # get_data() takes at least 2 arguments (1 given)
    print "duration:", b.get_duration()  # 0 if not finished
    #print dir(b.get_jenkins_obj())
    print "get_status:", b.get_status()  # None if not finished
    print "timestamp:", b.get_timestamp()  # yes, it's start of the build
    # [{'shortDescription': 'Started by timer'}
    #print "get_causes:", b.get_causes()
    # print "get_console:", b.get_console()  # entire console log
    # print "get_data:", b.get_data()  # requires arg which item of data ...
    from jenkinsapi.custom_exceptions import NoResults
    try:
        print "get_resultset:", b.get_resultset()
    except NoResults as ex:
        # is thrown even on fisnished builds
        print ex
    
    # retuns True upon call
    # have build ID, build ref, check status, should be ABORTED
    #print "stop:", b.stop()


    #d = job.get_build_dict() # all the build IDs and URLs ... not useful
    #print d
    #m = job.get_build_metadata(last)
    #print m
    return