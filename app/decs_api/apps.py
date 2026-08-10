from django.apps import AppConfig


class TastypieConfig(AppConfig):
    """Pin tastypie's models to AutoField.

    tastypie ships no AppConfig of its own, so the project-wide
    DEFAULT_AUTO_FIELD (BigAutoField) would apply to its models — but its
    shipped migrations created plain AutoField columns, and the existing
    database matches those. Without this, `makemigrations` reports drift and
    wants to ALTER tastypie_apikey.id / tastypie_apiaccess.id for no reason.
    """

    name = "tastypie"
    default_auto_field = "django.db.models.AutoField"
