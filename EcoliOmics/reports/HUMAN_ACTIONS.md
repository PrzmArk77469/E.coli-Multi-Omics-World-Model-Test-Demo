# Human Actions

These items need account access, contractual review, or a storage decision.
Do not put passwords, API keys, or cloud credentials in this repository.

## Priority 0: Accounts and access

1. **NCBI API key (recommended, not required).** An API key raises E-utilities
   throughput from roughly 3 to 10 requests per second. Set it only in the
   environment as `NCBI_API_KEY`, then rerun the NCBI count collector.
2. **RegulonDB release terms.** The public GraphQL records are being downloaded
   for local analysis, but the website does not expose a clear machine-readable
   redistribution license. Confirm whether derived tables may be redistributed.
3. **EcoCyc access.** An academic subscription or API entitlement is likely
   required. The knowledge layer remains blocked until access terms are known.
4. **KEGG licensing.** Confirm whether the project is academic or commercial
   and whether the intended cache and redistribution are allowed.
5. **BRENDA and SABIO-RK.** Confirm API use, rate limits, and redistribution
   terms before storing kinetic or enzyme records in the integrated layer.

## Priority 1: Repository choices

1. **Proteomics storage.** Decide whether proteomics should retain only
   processed search results and `mzTab`, or also download `mzML` and raw
   instrument files. Raw files can dominate total storage. The automated
   queue currently contains selected processed results only.
2. **Metabolomics storage.** Decide whether to retain processed tables plus
   peak matrices, or mirror vendor raw files from MetaboLights and the
   Metabolomics Workbench. MetaboLights metadata/MAF and 16 Workbench processed
   matrices are local; vendor raw has not been mirrored.
3. **Public redistribution.** The current sequencing and RegulonDB downloads
   are tagged `license_unverified` and are local-analysis only. If public
   redistribution is planned, provide a list of target studies so their terms
   can be reviewed one by one.
4. **Raw proteomics whitelist.** Provide a project or assay whitelist if raw
   instrument files, rather than processed search results, are required.

## Priority 2: Scale-out storage

1. **Object storage.** For multi-TB growth, provide an approved Alibaba Cloud
   OSS, AutoDL, or other object-storage bucket and use environment-based
   credentials. The current local D: volume is suitable for the first core
   batches, not a species-wide raw mirror.
2. **Budget ceiling.** Confirm the maximum monthly storage and outbound traffic
   budget. The download scripts already isolate batches and retain checksums,
   but they cannot make an unbounded budget decision.

## Current safe boundary

The project can continue metadata collection, reference downloads, small
core MG1655 batches, and local-only normalized RegulonDB exports without user
intervention. It should stop before paid database ingestion, redistribution,
or a sustained multi-TB mirror.
