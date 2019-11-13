import datetime
import sqlalchemy
import sqlalchemy.dialects.postgresql

import logging
logger = logging.getLogger(__name__)

SCHEMA                 = 'engineering_metrics'
DEPLOYMENTS_TABLE_NAME = 'deployments'
DEPLOYMENTS_TABLE      = sqlalchemy.Table(
    DEPLOYMENTS_TABLE_NAME,
    sqlalchemy.MetaData(),
    sqlalchemy.Column('artifact',            sqlalchemy.TEXT),
    sqlalchemy.Column('deployed_at',         sqlalchemy.TIMESTAMP(timezone=True)),
    sqlalchemy.Column('ingested_at',         sqlalchemy.TIMESTAMP(timezone=True)),
    sqlalchemy.Column('is_rollback',         sqlalchemy.BOOLEAN),
    sqlalchemy.Column('datadog_event_id',    sqlalchemy.TEXT),
    sqlalchemy.Column('jenkins_job_name',    sqlalchemy.TEXT),
    sqlalchemy.Column('jenkins_build_num',   sqlalchemy.INTEGER),
    sqlalchemy.Column('jenkins_event_title', sqlalchemy.TEXT),
    schema=SCHEMA
)


# TODO error or warn or log on column mismatch
def upsert_deploys(conn, deploys):
    stmt = sqlalchemy.dialects.postgresql.insert(DEPLOYMENTS_TABLE)
    # TODO match on datadog event id instead?
    stmt = stmt.on_conflict_do_nothing(index_elements=['artifact', 'deployed_at'])
    logger.info("Upserting ({}) deployments".format(len(deploys)))

    ingest_time = datetime.datetime.now()
    for deploy in deploys:
        deploy["ingested_at"] = ingest_time

    res = conn.execute(stmt, deploys)
