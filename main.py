# -*- coding: utf-8 -*-
"""
Google App Engine Jenkins CI server watcher application.

Main application file.

NOTES:
    the number of HTTP connection to jenkins server is very high (jenkinsapi lib)
    very often:

    ConnectionError: HTTPConnectionPool(host='XXXXX', port=8080):
    Max retries exceeded with url: XXXXX
    (Caused by <class 'gae_override.httplib.HTTPException'>:
    Deadline exceeded while waiting for HTTP response from URL: XXXXX
    solved by patching jenkinsappi and requests lib (libs/README.md)


REFERENCE:
    self.request.body


TODO:
    timezone - correct time
        check timezone, transform into CET/CEST
        get automatically correct according to current local timezone (of the caller)
        check pytz

    periodic task also sends alert (email) if the builds timestamp exceeds some duration (60min)
        this will later do build.stop() to abort the build ; experiment with sms alert

    would be nice to have longer-term (24h, 48, 72hs overviews), all trends

    user access control, by domain restriction
        currentuser=users.get_current_user().email()

"""


import os
import json
import sys
import logging as log
import datetime

import webapp2
from google.appengine.ext import deferred
from google.appengine.api import users

from config import egg_files
for egg_file in egg_files:
    sys.path.append(os.path.join(os.path.dirname(__file__), "libs", egg_file))

from jenkins import get_jenkins_interface, refresh, JenkinsInterface


class RequestHandler(webapp2.RequestHandler):
    def index(self):
        # there is no timezone info there, maybe it's deeper
        # log.info("Received request, headers:\n%s" % self.request.headers.items())
        resp = JenkinsInterface.get_overview_data()
        resp["current_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.response.headers["Content-Type"] = "application/json"
        self.response.out.write(json.dumps(resp))

    def refresh(self):
        time_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = "Running refresh task (%s) ..." % time_now
        log.info(msg)
        deferred.defer(refresh)
        self.response.out.write(msg)

routes = [
    webapp2.Route(r"/",
                  handler="main.RequestHandler:index",
                  name="index",
                  methods=["GET", ]),
    webapp2.Route(r"/refresh",
                  handler="main.RequestHandler:refresh",
                  name="refresh",
                  methods=["GET", ]),
]


# application instance
app = webapp2.WSGIApplication(routes=routes, debug=True)