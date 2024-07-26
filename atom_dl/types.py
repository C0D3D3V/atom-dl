from dataclasses import dataclass


@dataclass
class AtomDlOpts:
    process_latest_feed: bool
    path_to_job_defs: str
    feed_jdownloader: bool
    extract_archives: bool

    do_not_auto_start_downloading: bool

    max_parallel_downloads: int

    allow_insecure_ssl: bool
    use_all_ciphers: bool
    skip_cert_verify: bool

    verbose: bool
    quiet: bool
    log_to_file: bool
    log_file_path: str

    max_reties_of_downloads: int = 3
