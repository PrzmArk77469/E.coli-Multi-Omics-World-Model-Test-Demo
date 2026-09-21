# Resume Downloads

The three recovered queues are complete as of 2026-09-14:

- `core_mg1655_batch02`: 68/68 files
- `core_mg1655_translatomics01`: 8/8 files
- `pride_processed_batch02`: 300/300 files

The commands below recheck local files and can resume any future additions.
Nonzero `.part` files are preserved and resumed. If direct Windows `curl`
connections fail while Clash TUN is unstable, use the `urllib` backend through
the local mixed proxy.

```powershell
Set-Location D:\CodexApp\Project13\EcoliOmics
$python = 'D:\Python314\python.exe'

# MG1655 core batch 02 (68 files; proxy-capable verification/resume)
& $python .\scripts\download_queue.py --queue .\manifests\download_queue\core_mg1655_batch02_files.tsv --workers 4 --retries 8 --backend urllib --proxy http://127.0.0.1:7897

# MG1655 translatomics 01 (8 files)
& $python .\scripts\download_queue.py --queue .\manifests\download_queue\core_mg1655_translatomics01_files.tsv --workers 2 --retries 8 --backend urllib --proxy http://127.0.0.1:7897

# Resume one ENA file from its existing .part when needed
& $python .\scripts\download_single_resume.py --url URL --destination PATH --expected-bytes BYTES --expected-md5 MD5 --proxy http://127.0.0.1:7897

# PRIDE processed batch 02 (300 files, resume existing queue)
& $python .\scripts\fetch_pride_files.py --queue-prefix pride_processed_batch02 --target-files 300 --min-file-mib 1.0 --max-file-gib 1.0 --budget-gib 8.0 --exclude-prefix pride_processed_batch01 --download --workers 6
```

After all three finish, rebuild the consolidated reports:

```powershell
& $python .\scripts\summarize_downloads.py
```

Status files:

- `reports\downloads\core_mg1655_batch02_files_status.jsonl`
- `reports\downloads\core_mg1655_translatomics01_files_status.jsonl`
- `reports\downloads\pride_processed_download_status.jsonl`
- `reports\coverage\download_inventory.json`
- `reports\coverage\download_inventory.tsv`
- `reports\coverage\DATASET_STATUS.md`
