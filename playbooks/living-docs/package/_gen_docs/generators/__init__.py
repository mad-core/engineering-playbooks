from .api import gen_api
from .changelog import gen_changelog
from .ci_cd import gen_ci_cd
from .config import gen_config
from .scripts import gen_scripts
from .trees import gen_source_tree, gen_test_tree

FULL: dict = {
    "source-tree": gen_source_tree,
    "test-tree": gen_test_tree,
    "api": gen_api,
    "scripts": gen_scripts,
    "changelog": gen_changelog,
}
SKELETON: dict = {
    "config": gen_config,
    "ci-cd": gen_ci_cd,
}
ALL: dict = {**FULL, **SKELETON}

__all__ = [
    "FULL", "SKELETON", "ALL",
    "gen_source_tree", "gen_test_tree", "gen_api",
    "gen_scripts", "gen_config", "gen_ci_cd", "gen_changelog",
]
