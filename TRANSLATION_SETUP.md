# Django Translation Setup Guide

## Current Configuration

The Django app is configured for automatic language detection based on browser `Accept-Language` header with fallback to English.

### Settings Configuration

In `settings.py`:
```python
LANGUAGE_CODE = 'en'

LANGUAGES = [
    ('en', 'English'),
    ('fr', 'Français'),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

USE_I18N = True
USE_L10N = True
```

### Middleware Configuration

In `settings.py` MIDDLEWARE:
```python
'django.middleware.locale.LocaleMiddleware',
```

## Adding New Languages

1. Add language to `LANGUAGES` in `settings.py`:
```python
LANGUAGES = [
    ('en', 'English'),
    ('fr', 'Français'),
    ('es', 'Español'),
    ('pt', 'Português'),
]
```

2. Create directory structure:
```bash
mkdir -p locale/es/LC_MESSAGES
mkdir -p locale/pt/LC_MESSAGES
```

3. Generate translation files:
```bash
python manage.py makemessages -l es
python manage.py makemessages -l pt
```

4. Edit `.po` files in `locale/{lang}/LC_MESSAGES/django.po`

5. Compile translations:
```bash
python manage.py compilemessages
```

## Making HTML Templates Translatable

1. Load i18n tags at top of template:
```html
{% load i18n %}
```

2. Set language attribute:
```html
<html lang="{{ LANGUAGE_CODE }}">
```

3. Mark strings for translation:
```html
<!-- Simple text -->
<h1>{% trans "Welcome to SIMBA" %}</h1>

<!-- Text with variables -->
<p>{% blocktrans %}Hello {{ name }}!{% endblocktrans %}</p>

<!-- Complex blocks -->
{% blocktrans %}
This is a longer paragraph that needs
to be translated as a whole block.
{% endblocktrans %}
```

## Adding French Translations to Other Templates

1. Add `{% load i18n %}` to template top
2. Add `lang="{{ LANGUAGE_CODE }}"` to `<html>` tag
3. Wrap translatable strings with `{% trans "..." %}`
4. Run `python manage.py makemessages -l fr`
5. Edit `locale/fr/LC_MESSAGES/django.po`
6. Add translations:
```
msgid "Your English text"
msgstr "Votre texte français"
```
7. Run `python manage.py compilemessages`

## Translation File Format

In `django.po`:
```
#: template_path:line_number
msgid "English text"
msgstr "Translated text"
```

## Commands Summary

```bash
# Create/update translation files
python manage.py makemessages -l fr
python manage.py makemessages -l es

# Update all languages
python manage.py makemessages --all

# Compile translations
python manage.py compilemessages

# Compile specific language
python manage.py compilemessages --locale=fr
```

## File Structure

```
locale/
├── fr/
│   └── LC_MESSAGES/
│       ├── django.po
│       └── django.mo
├── es/
│   └── LC_MESSAGES/
│       ├── django.po
│       └── django.mo
```

## Testing

Browser language detection works automatically. To test specific languages:
- Change browser language settings
- Use browser developer tools to modify `Accept-Language` header
- Language fallback: unsupported languages → English 