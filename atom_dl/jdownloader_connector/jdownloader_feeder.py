import json
import urllib
import logging
import requests

from requests.exceptions import RequestException
from atom_dl.utils.path_tools import PathTools


class JDownloaderFeeder:
    """
    Encapsulates the recurring logic for sending out requests to the JDownloader
    """

    stdHeader = {
        'User-Agent': ('Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0'),
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': 'https://comicmafia.to/',
    }

    def __init__(
        self,
        storage_path: str,
        metadata_json_path: str,
        categories: [str],
        skip_cert_verify: bool,
    ):
        self.storage_path = storage_path
        self.metadata_json_path = metadata_json_path
        self.skip_cert_verify = skip_cert_verify
        self.categories = categories
        self.url_base = 'http://127.0.0.1:9666/'

        logging.getLogger("requests").setLevel(logging.WARNING)

    def add_book_to_jdownloader(self, book: {}, category: str):
        """
        calls: http://127.0.0.1:9666/flash/add
        with GET parameters:
            urls: string
            passwords: string
            source: string - we do not use this instead we use the referer
            comment: string
            dir: string - destination directory
            package: string - package name
        returns `success` or `failed errortext`

        parameter book looks like:
        {
            "title": title,
            "upload_date": upload_date,
            "extra_info": extra_info,
            "description": description,
            "crypt_download_link": crypt_download_link,
            "image_link": image_link,
        }
        """
        session = requests.Session()

        urls = " ".join(link for link in book['crypt_download_links'])
        if urls is None or urls == '':
            print('Error: No download link!')
            return
        if book['image_link'] is not None and book['image_link'] != 'None':
            urls += f' {book["image_link"]}'

        book_title = book['title']
        if book_title is None or book_title == '':
            book_title = "Title not defined"
        save_to = PathTools.path_of_download_book(self.storage_path, category, book_title)
        data = {
            "urls": urls,
            "package": book_title,
            "dir": save_to,
            "passwords": "comicmafia.to",
        }

        package_parameters = self.recursive_urlencode(data)
        jdownloader_url = f'{self.url_base}flash/add'

        try:
            response = session.post(
                jdownloader_url,
                data=package_parameters,
                headers=self.stdHeader,
                verify=self.skip_cert_verify,
                timeout=60,
            )
        except RequestException as error:
            raise ConnectionError(f"Connection error: {str(error)}") from None

        self.check_response_code(response)

    def check_jdownloader(self) -> object:
        """
        calls: http://127.0.0.1:9666/jdcheckjson
        with no GET parameters:
        returns json with version, deviceId and name
        """
        try:
            response = requests.get(
                f'{self.url_base}jdcheckjson',
                headers=self.stdHeader,
                verify=self.skip_cert_verify,
                timeout=60,
            )
        except RequestException as error:
            raise ConnectionError(f"Connection error: {str(error)}") from None

        self.check_response_code(response)

        # Try to parse the JSON
        try:
            response_extracted = response.json()
        except ValueError:
            raise RequestRejectedError('The JDownloader API does not appear to be available at this time.') from None
        except Exception as error:
            raise RequestRejectedError(
                'An Unexpected Error occurred while trying'
                + ' to parse the json response! JDownloader'
                + f' response: {response.text}.\nError: {error}'
            ) from None

        print(f"Connected to: {response_extracted['name']}")

    def check_response_code(self, response):
        if response.status_code not in [200, 204]:
            raise RequestRejectedError(
                'An Unexpected Error happened!'
                + f' Status-Code: {str(response.status_code)}'
                + f'\nHeader: {response.headers}'
                + f'\nResponse: {response.text}'
            )

    def ask_for_next_batch(self):
        result = 'No'
        while result.upper() not in ['NEXT', 'BACK']:
            result = input("Type 'NEXT' to send next 50 comics to JDownloader: ")
        if result.upper() == 'BACK':
            return False
        return True

    def recursive_urlencode(self, data):
        """URL-encode a multidimensional dictionary.
        @param data: the data to be encoded
        @returns: the url encoded data
        """

        def recursion(data, base=None):
            if base is None:
                base = []
            pairs = []

            for key, value in data.items():
                new_base = base + [key]
                if hasattr(value, 'values'):
                    pairs += recursion(value, new_base)
                else:
                    new_pair = None
                    if len(new_base) > 1:
                        first = urllib.parse.quote(new_base.pop(0))
                        rest = map(urllib.parse.quote, new_base)
                        new_pair = f"{first}[{']['.join(rest)}]={urllib.parse.quote(str(value))}"
                    else:
                        new_pair = f'{urllib.parse.quote(str(key))}={urllib.parse.quote(str(value))}'
                    pairs.append(new_pair)
            return pairs

        return '&'.join(recursion(data))

    def run(self):
        with open(self.metadata_json_path, encoding='utf-8') as json_file:
            data = json.load(json_file)

        self.check_jdownloader()

        for category in self.categories:
            if category not in data:
                continue
            idx_book = 0
            while idx_book < len(data[category]):
                book = data[category][idx_book]
                self.add_book_to_jdownloader(book, category)
                print(f"Added {idx_book + 1}/{len(data[category])}: {book['title']}")
                if idx_book % 50 == 0:
                    if not self.ask_for_next_batch():
                        idx_book -= 50
                        if idx_book < 0:
                            idx_book = 0
                        continue
                idx_book += 1


class RequestRejectedError(Exception):
    pass
