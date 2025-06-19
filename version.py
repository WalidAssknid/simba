"""
SIMBA 
"""

__version__ = "1.0.0"
__version_info__ = (1, 0, 0)
__build_date__ = "27/05/2025"
__author__ = "SIMBA Team"

VERSION_HISTORY = {
    "1.0.0": {
        "date": "27/05/2025",
        "features": [
            "Role-based access control per course",
            "Dashboard with teacher/student views",
            "Course and activity limits (3 courses, 10 activities total)",
            "Course enrollment system with role selection",
            "Analytics dashboard with conversation stats",
            "Activity management with visibility controls",
            "User profile management",
            "Chainlit integration for conversations"
        ],
        "breaking_changes": [
            "Removed global user roles",
            "Implemented per-course role system",
            "Changed activity limits from global to per-course"
        ]
    }
}

def get_version():
    """Return the current version string."""
    return __version__

def get_version_info():
    """Return version information as a dictionary."""
    return {
        "version": __version__,
        "version_info": __version_info__,
        "build_date": __build_date__,
        "author": __author__
    }

def get_changelog():
    """Return the version history."""
    return VERSION_HISTORY 