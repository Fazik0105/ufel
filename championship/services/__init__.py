# championship/services/__init__.py
from .services import (
    generate_league_matches,
    generate_group_playoff,
    generate_playoff_matches,
    get_bracket_data,
    update_playoff_bracket,
    check_playoff_completion
)

__all__ = [
    'generate_league_matches',
    'generate_group_playoff', 
    'generate_playoff_matches',
    'get_bracket_data',
    'update_playoff_bracket',
    'check_playoff_completion'
]