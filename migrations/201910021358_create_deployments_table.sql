CREATE TABLE deployments (
    id integer NOT NULL,
    artifact text,
    jenkins_build_num text,
    jenkins_event_title text,
    jenkins_job_name text,
    datadog_event_id text,
    ingested_at timestamp with time zone,
    is_rollback BOOLEAN,
    deployed_at timestamp with time zone,
    env text
);
-- TODO ingest job id ? 

CREATE SEQUENCE deployments_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER TABLE ONLY deployments ALTER COLUMN id SET DEFAULT nextval('deployments_id_seq'::regclass);

ALTER TABLE ONLY deployments
    ADD CONSTRAINT deployments PRIMARY KEY (id);

CREATE UNIQUE INDEX idx_artifact_deployed_at_uniq on deployments (artifact, deployed_at);
