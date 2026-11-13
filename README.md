# withdrawn-ror-census

How many DOIs carry an organisation ID that the Research Organization Registry (ROR) has
**withdrawn**, meaning the record was created in error (for example, a duplicate)?

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name.
Code: Apache-2.0. Text and data: CC BY 4.0.

## First example

ROR withdrew Harvard Medical School's record **https://ror.org/03wevmz92**; its successor
is Harvard University (https://ror.org/03vek6s52). On 2026-11-13 the withdrawn ID was
still in:

- **1,209 DataCite DOIs** as a creator affiliation: 1,065 from Zenodo, 88 from Dryad and
  47 from Mendeley Data. Use is growing: 42 created in 2023, 275 in 2024, 362 in 2025
  and 452 so far in 2026.
- **237 Crossref works** (`https://api.crossref.org/works?filter=ror-id:03wevmz92`),
  220 of them created since 2024.

One likely cause: Zenodo's affiliation search, which is built on InvenioRDM, still offers
withdrawn records. Searching it for "Harvard Medical School" returns the withdrawn record
first (`"status": "withdrawn"`), and Harvard University fifth. InvenioRDM's ROR importer
keeps every status, and the request to hide withdrawn records from default search,
[invenio-vocabularies #323](https://github.com/inveniosoftware/invenio-vocabularies/issues/323),
has been open since May 2024.

## The census

[PREREG-ROR-1.md](PREREG-ROR-1.md) pre-registers a census of all 1,441 withdrawn ROR
records: Crossref and DataCite counts, Zenodo's share, the trend since 2023, and whether
Zenodo ranks each withdrawn record above its successor. It sets out nine predictions,
written before any census output existed.

```
pip install ijson
python -m unittest -v test_withdrawn_ror_census
python withdrawn_ror_census.py --data-dir ./data --out-dir ./out
```

It uses only public APIs: ROR v2, Crossref REST (with a mailto), DataCite REST and
Zenodo's affiliations API. It also uses the ROR v1.16 data dump from Zenodo. The run is
paced to stay within each API's rate limits.

## Fixing a record

If you deposit DOIs: look up each ROR ID you use at `https://api.ror.org/v2/organizations/<id>`.
If its `status` is `withdrawn`, replace it with the ID in its `successor` relationship.
Inactive IDs are different: ROR says DOIs should keep them for historical accuracy.
