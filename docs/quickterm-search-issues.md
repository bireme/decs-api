- ~~Busca usando \* não esta funcionando quando tem mais de um termo, exemplo: sindrome respi\*~~ **Resolvido** — as buscas truncadas (com `*`) agora são montadas palavra a palavra (`truncated_word_must` em `esearch_functions.py`): cada palavra é um `must` AND no campo analisado `term_string`, sendo que a palavra com `*` usa `wildcard` e as demais usam `match`. Isso reproduz a semântica "palabra a palabra" da API antiga e casa termos não contíguos (ex.: `transtorno espectro au*` → "Transtorno **do** Espectro Autista", pulando o "do"). A fase "top 2" (op_prefix `103`) usa a mesma lógica e é ordenada por termo preferido e depois alfabeticamente (byte order) para um top-2 determinístico.

  https://srv.bvsalud.org/decsQuickTerm/search?query=doenca%20de%20cha*

  https://srv.bvsalud.org/decsQuickTerm/search?query=transtorno%20espectro%20au*
- ~~Primeiros descritores retornados não são os mais relevantes~~ **Resolvido** — a query "top 2" agora usa `match_phrase` no campo analisado `term_string`, a ordenação alfabética usa campo keyword sem normalizer (byte order), e os resultados top-2 não são mais removidos da lista alfabética, reproduzindo o comportamento da API antiga.

  https://srv.bvsalud.org/decsQuickTerm/search?query=sindrome%20respiratoria

  https://decs-api.bvsalud.org/api/thesaurus/quickterm/?query=sindrome%20respiratoria
