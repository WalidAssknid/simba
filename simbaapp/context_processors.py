"""
Context processors for SIMBA application
"""
from version import get_version_info

def version_context(request):
    """Add version information to all templates"""
    version_info = get_version_info()
    return {
        'app_version': version_info['version'],
    } 