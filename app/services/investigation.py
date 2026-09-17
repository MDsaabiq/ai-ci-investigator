from app.agent.investigator import Investigator
from app.models.evidence import InitialEvidence
from app.services.evidence import EvidenceCollector


class InvestigationService:
    def __init__(
        self,
        evidence_collector: EvidenceCollector,
        investigator: Investigator,
    ):
        self.evidence_collector = evidence_collector
        self.investigator = investigator

    def investigate(
        self,
        repository: str,
        run_id: int,
    ):
        evidence = self.evidence_collector.collect(
            repository,
            run_id,
        )

        result = self.investigator.investigate(evidence)

        return {
            "evidence": evidence,
            "investigation": result,
        }