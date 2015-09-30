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

    Done migrations on projects - all currently visible done.

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