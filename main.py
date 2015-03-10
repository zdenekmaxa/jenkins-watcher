# -*- coding: utf-8 -*-
"""
Google App Engine Jenkins CI server watcher application.

Main application file.

Uses jenkinsapi library (wrapper around Jenkins CI server REST calls).
https://pypi.python.org/pypi/jenkinsapi


NOTES:
    the number of HTTP connection to jenkins server is very high (jenkinsapi lib)
    very often:

    ConnectionError: HTTPConnectionPool(host='XXXXX', port=8080):
    Max retries exceeded with url: XXXXX
    (Caused by <class 'gae_override.httplib.HTTPException'>:
    Deadline exceeded while waiting for HTTP response from URL: XXXXX
    solved by patching jenkinsappi and requests lib (libs/README.md)

    The server works in CET/CEST times, talk the same (convert to this timezome
        times as retrieved from the server or datetime timestamps which are UTC).


REFERENCE:
    self.request.body


TODO:
    experiment with sms alerts

"""


import os
import json
import sys
import pprint
import logging as log

import webapp2
from google.appengine.ext import deferred

from config import egg_files
for egg_file in egg_files:
    sys.path.append(os.path.join(os.path.dirname(__file__), "libs", egg_file))

from jenkins import update_overview, update_builds_stats, builds_stats_init, JenkinsInterface
from jenkins import ActivitySummary, BuildsStatistics
from utils import get_current_timestamp_str, access_restriction, send_email


class RequestHandler(webapp2.RequestHandler):
    @access_restriction
    def index(self):
        # there is no timezone info there, maybe it's deeper
        # log.info("Received request, headers:\n%s" % self.request.headers.items())
        # returns Python dictionary
        resp = JenkinsInterface.get_overview_data()
        resp["current_time"] = get_current_timestamp_str()
        self.response.headers["Content-Type"] = "application/json"
        self.response.out.write(json.dumps(resp))

    def update_overview(self):
        msg = "Running update_overview task at %s ..." % get_current_timestamp_str()
        log.info(msg)
        deferred.defer(update_overview)
        self.response.out.write(msg)

    def update_builds_stats(self):
        msg = "Running update_builds_stats task at %s ..." % get_current_timestamp_str()
        log.info(msg)
        deferred.defer(update_builds_stats)
        self.response.out.write(msg)

    def init(self):
        msg = "Initialization run at %s ..." % get_current_timestamp_str()
        log.info(msg)
        if ActivitySummary.get_by_id(ActivitySummary.summary_id_key) is None:
            log.debug("ActivitySummary initialization ...")
            activity = ActivitySummary(id=ActivitySummary.summary_id_key)
            activity.put()
            log.debug("Finished ActivitySummary initialization.")
        else:
            log.debug("ActivitySummary is already initialized.")
        if len(BuildsStatistics.query().fetch()) == 0:
            deferred.defer(builds_stats_init)
            log.debug("Finished BuildsStatistics initialization.")
        else:
            log.debug("BuildStatistics is already initialized.")
        self.response.out.write(msg)

    def send_summary(self):
        log.info("Sending activity summary email at %s ..." % get_current_timestamp_str())
        formatted_data = pprint.pformat(ActivitySummary.get_data())
        send_email(subject="activity summary",
                   body="activity summary: " + "\n\n" + formatted_data)
        ActivitySummary.reset()
        log.info("Finished activity summary.")


routes = [
    webapp2.Route(r"/",
                  handler="main.RequestHandler:index",
                  name="index",
                  methods=["GET", ]),
    webapp2.Route(r"/update_overview",
                  handler="main.RequestHandler:update_overview",
                  name="update_overview",
                  methods=["GET", ]),
    webapp2.Route(r"/update_builds_stats",
                  handler="main.RequestHandler:update_builds_stats",
                  name="update_builds_stats",
                  methods=["GET", ]),
    webapp2.Route(r"/init",
                  handler="main.RequestHandler:init",
                  name="init",
                  methods=["GET", ]),
    webapp2.Route(r"/send_summary",
                  handler="main.RequestHandler:send_summary",
                  name="send_summary",
                  methods=["GET", ]),
]


# application instance
app = webapp2.WSGIApplication(routes=routes, debug=True)