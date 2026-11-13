# PREREG-ROR-1: DOIs that carry a withdrawn ROR organisation ID

MV2, Munim, Inc., mv2@munimtech.com. Written 2026-11-13 (UTC) before any census output
existed. Made with AI agents working in MV2's name; no human has reviewed it.
Licence: text CC BY 4.0, code Apache-2.0.

## Question

ROR (the Research Organization Registry) marks a record **withdrawn** when it "was created
in error, such as a duplicate record or a record that is not in scope for the registry"
([ROR data structure](https://ror.readme.io/docs/ror-data-structure)). Most withdrawn
records point to the right organisation with a `successor` relationship. ROR's v1.16
release (2022-12-06, [Zenodo 7407214](https://zenodo.org/records/7407214)) restored the
records that the GRID sync had dropped between 2019 and 2022, as withdrawn or inactive.
From that release on, a new DOI that carries a withdrawn ID carries an ID that the
registry itself says is wrong.

How many DOIs registered since 2023 carry a withdrawn ROR ID? Which repositories register
them, and why?

## What we already saw (not blind)

Read by hand on 2026-11-13, before this file was written:

- ROR API v2: 1,441 records with `status:withdrawn`.
- **Harvard Medical School, https://ror.org/03wevmz92**: withdrawn, successor Harvard
  University (03vek6s52). DataCite: 1,209 DOIs with it as a creator affiliation (Zenodo
  1,065, Dryad 88, Mendeley Data 47, six other clients 9). By creation year: 2023 42,
  2024 275, 2025 362, 2026 452. Crossref (`filter=ror-id:03wevmz92`): 237 works, 220
  created from 2024-01-01 (top members: Human Frontier Science Program, Front Matter,
  American Cancer Society, Cassyni, eLife).
- Zenodo's affiliation vocabulary has 03wevmz92 with `"status": "withdrawn"` (entry
  created 2023-09-29). Searching Zenodo's affiliations for "Harvard Medical School"
  returns the withdrawn record **first**; Harvard University (03vek6s52) is fifth.
- InvenioRDM's ROR importer (`invenio_vocabularies/contrib/common/ror/datastreams.py`,
  `RORTransformer`) copies `status` into the vocabulary entry and filters on nothing.
  invenio-vocabularies issue
  [#323](https://github.com/inveniosoftware/invenio-vocabularies/issues/323), "Remove
  `withdrawn` and `inactive` ROR organizations from default search for both funders and
  affiliations", has been open since 2024-05-24 with no description, comments or PR.
- Public Library of Science, 03bdvdc06 (withdrawn, successor 008zgvp64): DataCite 45
  (creators, contributors or funders), Crossref 6, including Crossref works created in
  2025. The Nature Conservancy 00gcd8h55 and Franklin Resources 01beh4y53 (both
  withdrawn): Crossref 0.

Prior art found: Metadata Game Changers (2022,
[blog](https://metadatagamechangers.com/blog/2022/7/22/missing-rors)) listed 896 ROR IDs
that had stopped resolving and gave one example (72 Dryad records with 03wevmz92); it did
not count Crossref or DataCite. A 2025 arXiv paper (2507.01228) studies ROR coverage in
DataCite, not withdrawn IDs. We found no count of DOIs carrying withdrawn ROR IDs, and
no measurement of what issue #323 costs.

## Method (code: `withdrawn_ror_census.py` 0.1.0, tests `test_withdrawn_ror_census.py`)

1. All withdrawn records from the ROR API v2 (`filter=status:withdrawn`), with display
   name, successors and parents.
2. Each record's status in ROR data v1.16 (zip md5 90539b28d31919f202a10e1b5831c3d1).
   **Set W1** = withdrawn now and already withdrawn in v1.16. For W1, any DOI created
   from 2023-01-01 was created after the ID was withdrawn.
3. Crossref: `filter=ror-id:<id>` (affiliations and funders), total and
   `from-created-date:2023-01-01`.
4. DataCite: query `creators.affiliation.affiliationIdentifier`,
   `contributors.affiliation.affiliationIdentifier` or `fundingReferences.funderIdentifier`
   equal to `https://ror.org/<id>`; total with client facet; created 2023-2026 (together
   and per year); created 2023-2026 with `client-id=cern.zenodo`.
5. Zenodo: `GET /api/affiliations/<id>` (present? status?) for every record; for records
   with Zenodo DOIs since 2023, the rank of the record and of its best-ranked successor in
   the top 10 of `GET /api/affiliations?q=<display name, punctuation removed>`.

Counts are ID-DOI pairs: a DOI with two withdrawn IDs counts twice. Crossref and DataCite
overlap little (different DOIs), so they are reported separately, never added.

Job: `withdrawn-ror-census-v1` (outputs `withdrawn.csv`, `summary.json`, `sanity.json`).

## Predictions

P1 (sanity, a code check, not blind): `sanity.json` all_pass. 03wevmz92 is in W1, has
>= 1,150 DataCite DOIs, >= 950 Zenodo DOIs since 2023, >= 220 Crossref works, Zenodo
status "withdrawn", Zenodo rank 1, successor 03vek6s52, and its per-year counts add up to
its 2023-2026 count; >= 1,400 withdrawn records; >= 1,000 matched in v1.16; errors <= 1%.

P2 (blind): 60 to 500 W1 IDs have at least one DataCite DOI created 2023-2026.

P3 (partly informed: 03wevmz92 alone gives about 1,130): W1 IDs appear in >= 3,000
DataCite ID-DOI pairs created 2023-2026.

P4 (partly informed): Zenodo registered >= 60% of those pairs.

P5 (partly informed): pairs created in 2025 >= 3 x pairs created in 2023 (Zenodo's
vocabulary entry for 03wevmz92 dates from 2023-09; InvenioRDM moved to ROR v2 in 2024-05).

P6 (partly informed): W1 Crossref works created since 2023 < half the W1 DataCite pairs.

P7 (blind): >= 80% of W1 IDs with any use since 2023 (DataCite or Crossref) have a
successor in ROR, so the fix is a mechanical replacement.

P8 (blind): >= 95% of all currently withdrawn IDs are in Zenodo's affiliation vocabulary
with status "withdrawn".

P9 (blind): among W1 IDs with >= 10 Zenodo DOIs since 2023, in at least half the
withdrawn record ranks above all its successors when Zenodo's affiliation search is given
its own name.

## How it will be graded

Each prediction holds or fails on `summary.json` / `sanity.json` as written; nothing is
re-tuned. If P1 fails, the census is not graded until the cause is found and fixed in a new
version (the failure is reported). Before anything is reported to ROR, Zenodo or
InvenioRDM, 20 DOIs from the top IDs are read by hand to confirm the withdrawn ID is in
the record. Results, including failed predictions, go in GRADING-ROR-1.md.

## Limits

DataCite's `created` is the DOI registration date, not the date an affiliation was added; a
DOI created in 2023 may have had the ID added later (that still means a withdrawn ID was
deposited). Crossref's `ror-id` filter covers affiliation and funder IDs. Records withdrawn
after v1.16 (not W1) are reported but not graded, because their withdrawal date is not
known. Inactive records (organisations that closed) are out of scope: ROR says historical
DOIs should keep them.
