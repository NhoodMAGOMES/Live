ORCHESTRATION_AGENT_SLUGS = {"verification_cycle"}


def is_orchestration_agent(slug: str) -> bool:
    return slug in ORCHESTRATION_AGENT_SLUGS
