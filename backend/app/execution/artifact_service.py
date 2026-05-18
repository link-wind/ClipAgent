from backend.db.repositories import AgentArtifactRepository


class ExecutionArtifactService:
    def __init__(self, db_session):
        self.artifact_repo = AgentArtifactRepository(db_session)

    def create_artifact(
        self,
        *,
        session_id: str,
        job_id: str,
        artifact_type: str,
        public_url: str,
        local_path: str | None = None,
        scene_id: str | None = None,
        source_url: str | None = None,
        duration: float | None = None,
        metadata: dict | None = None,
    ):
        return self.artifact_repo.create(
            session_id=session_id,
            job_id=job_id,
            artifact_type=artifact_type,
            scene_id=scene_id,
            source_url=source_url,
            local_path=local_path,
            public_url=public_url,
            duration=duration,
            metadata_json=metadata or None,
        )
