"""Middleware configuration for the EvoScientist agent."""

from deepagents.backends import FilesystemBackend
from deepagents.middleware.skills import SkillsMiddleware


def create_skills_middleware(
    skills_dir: str = "./skills/",
    workspace_dir: str = "./workspace/",
) -> SkillsMiddleware:
    """Create a SkillsMiddleware that loads skills.

    All skills (system and user-installed) live in ./skills/.
    The --user flag in install_skill.py also installs to ./skills/.

    Args:
        skills_dir: Path to the skills directory
        workspace_dir: Unused, kept for API compatibility

    Returns:
        Configured SkillsMiddleware instance
    """
    skills_backend = FilesystemBackend(root_dir=skills_dir, virtual_mode=True)
    return SkillsMiddleware(
        backend=skills_backend,
        sources=["/"],
    )
