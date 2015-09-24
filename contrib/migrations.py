"""
Data migrations, data update functionality.

"""

import logging as log

from contrib.models import BuildsStatisticsModel


def migrate_01(project_name=None, start_bid=None, stop_bid=None):
    """
    Update keys on the BuildsStatisticsModel model.
    Previous key id was name-build_id without padding zeros.
    Current key id format is: "%s-%015d" % (job_name, build_id)

    Done migrations on projects (2015-09-23):

        [remains two upmost development jenkins projects and projects excluded currently]

        Selenium_Portal_MTV_master_public
        Selenium_Portal_MTV_master_sandbox
        Selenium_Portal_MTV_staging_public
        Selenium_Portal_MTV_staging_sandbox
        Selenium_Portal_MTV_topic_selenium_public
        Selenium_Portal_MTV_topic_selenium_sandbox

        all TN done
        Selenium_Portal_TN_topic_selenium_public
        Selenium_Portal_TN_staging_public
        Selenium_Portal_TN_master_public
        Selenium_Portal_TN_development_public



        TODO:
        1) check and migrate also jenkins projects which are no longer
            daily processed (master CI)
        2) have a query for check for types of jenkins projects (names)
            and how many items are in the datastore in total


    """
    log.debug("Start of migration method ...")

    def process_item(project_name, bid):
        log.debug("Processing project/build: '%s', build: '%s' ..." % (project_name, bid))
        # original keys
        # 7 digits 0 padded keys
        # 10 digits 0 padded keys
        key_ids = ["%s-%s"    % (project_name, bid),
                   "%s-%07d"  % (project_name, bid),
                   "%s-%010d" % (project_name, bid)]
        key_id15 = "%s-%015d" % (project_name, bid)
        for key_id in key_ids:
            log.debug("Checking key '%s' ..." % key_id)
            build = BuildsStatisticsModel.get_by_id(key_id)
            if build:
                assert build.key.id() == key_id
                log.debug(build)
                log.debug("Item of the key '%s' exists." % build.key.id())  # returns key
                build15 = BuildsStatisticsModel.get_by_id(key_id15)
                if build15:
                    assert build.name == build15.name and build.bid == build15.bid
                    log.debug("15 zeros padded item exists, deleting item of key '%s' ..." % key_id)
                    build.key.delete()
                else:
                    # update the current key to what we want
                    log.debug("Updating key of the item %s\n to '%s'" % (build, key_id15))
                    build.id = key_id15
                    build.put()
            else:
                log.debug(" ... non existent.")

    for b_id in range(int(start_bid), int(stop_bid)+1):
        process_item(project_name, b_id)

    log.debug("Migration method finished ...")