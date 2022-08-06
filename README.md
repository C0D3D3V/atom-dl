<div align="center">
    <br>
    <h2>Books Downloader</h2>
    <small>A collection of tools to download ebooks from ibooks.to</small> 
    <br>
    <small>Built with ❤︎</small>
</div>

---

### DISCLAIMER, THIS IS ONLY FOR EDUCATIONAL PURPOSES ONLY. 
This project is to be used for educational purposes only. This project is in no way associated with the illegal site ibooks.to, nor does it support the piracy of the media listed there. 
I am not liable for any violation of the law that applies in your country nor for any other illegal actions or problems that may arise from the use of this project.

## 🚀 Setup

1. Install [Python](https://www.python.org/) >=3.7
2. Run `pip install comics-dl` as administrator. </br>
    <sup>(To upgrade from an older Version use `pip install -U comics-dl` instead)</sup>
4. Read the Usage section



### Usage
```
usage: comics-dl [-h] (--version | -dp | -eld | -em | -cm CLEAN_METADATA | -stj SEND_TO_JDOWNLOADER | -rdol | -rfl | -ell EXTRACT_LINK_LIST | -cfd CHECK_FOR_DUPLICATES | -adf ADD_DESCRIPTION_FILES | -ghl GENERATE_HASHES_LIST) [-p PATH]
                [-ud UNTIL_DATE] [-cat [{ebooks,roman-drama,horror,action-horror,krimi-thriller,humor-satire,fantasy-science-fiction,kinderbuch,erotik,historisch,fachbuecher-sachbuecher,magazine-zeitschriften,zeitungen} ...]] [-mplw]
                [-t THREADS] [-scv] [-v]

Books Downloader - A collection of tools to download ebooks from ibooks.to

options:
  -h, --help            show this help message and exit
  --version             Print program version and exit
  -dp, --download-pages
                        Downloads all pages from all catergories if not other defined
  -eld, --extract-last-date
                        Extract the last upload date from the download html files
  -em, --extract-metadata
                        Extract the metadata from the downloaded pages
  -cm CLEAN_METADATA, --clean-metadata CLEAN_METADATA
                        Clean the metadata json from duplicated entires
  -stj SEND_TO_JDOWNLOADER, --send-to-jdownloader SEND_TO_JDOWNLOADER
                        Sends all books in the metadata json to JDownloader
  -rdol, --retry-decryption-of-links
                        Retry decrpytion of links in JDownloader that got aborted
  -rfl, --remove-finished-links
                        Remove already finished (links that got extracted in an older run) links from JDownloader
  -ell EXTRACT_LINK_LIST, --extract-link-list EXTRACT_LINK_LIST
                        Extract all links in linklist from JDownloader and update history file of already "downloaded" links
  -cfd CHECK_FOR_DUPLICATES, --check-for-duplicates CHECK_FOR_DUPLICATES
                        Check downloads for duplicates per book link for all books in a given metadata json
  -adf ADD_DESCRIPTION_FILES, --add-description-files ADD_DESCRIPTION_FILES
                        Add all description files to all book folders for all books in a given metadata json
  -ghl GENERATE_HASHES_LIST, --generate-hashes-list GENERATE_HASHES_LIST
                        Generate a list of all hashes for all uncompressed books in a given metadata json
  -p PATH, --path PATH  Sets the location of the downloaded files. PATH must be an existing directory in which you have read and write access. (default: current working directory)
  -mplw, --max-path-length-workaround
                        If this flag is set, all path are made absolute in order to workaround the max_path limitation on Windows.To use relative paths on Windows you should disable the max_path limitationhttps://docs.microsoft.com/en-
                        us/windows/win32/fileio/maximum-file-path-limitation
  -t THREADS, --threads THREADS
                        Sets the number of download threads. (default: 10)
  -scv, --skip-cert-verify
                        If this flag is set, the SSL certificate is not verified. This option should only be used in non production environments.
  -v, --verbose         Print various debugging information
```


---


## 🏆 Contributing

Do you have a great new feature idea or just want to be part of the project ? Awesome! Every contribution is welcome!


## ⚖️ License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details