import time
import datetime
import logging
import sqlalchemy
import sys
import ah_config
import ah_db

sys.path.append('src/')
# TODO not really necessary to go through here
import datadog_events
import deployments_db
import deployment_sources.earnin_standard
import deployment_sources.nativeapi_legacy


if __name__ == "__main__":
    ah_config.initialize()

    datadog_events.initiatilize_datadog(
        api_key=ah_config.get("datadog_credentials.api_key"),
        app_key=ah_config.get("datadog_credentials.app_key")
    )

    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    with ah_db.open_db_connection('engineering_metrics') as conn:
        # TODO Use logging lib instead of print
        print("Connected to %s", conn.engine.url.__repr__())

        start = datetime.datetime.now() - datetime.timedelta(50)
        end   = datetime.datetime.now()

        # deployments_db.upsert_deploys(conn,
            # deployment_sources.nativeapi_legacy.query(start, end)
        # )

        deployments_db.upsert_deploys(conn,
            deployment_sources.earnin_standard.query(start, end)
        )
