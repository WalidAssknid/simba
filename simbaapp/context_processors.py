"""
Context processors for SIMBA application
"""
from version import get_version_info
from django.conf import settings
from django.utils import translation

def version_context(request):
    """Add version information to all templates"""
    version_info = get_version_info()
    return {
        'app_version': version_info['version'],
    }

def language_context(request):
    """Add language information to all templates"""
    current_language = request.session.get('django_language', request.session.get('_language_override', 'en'))
    
    if not current_language:
        current_language = translation.get_language() or 'en'
    
    translation.activate(current_language)
    
    return {
        'LANGUAGES': settings.LANGUAGES,
        'CURRENT_LANGUAGE': current_language,
    } 