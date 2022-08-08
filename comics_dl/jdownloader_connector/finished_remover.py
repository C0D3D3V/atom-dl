import json
import os

from pathlib import Path

from comics_dl.my_jd_api import MyJdApi
from comics_dl.download_service.path_tools import PathTools
from comics_dl.config_service.config_helper import ConfigHelper


class FinishedRemover:
    def __init__(self, storage_path: str, categories: [str]):
        self.storage_path = storage_path
        self.categories = categories

    def run(self):
        """
        package structure is like:
        {
            'saveTo': '/home/user/fachbuecher-sachbuecher/Dirk Roßmann – …. dann bin ich auf den Baum geklettert'
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
            Path(ConfigHelper.get_user_config_directory()) / 'comics-dl' / 'already_downloaded_links.json'
        )
        already_downloaded_links = []
        try:
            with open(path_to_already_downloaded_links, encoding='utf-8') as json_file:
                already_downloaded_links = json.load(json_file)
        except Exception as error:
            already_downloaded_links = []
            print('No already_downloaded_links.json found!')
            print(error)
            return

        # Todo build comperator that take "aktuelle Ausgabe XXXX" and spezial characters into account
        # print('Collecting already downloaded filenames...')
        # all_filenames = []
        # for category in self.categories:
        #    category_path = PathTools.path_of_download_category(self.storage_path, category)
        #    book_title_list = os.listdir(category_path)
        #    for book_title in book_title_list:
        #        book_path = str(Path(category_path) / book_title)
        #        if not os.path.isdir(book_path):
        #            continue
        #
        #        file_list = os.listdir(book_path)
        #        for filename in file_list:
        #            if filename == 'description.txt':
        #                continue
        #            # ext = filename.split('.')[-1]
        #            # if ext in ['.txt', 'png', 'jpg', 'jpeg', 'gif']:
        #            #     continue
        #            all_filenames.append(filename)

        print('Try to connect to JDownloader...')
        jd = MyJdApi()
        jd.set_app_key("Comics-Downloader")
        config = ConfigHelper()
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

        print('Downloading packages...')
        packages = device.linkgrabber.query_packages(
            [
                {
                    "availableOfflineCount": False,
                    "availableOnlineCount": True,
                    "availableTempUnknownCount": False,
                    "availableUnknownCount": False,
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

        availible_count_package_map = {}
        removed_count_package_map = {}
        hosts_count_package_map = {}
        save_to_package_map = {}
        for package in packages:
            availible_count_package_map[package['uuid']] = package['onlineCount']
            save_to_package_map[package['uuid']] = package['saveTo']
            hosts_count_package_map[package['uuid']] = len(package['hosts'])
            if 'http links' in package['hosts']:
                hosts_count_package_map[package['uuid']] -= 1

        print('Build link list...')

        links_to_remove = []
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

            if os.path.exists(str(Path(save_to_package_map[link['packageUUID']]) / link['name'])):
                # if link['name'] in all_filenames:
                idx_link += 1
                if link['packageUUID'] in removed_count_package_map:
                    removed_count_package_map[link['packageUUID']] += 1
                else:
                    removed_count_package_map[link['packageUUID']] = 1
                links_to_remove.append(link['uuid'])
                continue

            if link["url"] is not None:
                full_link = link['url']
                cutted_link = full_link[: full_link.rfind('/')]
                if full_link in already_downloaded_links or cutted_link in already_downloaded_links:
                    links_to_remove.append(link['uuid'])
                    if link['packageUUID'] in removed_count_package_map:
                        removed_count_package_map[link['packageUUID']] += 1
                    else:
                        removed_count_package_map[link['packageUUID']] = 1
            idx_link += 1

        packages_to_remove = []
        for uuid, removed_count in removed_count_package_map.items():
            if hosts_count_package_map[uuid] * removed_count + 1 >= availible_count_package_map[uuid]:
                packages_to_remove.append(uuid)

        print(f'Removing {len(links_to_remove)} Links')
        print(f'Removing {len(packages_to_remove)} Packages')
        device.linkgrabber.remove_links(links_to_remove, packages_to_remove)

        jd.disconnect()
