from backend.db.repositories import AgentJobRepository


class JobClaimService:
    def try_claim_job(self, db, job_id: str):
        return AgentJobRepository(db).try_claim_job(job_id)
