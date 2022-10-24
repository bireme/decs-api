# decs-api

1. Intended to be used with database with only tables from decs_portal (from current year edition)
2. Run **python manage.py migrate thesaurus** to create API auxiliary tables (from models_full.py)
3. Run **python manage.py saveauxiliardata** to populate auxiliary tables
4. Run **python manage.py search_index --rebuild  -f --models thesaurus** to create elasticsearch indexes
