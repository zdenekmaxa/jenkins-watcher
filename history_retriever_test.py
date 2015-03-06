"""
jenkisapi library useful API

API references

server.build_job
job = self.server.get_job(job_name)
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

job = self.server.get_job(job_name)
last_success_id = job.get_last_good_buildnumber()
last_fail_id = job.get_last_failed_buildnumber()
job.is_enabled()) .enable() .disable()

job.get_last_buildnumber()
b = job.get_build(build_number)

b.get_data() # get_data() takes at least 2 arguments (1 given)
b.get_duration()  # 0 if not finished ; duration of a build
b.get_status()  # None if not finished
b.get_timestamp()  # yes, it's start of the build
b.get_console()  # entire console log
job.get_build_dict() # all the build IDs and URLs
job.get_build_metadata(last) ?

"""


import os
import re
import sys

from jenkinsapi.jenkins import Jenkins
from jenkinsapi.custom_exceptions import NoBuildData
from jenkinsapi.custom_exceptions import NoResults

from config import job_names, jenkins_url, user_name, access_token


def init(jenkins_server, history_length=sys.maxint):
    for job_name in job_names:
        job = jenkins_server.get_job(job_name)
        print "Job: '%s'" % job
        print "is running: %s" % job.is_running()
        # returns iterator of available build id numbers in
        # reverse order, most recent first
        bids = job.get_build_ids()
        count = 0
        for bid in bids:
            count += 1
            if count == 1:
                # not interested in the very last one, may even be running
                continue
            # retrieve details
            b = job.get_build(bid)
            status = b.get_status()
            ts = b.get_timestamp()
            # TODO
            # remove part after decimal point
            duration = b.get_duration()
            console_output = b.get_console()
            f = open("consoles/%s-%s-console.txt" % (job_name, bid), 'w')
            f.write(console_output)
            f.close()
            # process console output - search for:
            # 14:31:30 =================== 28 passed, 5 skipped in 1078.49 seconds ====================
            # 1078.49 seconds ====================
            #   for P, S, F, E number of testcases and which FAIL tests (here test cases names)

            # CONTINUE WITH SEARCHING FOR THIS CRITICAL LINE

            print ("id: %s  status: %s  start ts: %s  duration: %s  console: %s" %
                   (bid, status, ts, duration, len(console_output)))
            if count > history_length:
                break
        print "\n\n"


def process_consoles():
    # total console files: 2571
    # example lines to search for:
    # =================== 28 passed, 5 skipped in 1078.49 seconds ====================
    # ========== 1 failed, 27 passed, 5 skipped, 1 error in 996.52 seconds ===========
    # don't do passed|failed|skipped - matches something else
    # TODO
    # - any better regexp solution?
    # - retrieve number of passed, failed, skipped, error tests and also duration (for check?)
    pattern1 = "=+\ .*[0-9]+\ passed.* in .* seconds\ =+"
    pattern2 = "=+\ .*[0-9]+\ failed.* in .* seconds\ =+"
    pattern3 = "=+\ .*[0-9]+\ skipped.* in .* seconds\ =+"
    cp1 = re.compile(pattern1)
    cp2 = re.compile(pattern2)
    cp3 = re.compile(pattern3)
    consoles = os.listdir("consoles")
    count = 0
    for name in consoles:
        output = open("consoles/%s" % name, 'r').read()
        for cp in (cp1, cp2, cp3):
            result = cp.findall(output)
            #result = cp.search(output)
            if result:
                break
        else:
            result = "n/a"
        print "%s .. %s chars result: %s" % (name, len(output), result)
        # count += 1
        # if count > 10:
        #     break


def main():
    server = Jenkins(jenkins_url, username=user_name, password=access_token)
    #init(server, history_length=10)
    #init(server)
    process_consoles()


if __name__ == '__main__':
    main()