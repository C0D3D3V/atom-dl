from comics_dl.my_jd_api import MyJdApi
from comics_dl.config_service.config_helper import ConfigHelper


class DecryptionRetryer:
    def ask_for_next_batch(self):
        result = 'No'
        while result.upper() not in ['NEXT']:
            result = input("Type 'NEXT' to send next 50 comics to JDownloader: ")
        return True

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

        jd = MyJdApi()
        jd.set_app_key("Comics-Downloader")
        config = ConfigHelper()
        username = config.get_my_jd_username()
        password = config.get_my_jd_password()
        device_name = config.get_my_jd_device()
        jd.connect(username, password)
        device = jd.get_device(device_name)
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

        retry_packages = []
        retry_packages_uuids = []
        for package in packages:
            if package['unknownCount'] > 0 and 'linkcrawlerretry' in package['hosts']:
                retry_packages.append(package)
                retry_packages_uuids.append(package['uuid'])

        links = device.linkgrabber.query_links(
            [
                {
                    "availability": False,
                    "bytesTotal": False,
                    "comment": False,
                    "enabled": False,
                    "host": False,
                    "maxResults": -1,
                    "packageUUIDs": retry_packages_uuids,
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

        pkg_idx = 0
        while pkg_idx < len(retry_packages):
            retry_package = retry_packages[pkg_idx]
            urls = ""
            for link in links:
                if link['packageUUID'] == retry_package['uuid']:
                    if urls == "":
                        urls = link['url']
                    else:
                        urls += f" {link['url']}"
            new_package = {
                "autostart": False,
                "destinationFolder": retry_package['saveTo'],
                "downloadPassword": 'comicmafia.to',
                "extractPassword": 'comicmafia.to',
                "links": urls,
                "overwritePackagizerRules": True,
                "packageName": retry_package['name'],
                "priority": "DEFAULT",
                "sourceUrl": 'https://comicmafia.to/',
            }

            print('Remove and re-add package: ')
            print(new_package)
            device.linkgrabber.remove_links([], [retry_package['uuid']])
            device.linkgrabber.add_links([new_package])

            if pkg_idx % 50 == 0:
                self.ask_for_next_batch()
            pkg_idx += 1

        jd.disconnect()
