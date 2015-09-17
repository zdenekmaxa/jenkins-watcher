"""
Data migrations, data update functionality.

"""

import logging as log

from contrib.models import BuildsStatisticsModel


def migrate_01():
    """
    Update keys on the BuildsStatisticsModel model.
    Previous key id was name-build_id without padding zeros.
    Current key id format is: "%s-%015d" % (job_name, build_id)
    """
    log.debug("start of migration method ...")
    build = BuildsStatisticsModel.get_by_id("Selenium_Portal_MTV_topic_selenium_sandbox-0001641")
    log.debug(build)
    new_id = "%s-%015d" % (build.name, build.bid)
    log.debug(new_id)
    # if this way of migrating / updating data doesn't work, then will have to
    # read all data fields, construct a new item (with a new key id), delete the old item
    # and store the new one
    # TODO
    # could not finish now - exceeded data read operations quota
    build.id = new_id
    build.put()
    log.debug("migration method finished ...")