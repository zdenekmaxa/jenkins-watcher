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

    The jenkins CI server works in CET/CEST times, talk the same (convert to
        this timezome times as retrieved from the server or datetime
         timestamps which are UTC).

    NDB can only store DataTimeProperty in UTC but timezone unaware (naive),
        otherwise .put() throws an exception


REFERENCE:
    self.request.body

"""


import datetime
import json
import pprint
import logging

import webapp2
from webapp2 import Route, WSGIApplication
from webapp2_extras.routes import PathPrefixRoute
from google.appengine.ext import deferred
from google.appengine.ext import db

from contrib.jenkins import JenkinsInterface, get_jenkins_instance, initialization
from contrib.models import OverviewModel, ActivitySummaryModel, BuildsStatisticsModel
from contrib.utils import get_current_timestamp_str, access_restriction, send_email
from contrib.utils import exception_catcher, get_localized_timestamp_str
from contrib.migrations import migrate_01


class BaseRequestHandler(webapp2.RequestHandler):
    def return_json_error(self, status, msg):
        self.response.headers["Content-Type"] = "application/json"
        self.response.set_status(status)
        self.response.out.write(json.dumps(dict(message=msg)))


class RequestHandler(BaseRequestHandler):
    @access_restriction
    @exception_catcher
    def get_overview(self):
        # there is no timezone info in the request headers, maybe it's deeper
        # log.info("Received request, headers:\n%s" % self.request.headers.items())
        # returns Python dictionary
        resp = OverviewModel.get_overview_data()
        self.response.headers["Content-Type"] = "application/json"
        self.response.out.write(json.dumps(resp))

    def init(self):
        msg = initialization()
        self.response.out.write(msg)

    def send_activity_summary(self):
        msg = "Sending activity summary email at %s ..." % get_current_timestamp_str()
        logging.info(msg)
        formatted_data = pprint.pformat(ActivitySummaryModel.get_data())
        send_email(subject="activity summary",
                   body="activity summary: " + "\n\n" + formatted_data)
        ActivitySummaryModel.reset()
        logging.info("Finished sending activity summary.")
        self.response.out.write(msg)

    @access_restriction
    @exception_catcher
    def get_activity_summary(self):
        resp = ActivitySummaryModel.get_data()
        self.response.headers["Content-Type"] = "application/json"
        self.response.out.write(json.dumps(resp))

    @exception_catcher
    def update_overview_check_running_builds(self):
        msg = "Running task at %s ..." % get_current_timestamp_str()
        logging.info(msg)
        deferred.defer(get_jenkins_instance().update_overview_check_running_builds)
        self.response.out.write(msg)

    @exception_catcher
    def update_builds(self):
        msg = "Running task at %s ..." % get_current_timestamp_str()
        logging.info(msg)
        deferred.defer(get_jenkins_instance().update_builds_stats)
        self.response.out.write(msg)

    @access_restriction
    @exception_catcher
    def get_builds_stats(self):
        try:
            arg = self.request.get("days_limit", 1)
            days_limit = int(arg)
        except Exception as ex:
            self.response.out.write("wrong argument: '%s'" % arg)
            return
        resp = BuildsStatisticsModel.get_builds_data(days_limit=days_limit)
        asm = ActivitySummaryModel.get_data()
        if asm:
            resp["builds_statistics_model_last_update_at"] = \
                asm["builds_statistics_model_last_update_at"]
        self.response.headers["Content-Type"] = "application/json"
        # seconds (10minutes)
        self.response.headers["Cache-Control"] = "max-age=600"  # , must-revalidate, private"
        # self.response.cache_control = 'public'
        # self.response.cache_control.max_age = 600
        self.response.out.write(json.dumps(resp))

    def print_builds(self):
        """
        Debugging route, print some builds stats datastore entries.
        This serves as basis for data migration (changing the
        BuildsStatisticsModel key ids) to "%s-%015d" % (job_name, build_id)
        format.

        2015-09-28 there is new interesting datastore quota now:
            Datastore Small Operations

        currently items: Retrieved builds from datastore: 14886

        consumes Datastore Small Operations Quota a lot!

        """
        # the order should be the same as BuildsStatistics.name, BuildsStatistics.ts
        # this will already be ordered by job name and then by build id (since keys are such)
        # now do reverse order so that newest appear first on the web page
        now = datetime.datetime.utcnow()
        time_condition = now - datetime.timedelta(days=1)
        # select only last day builds
        #query = BuildsStatisticsModel.query(BuildsStatisticsModel.ts > time_condition)
        query = BuildsStatisticsModel.query()

        # reverse sort, fetches only datastore key objects
        builds = sorted(query.fetch(keys_only=True), key=lambda x: x.id(), reverse=True)

        t_end = datetime.datetime.now()
        msg = "Current time: %s<br/>" % datetime.datetime.now()
        msg += "Retrieving data lasted: %s [sec]<br/>" % (t_end - now).seconds
        msg += "Retrieved builds from datastore: %s<br/><br/>" % len(builds)
        self.response.out.write(msg)
        self.response.out.write("<br /><br />")
        # do this only if there is a days=something limit applied, it's otherwise very
        # many of items
        #for b in builds:
        #    self.response.out.write(b)
        #    self.response.out.write("<br />")

        # get distinct jenkins projects names:
        # DOESN'T WORK ON NDB:
        #q = "SELECT DISTINCT name FROM BuildsStatisticsModel;"
        #query = db.GqlQuery(q)

        query = BuildsStatisticsModel.query(projection=[BuildsStatisticsModel.name],
                                            distinct=True)
        # fetches
        # BuildsStatisticsModel(key=Key('BuildsStatisticsModel', 'Selenium_Portal_MTV_development_public-000000000001013'), name=u'Selenium_Portal_MTV_development_public', _projection=('name',))
        build_keys = query.fetch()
        for key in build_keys:
            self.response.out.write(key)
            self.response.out.write("<br />")

    def migrate(self, start="01", end=None):
        """
        Should we even need, start, end would be migrations indexes to
        run.
        start, end - migrations indexes

        Run as
        https://jenkins-watcher.appspot.com/datastore/migrate?jenkins_project_name=Selenium_Portal_MTV_topic_selenium_sandbox&start_bid=100&stop_bid=1700

        """
        jenkins_project_name = self.request.get("jenkins_project_name", None)
        start_bid = self.request.get("start_bid", None)
        stop_bid = self.request.get("stop_bid", None)
        if jenkins_project_name is None or start_bid is None or stop_bid is None:
            self.response.out.write("Some arguments not provided.<br />");
            self.response.out.write("Run as https://jenkins-watcher.appspot.com/datastore/migrate?jenkins_project_name=Selenium_Portal_MTV_topic_selenium_sandbox&start_bid=100&stop_bid=1700")
        else:
            deferred.defer(migrate_01,
                           project_name=jenkins_project_name,
                           start_bid=start_bid,
                           stop_bid=stop_bid)
            self.response.out.write("Background migration task started, check logs ...")


# adjust logging
LOG_FORMAT = "[%(module)s::%(funcName)s:%(lineno)s] %(message)s"
logging.getLogger().handlers[0].setFormatter(logging.Formatter(fmt=LOG_FORMAT))
# jenkinsapi makes incredible amount of calls to jenkins and log output
# is crowded with each HTTP call and its result debug messages, limit this
log = logging.getLogger("requests.packages.urllib3")
log.setLevel(logging.WARNING)



routes = [
    Route(r"/init",
          handler="main.RequestHandler:init",
          name="init",
          methods=["GET", ]),
    Route(r"/overview",
          handler="main.RequestHandler:get_overview",
          name="get_overview",
          methods=["GET", ]),
    PathPrefixRoute(r"/overview", [
        Route(r"/update",
              handler="main.RequestHandler:update_overview_check_running_builds",
              name="update_overview_check_running_builds",
              methods=["GET", ])
    ]),
    Route(r"/builds",
          handler="main.RequestHandler:get_builds_stats",
          name="get_builds_stats",
          methods=["GET", ]),
    PathPrefixRoute(r"/builds", [
        Route(r"/update",
              handler="main.RequestHandler:update_builds",
              name="update_builds",
              methods=["GET", ])
    ]),
    Route(r"/activity",
          handler="main.RequestHandler:get_activity_summary",
          name="get_activity_summary",
          methods=["GET", ]),
    PathPrefixRoute(r"/datastore", [
        Route(r"/builds",
              handler="main.RequestHandler:print_builds",
              name="print_builds",
              methods=["GET", ]),
        Route(r"/migrate",
              handler="main.RequestHandler:migrate",
              name="migrate",
              methods=["GET", ])
    ])
]

# application instance
app = WSGIApplication(routes=routes, debug=True) # , config=webapp2_config)