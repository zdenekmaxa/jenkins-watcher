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
    have longer-term (24h, 48, 72hs overviews - query by 1, 2, 3 ... days), all trends
        periodically retrieve data on all builds:
        status, duration, timestamp ; result: which jobs failed, P:num, F:num, S:num, E:num
        on frontend horizontal scroll, colour coding

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

from jenkins import refresh, JenkinsInterface
from jenkins import ActivitySummary
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

    def refresh(self):
        msg = "Running refresh task at %s ..." % get_current_timestamp_str()
        log.info(msg)
        deferred.defer(refresh)
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
    webapp2.Route(r"/refresh",
                  handler="main.RequestHandler:refresh",
                  name="refresh",
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