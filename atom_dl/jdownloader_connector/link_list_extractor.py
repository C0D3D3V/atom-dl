import json

from pathlib import Path

from atom_dl.utils.path_tools import PathTools
from atom_dl.my_jd_api import MyJdApi
from atom_dl.config_helper import Config


class LinkListExtractor:
    def __init__(
        self,
        storage_path: str,
        metadata_json_path: str,
    ):
        self.storage_path = storage_path
        self.metadata_json_path = metadata_json_path

    def run(self):
        """
        package structure is like:
        {
            'saveTo': '/home/user/fachbuecher-sachbuecher/Dirk Roßmann – …. dann bin ich auf den Baum geklettert'
            'unknownCount': 1
            'hosts': ['linkcrawlerretry', 'http links']
            'name': 'Dirk Roßmann –  …. dann bin ich auf den Baum geklettert'
            'uuid': 1658137165627
        }
        link structure is like:
        {
            'name': 'cover-73.jpg'
            'packageUUID': 1658137165627
            'uuid': 1658137165628
            'url': 'https://comicmafia.to/wp-content/uploads/2019/01/cover-73.jpg'
        }
        """
        path_to_already_downloaded_links = str(
            Path(Config.get_user_config_directory()) / 'atom-dl' / 'already_downloaded_links.json'
        )
        already_downloaded_links = []
        try:
            with open(path_to_already_downloaded_links, encoding='utf-8') as json_file:
                already_downloaded_links = json.load(json_file)
        except Exception as error:
            already_downloaded_links = []
            print('No already_downloaded_links.json found!')
            print(error)

        print('Try to connect to JDownloader...')
        jd = MyJdApi()
        jd.set_app_key("Atom-Downloader")
        config = Config()
        username = config.get_my_jd_username()
        password = config.get_my_jd_password()
        device_name = config.get_my_jd_device()
        jd.connect(username, password)
        device = jd.get_device(device_name)

        print('Downloading links...')
        links = device.linkgrabber.query_links(
            [
                {
                    "availability": True,
                    "bytesTotal": True,
                    "comment": False,
                    "enabled": False,
                    "host": True,
                    "maxResults": -1,
                    "packageUUIDs": None,
                    "password": False,
                    "priority": False,
                    "startAt": 0,
                    "status": False,
                    "url": True,
                    "variantID": False,
                    "variantIcon": False,
                    "variantName": False,
                    "variants": False,
                }
            ]
        )
        jd.disconnect()

        old_already_downloaded_links = already_downloaded_links[:]
        print('Build link list...')
        idx_link = 0
        while idx_link < len(links):
            link = links[idx_link]
            if idx_link % 333 == 0:
                print(f'{idx_link:05}/{len(links):05}')
            if (
                link["host"] is not None
                and link["host"] == 'http links'
                and link["url"] is not None
                and link["url"].startswith('https://comicmafia.to')
            ):
                idx_link += 1
                continue
            if link['url'] not in old_already_downloaded_links:
                already_downloaded_links.append(link['url'])
            idx_link += 1

        out_file = open(path_to_already_downloaded_links, "w", encoding='utf-8')
        json.dump(already_downloaded_links, out_file, indent=6)
        out_file.close()

    def merge_link_list_with_metadata(self):
        """
        package structure is like:
        {
            'saveTo': '/home/user/fachbuecher-sachbuecher/Dirk Roßmann – …. dann bin ich auf den Baum geklettert'
            'unknownCount': 1
            'hosts': ['linkcrawlerretry', 'http links']
            'name': 'Dirk Roßmann –  …. dann bin ich auf den Baum geklettert'
            'uuid': 1658137165627
        }
        link structure is like:
        {
            'name': 'cover-73.jpg'
            'packageUUID': 1658137165627
            'uuid': 1658137165628
            'url': 'https://comicmafia.to/wp-content/uploads/2019/01/cover-73.jpg'
        }
        """
        with open(self.metadata_json_path, encoding='utf-8') as json_file:
            metadata = json.load(json_file)

        print('Try to connect to JDownloader...')
        jd = MyJdApi()
        jd.set_app_key("Atom-Downloader")
        config = Config()
        username = config.get_my_jd_username()
        password = config.get_my_jd_password()
        device_name = config.get_my_jd_device()
        jd.connect(username, password)
        device = jd.get_device(device_name)
        print('Downloading packages...')
        packages = device.linkgrabber.query_packages(
            [
                {
                    "availableOfflineCount": False,
                    "availableOnlineCount": False,
                    "availableTempUnknownCount": False,
                    "availableUnknownCount": True,
                    "bytesTotal": False,
                    "childCount": False,
                    "comment": False,
                    "enabled": False,
                    "hosts": True,
                    "maxResults": -1,
                    "packageUUIDs": [],
                    "priority": False,
                    "saveTo": True,
                    "startAt": 0,
                    "status": False,
                }
            ]
        )

        print('Downloading links...')
        links = device.linkgrabber.query_links(
            [
                {
                    "availability": True,
                    "bytesTotal": True,
                    "comment": False,
                    "enabled": False,
                    "host": True,
                    "maxResults": -1,
                    "packageUUIDs": None,
                    "password": False,
                    "priority": False,
                    "startAt": 0,
                    "status": False,
                    "url": True,
                    "variantID": False,
                    "variantIcon": False,
                    "variantName": False,
                    "variants": False,
                }
            ]
        )
        jd.disconnect()

        print('Setup identifier...')
        for category in metadata:
            comics = metadata[category]
            for book in comics:
                title = book['title']
                if title is None or title == '':
                    title = 'Title not defined'
                book['identifier'] = PathTools.to_valid_name(category) + '/' + PathTools.to_valid_name(title)

        print('Merge metadata with extracted link list... This is optional and can be skipped at any time!')
        all_packages_in_link_list = []
        idx_pkg = 0
        while idx_pkg < len(packages):
            package = packages[idx_pkg]
            package_links = []
            for link in links:
                if (
                    link["host"] is not None
                    and link["host"] == 'http links'
                    and link["url"] is not None
                    and link["url"].startswith('https://comicmafia.to')
                ):
                    continue
                if link['packageUUID'] == package['uuid']:
                    new_link = {
                        "url": link['url'],
                        "name": link['name'],
                        "host": link['host'],
                        "availability": link['availability'],
                    }
                    if 'bytesTotal' in link:
                        new_link['bytesTotal'] = link['bytesTotal']
                    package_links.append(new_link)

            save_to_path = Path(package['saveTo'])
            # Identify by sanitize category/tilte
            ident_category = save_to_path.parent.name
            ident_title = save_to_path.name
            identifier = ident_category + '/' + ident_title
            new_package = {
                "packageName": package['name'],
                "availability": "online",
                # Todo: mark book links as found and add also offline book links if it was not found in the link list
                "destinationFolder": package['saveTo'],
                "links": package_links,
                "category": ident_category,
            }
            # add all other elements from matching metadata book like: category, cryoto url, description...
            found = False
            for book in metadata[ident_category]:
                if identifier == book['identifier']:
                    found = True
                    for key in book:
                        if key == 'identifier':
                            continue
                        new_package[key] = book[key]
                    break
            if not found:
                print(f'{idx_pkg:05}/{len(packages):05}Found no match in metadata for: {new_package}')

            if idx_pkg % 53 == 0:
                print(f'{idx_pkg:05}/{len(packages):05}')

            all_packages_in_link_list.append(new_package)
            idx_pkg += 1

        out_file = open(str(Path(self.storage_path) / 'merged_metadata_with_linklist.json'), "w", encoding='utf-8')
        json.dump(all_packages_in_link_list, out_file, indent=6)
        out_file.close()
