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
import datetime
import pytz

from jenkinsapi.jenkins import Jenkins
from jenkinsapi.custom_exceptions import NoBuildData
from jenkinsapi.custom_exceptions import NoResults

from config import job_names, jenkins_url, user_name, access_token
from utils import get_localized_timestamp_str


def init(jenkins_server, history=24*60*60):  # 1 day in seconds
    # there is no timezone info, putting UTC
    utc_now = pytz.utc.localize(datetime.datetime.utcnow())
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
                # not interested in the very last one, may be running
                continue
            # retrieve details
            b = job.get_build(bid)
            ts = b.get_timestamp()
            print type(ts), ts
            dt = datetime.datetime.utcfromtimestamp(ts)
            print dt
            if (utc_now - ts).total_seconds() > history:
                # not interested in builds older than history limit
                break
            status = b.get_status()
            # get rid of decimal point 0:18:19.931000
            duration = str(b.get_duration()).split('.')[0]
            ts = get_localized_timestamp_str(ts)
            console_output = b.get_console()
            result = process_console_output(console_output)
            print "%s .. %s .. %s .. %s .. %s\n" % (bid, ts, duration, status, result)


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


def process_console_output(console_output):
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
            result = "n/a"
    return result


def process_consoles():
    consoles = os.listdir("consoles")
    count = 0
    for name in consoles:
        output = open("consoles/%s" % name, 'r').read()
        result = process_console_output(output)
        print "%s .. %s" % (name, result)
        # count += 1
        # if count > 10:
        #     break


def main():
    server = Jenkins(jenkins_url, username=user_name, password=access_token)
    init(server, history=5*60*60)  # 5 hours
    #init(server, history=5*24*60*60)  # 5 days
    #init(server)
    #process_consoles()


if __name__ == '__main__':
    main()