"""
Jenkins CI server interface file.

"""


import sys
import time
import datetime
import json
import logging as log

from google.appengine.ext import deferred
from google.appengine.ext import ndb

from jenkinsapi.jenkins import Jenkins
from jenkinsapi.custom_exceptions import NoBuildData

from config import user_name, access_token, job_names, jenkins_url, egg_files


class DataOverview(ndb.Model):
    data = ndb.JsonProperty(required=True)


class JenkinsInterface(object):

    overview_id_key = 1

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
        self.server.RETRY_ATTEMPTS = 5

    def get_total_queued_jobs(self):
        return len(self.server.get_queue())

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
                # TODO:
                # works in UTC
                # the type returned here:
                # datetime.datetime(2015, 3, 3, 19, 41, 56, tzinfo=<UTC>) is not JSON serializable
                # convert timezone
                r["start_timestamp"] = str(build.get_timestamp())
                resp.append(r)
        return resp

    @ndb.transactional()
    def _update_data_store(self, data):
        # just the update has to be separated from the refresh method,
        # the transaction fails there since it takes too long
        overview = DataOverview(id=self.overview_id_key, data=data)
        overview.put()

    def refresh_overview_data(self):
        start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.info("Start refresh overview data task: '%s'" % start_time)
        data = dict(total_queued_jobs=self.get_total_queued_jobs(),
                    running_jobs=self.get_running_jobs_info())
        data["data_retrieved_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._update_data_store(data)
        # TODO:
        # implement checker of the 'start_timestamp' values ...
        end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.debug("Data updated under key id: '%s'" % self.overview_id_key)
        log.debug("Finished refresh overview data task: '%s'" % end_time)

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