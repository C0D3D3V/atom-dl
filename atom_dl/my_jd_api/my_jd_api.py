# -*- encoding: utf-8 -*-
# Mirrored from https://github.com/mmarquezs/My.Jdownloader-API-Python-Library
# API Documentation: https://my.jdownloader.org/developers
import base64
import hashlib
import hmac
import orjson
import time

# from urllib.request import urlopen
from urllib.parse import quote
from typing import Dict

import requests

from Cryptodome.Cipher import AES

from atom_dl.my_jd_api.exception import (
    MYJDApiException,
    MYJDConnectionException,
    MYJDDecodeException,
    MYJDDeviceNotFoundException,
)

BS = 16


def PAD(s):
    return s + ((BS - len(s) % BS) * chr(BS - len(s) % BS)).encode()


def UNPAD(s):
    return s[0 : -s[-1]]


class System:
    """
    Class that represents the system-functionality of a Device
    """

    def __init__(self, device):
        self.device = device
        self.url = '/system'

    def exit_jd(self):
        """

        :return:
        """
        resp = self.device.action(self.url + "/exitJD")
        return resp

    def restart_jd(self):
        """

        :return:
        """
        resp = self.device.action(self.url + "/restartJD")
        return resp

    def hibernate_os(self):
        """

        :return:
        """
        resp = self.device.action(self.url + "/hibernateOS")
        return resp

    def shutdown_os(self, force):
        """

        :param force:  Force Shutdown of OS
        :return:
        """
        params = force
        resp = self.device.action(self.url + "/shutdownOS", params)
        return resp

    def standby_os(self):
        """

        :return:
        """
        resp = self.device.action(self.url + "/standbyOS")
        return resp

    def get_storage_info(self):
        """

        :return:
        """
        resp = self.device.action(self.url + "/getStorageInfos?path")
        return resp


class Jd:
    """
    Class that represents the jd-functionality of a Device
    """

    def __init__(self, device):
        self.device = device
        self.url = '/jd'

    def get_core_revision(self):
        """

        :return:
        """
        resp = self.device.action(self.url + "/getCoreRevision")
        return resp


class Update:
    """
    Class that represents the update-functionality of a Device
    """

    def __init__(self, device):
        self.device = device
        self.url = '/update'

    def restart_and_update(self):
        """

        :return:
        """
        resp = self.device.action(self.url + "/restartAndUpdate")
        return resp

    def run_update_check(self):
        """

        :return:
        """
        resp = self.device.action(self.url + "/runUpdateCheck")
        return resp

    def is_update_available(self):
        """

        :return:
        """
        resp = self.device.action(self.url + "/isUpdateAvailable")
        return resp

    def update_available(self):
        self.run_update_check()
        resp = self.is_update_available()
        return resp


class Config:
    """
    Class that represents the Config of a Device
    """

    def __init__(self, device):
        self.device = device
        self.url = '/config'

    def list(self):
        """
        :return:  List<AdvancedConfigAPIEntry>
        """
        resp = self.device.action(self.url + "/list")
        return resp

    def get(self, interface_name, storage, key):
        """
        :param interfaceName: a valid interface name from List<AdvancedConfigAPIEntry>
        :type: str:
        :param storage: 'null' to use default or 'cfg/' + interfaceName
        :type: str:
        :param key: a valid key from from List<AdvancedConfigAPIEntry>
        :type: str:
        """
        params = [interface_name, storage, key]
        resp = self.device.action(self.url + "/get", params)
        return resp

    def set(self, interface_name, storage, key, value):
        """
        :param interfaceName:  a valid interface name from List<AdvancedConfigAPIEntry>
        :type: str:
        :param storage: 'null' to use default or 'cfg/' + interfaceName
        :type: str:
        :param key: a valid key from from List<AdvancedConfigAPIEntry>
        :type: str:
        :param value: a valid value for the given key (see type value from List<AdvancedConfigAPIEntry>)
        :type: Object:
        """
        params = [interface_name, storage, key, value]
        resp = self.device.action(self.url + "/set", params)
        return resp


class DownloadController:
    """
    Class that represents the download-controller of a Device
    https://my.jdownloader.org/developers/#tag_90
    """

    def __init__(self, device):
        self.device = device
        self.url = '/downloadcontroller'

    def force_download(self, link_ids, package_ids):
        """
        :param link_ids: link UUID's.
        :type: list of strings

        :param package_ids: Package UUID's.
        :type: list of strings.
        """
        params = [link_ids, package_ids]
        resp = self.device.action(self.url + "/forceDownload", params)
        return resp

    def get_current_state(self):
        """
        :return: String
        """
        resp = self.device.action(self.url + "/getCurrentState")
        return resp

    def get_speed_in_bps(self):
        """
        :return:  int
        """
        resp = self.device.action(self.url + "/getSpeedInBps")
        return resp

    def pause_downloads(self, value):
        """
        :param value:
        :type: boolean

        :return:  boolean
        """
        params = [value]
        resp = self.device.action(self.url + "/pause", params)
        return resp

    def start_downloads(self):
        """
        :return: boolean
        """
        resp = self.device.action(self.url + "/start")
        return resp

    def stop_downloads(self):
        """
        :return: boolean
        """
        resp = self.device.action(self.url + "/stop")
        return resp


class Linkgrabber:
    """
    Class that represents the linkgrabber of a Device
    https://my.jdownloader.org/developers/#tag_239


    Not yet implemented:

    abort
    abort (jobId)
    addVariantCopy (linkid, destinationAfterLinkID, destinationPackageID, variantID)
    getChildrenChanged (structureWatermark)
    getDownloadFolderHistorySelectionBase
    moveLinks (linkIds, afterLinkID, destPackageID)
    movePackages (packageIds, afterDestPackageId)
    setDownloadPassword (linkIds, packageIds, pass)
    setVariant (linkid, variantID)
    splitPackageByHoster (linkIds, pkgIds)
    startOnlineStatusCheck (linkIds, packageIds)
    """

    def __init__(self, device):
        self.device = device
        self.url = '/linkgrabberv2'

    def add_container(self, type_, content):
        """
        Adds a container to Linkgrabber.

        :param type_: Type of container.
        :type: string.
        :desc: e.g "dlc" this is the file extension of the container file that will be added to jd

        :param content: The container.
        :type: string.
        :desc: The content of the container file as base64 data URL

        :return: myLinkCollectingJob =
                  {
                    "id" = (long)
                  }
        """
        params = [type_, content]
        resp = self.device.action(self.url + "/addContainer", params)
        return resp

    def add_links(self, query) -> Dict:
        """
        Add links to the linkcollector

        :param: query: myAddLinksQuery =
                  {
                    "assignJobID"              = (boolean|null),
                    "autoExtract"              = (boolean|null),
                    "autostart"                = (boolean|null),
                    "dataURLs"                 = (String[]),
                    "deepDecrypt"              = (boolean|null),
                    "destinationFolder"        = (String),
                    "downloadPassword"         = (String),
                    "extractPassword"          = (String),
                    "links"                    = (String),
                    "overwritePackagizerRules" = (boolean|null),
                    "packageName"              = (String),
                    "priority"                 = (Priority),
                    "sourceUrl"                = (String)
                  }

        Priority:
        :type: str: One of:
            HIGHEST
            HIGHER
            HIGH
            DEFAULT
            LOW
            LOWER
            LOWEST


        :return: myLinkCollectingJob =
                  {
                    "id" = (long)
                  }
        """
        resp = self.device.action("/linkgrabberv2/addLinks", [query])
        return resp

    def cleanup(self, link_ids, package_ids, action, mode, selection_type):
        """
        Clean packages and/or links of the linkgrabber list.
        Requires at least a package_ids or link_ids list, or both.

        :param link_ids: link UUID's.
        :type: list of strings

        :param package_ids: Package UUID's.
        :type: list of strings.

        :param action: Action to be done. Actions:
        :type: str: One of:
            DELETE_ALL
            DELETE_DISABLED
            DELETE_FAILED
            DELETE_FINISHED
            DELETE_OFFLINE
            DELETE_DUPE
            DELETE_MODE

        :param mode: Mode to use. Modes:
        :type: str: One of:
            REMOVE_LINKS_AND_DELETE_FILES
            REMOVE_LINKS_AND_RECYCLE_FILES
            REMOVE_LINKS_ONLY

        :param selection_type: Type of selection to use. Types:
        :type: str: One of:
            SELECTED
            UNSELECTED
            ALL
            NONE
        """
        params = [link_ids, package_ids]
        params += [action, mode, selection_type]
        resp = self.device.action(self.url + "/cleanup", params)
        return resp

    def clear_list(self):
        """
        Clears Linkgrabbers list

        :return: bool
        """
        resp = self.device.action(self.url + "/clearList", http_action="POST")
        return resp

    def get_download_urls(self, link_ids, package_ids, url_display_type):
        """
        Gets download urls from Linkgrabber.

        :param link_ids: link UUID's.
        :type: List of strings

        :param package_ids: Package UUID's.
        :type: List of strings.

        :param url_display_type: No clue. Not documented
        :type: List of strings:
            CUSTOM
            REFERRER
            ORIGIN
            CONTAINER
            CONTENT

        :return:  Map<String, List<Long>>
        """
        params = [package_ids, link_ids, url_display_type]
        resp = self.device.action(self.url + "/getDownloadUrls", params)
        return resp

    def get_package_count(self):
        """
        :return: int
        """
        resp = self.device.action("/linkgrabberv2/getPackageCount")
        return resp

    def get_variants(self, link_id):
        """
        Gets the variants of a url/download (not package), for example a youtube
        link gives you a package with three downloads, the audio, the video and
        a picture, and each of those downloads have different variants (audio
        quality, video quality, and picture quality).

        :param params: UUID of the download you want the variants. Ex: 232434
        :type: int

        :return:  myLinkVariant =
                  {
                    "iconKey" = (String),
                    "id"      = (String),
                    "name"    = (String)
                  }
        :rtype: Variants in a list with dictionaries like this one:
        [
            {
                'id': 'M4A_256',
                'name': '256kbit/s M4A-Audio',
            },
            {
                'id': 'AAC_256',
                'name': '256kbit/s AAC-Audio',
            },
        ]
        """
        resp = self.device.action(self.url + "/getVariants", link_id)
        return resp

    def is_collecting(self):
        """
        Boolean status query about the collecting process

        :return: bool
        """
        resp = self.device.action(self.url + "/isCollecting")
        return resp

    def move_to_downloadlist(self, link_ids, package_ids):
        """
        Moves packages and/or links to download list.

        :param link_ids: Link UUID's.
        :type: list of strings.

        :param package_ids: Package UUID's.
        :type: list of strings.
        """
        params = [link_ids, package_ids]
        resp = self.device.action(self.url + "/moveToDownloadlist", params)
        return resp

    def move_to_new_package(self, link_ids, package_ids, new_pkg_name, download_path):
        """
        Moves links and packages to new package

        :param link_ids: Link UUID's.
        :type: list of strings.

        :param package_ids: Package UUID's.
        :type: list of strings.

        :param new_pkg_name: New Package Name
        :type: string.

        :param download_path: Overwrite old download path with this (optional)
        :type: string.
        """
        params = link_ids, package_ids, new_pkg_name, download_path
        resp = self.device.action(self.url + "/movetoNewPackage", params)
        return resp

    def query_link_crawler_jobs(self, query):
        """
        Asks for status about crawler jobs

        :param: query: myLinkCrawlerJobsQuery =
                  {
                    "collectorInfo" = (boolean),
                    "jobIds"        = (long[])
                  }

        :return  List<JobLinkCrawler>:
        :type: myJobLinkCrawler =
                  {
                    "broken"    = (int),
                    "checking"  = (boolean),
                    "crawled"   = (int),
                    "crawlerId" = (long),
                    "crawling"  = (boolean),
                    "filtered"  = (int),
                    "jobId"     = (long),
                    "unhandled" = (int)
                  }
        """
        resp = self.device.action("/linkgrabberv2/queryLinkCrawlerJobs", [query])
        return resp

    def query_links(self, queryParams):
        """
        Get the links in the linkcollector/linkgrabber

        :param queryParams:
                 myCrawledLinkQuery =
                  {
                    "availability" = (boolean),
                    "bytesTotal"   = (boolean),
                    "comment"      = (boolean),
                    "enabled"      = (boolean),
                    "host"         = (boolean),
                    "jobUUIDs"     = (long[]),
                    "maxResults"   = (int),
                    "packageUUIDs" = (long[]),
                    "password"     = (boolean),
                    "priority"     = (boolean),
                    "startAt"      = (int),
                    "status"       = (boolean),
                    "url"          = (boolean),
                    "variantID"    = (boolean),
                    "variantIcon"  = (boolean),
                    "variantName"  = (boolean),
                    "variants"     = (boolean)
                  }

        :return List<CrawledLink>:
        :type: myCrawledLink =
                  {
                    "availability"     = (AvailableLinkState),
                    "bytesTotal"       = (long),
                    "comment"          = (String),
                    "downloadPassword" = (String),
                    "enabled"          = (boolean),
                    "host"             = (String),
                    "name"             = (String),
                    "packageUUID"      = (long),
                    "priority"         = (Priority),
                    "url"              = (String),
                    "uuid"             = (long),
                    "variant"          = (LinkVariant),
                    "variants"         = (boolean)
                  }

        AvailableLinkState
        :type: str: One of:
            ONLINE
            OFFLINE
            UNKNOWN
            TEMP_UNKNOWN

        Priority
        :type: str: One of:
            HIGHEST
            HIGHER
            HIGH
            DEFAULT
            LOW
            LOWER
            LOWEST

        LinkVariant
        :type: str: One of:
          myLinkVariant =
            {
            "iconKey" = (String),
            "id"      = (String),
            "name"    = (String)
            }
        """

        resp = self.device.action(self.url + "/queryLinks", [queryParams])
        return resp

    def query_packages(
        self,
        queryParams,
    ):
        """
        :param queryParams:
            myCrawledPackageQuery =
                  {
                    "availableOfflineCount"     = (boolean),
                    "availableOnlineCount"      = (boolean),
                    "availableTempUnknownCount" = (boolean),
                    "availableUnknownCount"     = (boolean),
                    "bytesTotal"                = (boolean),
                    "childCount"                = (boolean),
                    "comment"                   = (boolean),
                    "enabled"                   = (boolean),
                    "hosts"                     = (boolean),
                    "maxResults"                = (int),
                    "packageUUIDs"              = (long[]),
                    "priority"                  = (boolean),
                    "saveTo"                    = (boolean),
                    "startAt"                   = (int),
                    "status"                    = (boolean)
                  }
        :return List<CrawledPackage>:
        :type CrawledPackage:
            myCrawledPackage =
                  {
                    "bytesTotal"       = (long),
                    "childCount"       = (int),
                    "comment"          = (String),
                    "downloadPassword" = (String),
                    "enabled"          = (boolean),
                    "hosts"            = (String[]),
                    "name"             = (String),
                    "offlineCount"     = (int),
                    "onlineCount"      = (int),
                    "priority"         = (Priority),
                    "saveTo"           = (String),
                    "tempUnknownCount" = (int),
                    "unknownCount"     = (int),
                    "uuid"             = (long)
                  }

        Priority
        :type: str: One of:
            HIGHEST
            HIGHER
            HIGH
            DEFAULT
            LOW
            LOWER
            LOWEST
        """
        resp = self.device.action(self.url + "/queryPackages", queryParams)
        return resp

    def remove_links(self, link_ids, package_ids):
        """
        Remove packages and/or links of the linkgrabber list.
        Requires at least a link_ids or package_ids list, or both.

        :param link_ids: link UUID's.
        :type: list of strings

        :param package_ids: Package UUID's.
        :type: list of strings.
        """
        params = [link_ids, package_ids]
        resp = self.device.action(self.url + "/removeLinks", params)
        return resp

    def rename_link(self, link_id, new_name):
        """
        Renames files related with link_id

        :param link_id: link UUID.
        :type: string

        :param new_name: New filename.
        :type: string.
        """
        params = [link_id, new_name]
        resp = self.device.action(self.url + "/renameLink", params)
        return resp

    def rename_package(self, package_id, new_name):
        """
        Rename package name with package_id

        :param package_id: package UUID.
        :type: string

        :param new_name: New filename.
        :type: string.
        """
        params = [package_id, new_name]
        resp = self.device.action(self.url + "/renamePackage", params)
        return resp

    def set_dl_location(self, directory, package_ids=None):
        """
        Changes the download directory of packages

        :param directory: New directory.
        :type: string.

        :param package_ids: packages UUID's.
        :type: list of strings
        """
        params = [directory, package_ids]
        resp = self.device.action(self.url + "/setDownloadDirectory", params)
        return resp

    def set_enabled(self, enable, link_ids, package_ids):
        """
        Enable or disable packages.

        :param enable: Enable or disable package.
        :type: boolean

        :param link_ids: Links UUID.
        :type: list of strings

        :param package_ids: Packages UUID.
        :type: list of strings.
        """
        params = [enable, link_ids, package_ids]
        resp = self.device.action(self.url + "/setEnabled", params)
        return resp

    def set_priority(self, priority, link_ids, package_ids):
        """
        Sets the priority of links or packages.

        :param package_ids: Package UUID's.
        :type: list of strings.

        :param link_ids: link UUID's.
        :type: list of strings

        Priority
        :type: str: One of:
            HIGHEST
            HIGHER
            HIGH
            DEFAULT
            LOW
            LOWER
            LOWEST
        """
        params = [priority, link_ids, package_ids]
        resp = self.device.action(self.url + "/setPriority", params)
        return resp

    def help(self):
        """
        It returns the API help.
        """
        resp = self.device.action("/linkgrabberv2/help", http_action="GET")
        return resp


class Toolbar:
    """
    Class that represents the toolbar of a Device
    """

    def __init__(self, device):
        self.device = device
        self.url = "/toolbar"
        self.status = None
        self.limit_enabled = None

    def get_status(self):
        resp = self.device.action(self.url + "/getStatus")
        return resp

    def status_downloadSpeedLimit(self):
        self.status = self.get_status()
        if self.status['limit']:
            return 1
        else:
            return 0

    def enable_downloadSpeedLimit(self):
        self.limit_enabled = self.status_downloadSpeedLimit()
        if not self.limit_enabled:
            self.device.action(self.url + "/toggleDownloadSpeedLimit")

    def disable_downloadSpeedLimit(self):
        self.limit_enabled = self.status_downloadSpeedLimit()
        if self.limit_enabled:
            self.device.action(self.url + "/toggleDownloadSpeedLimit")


class Downloads:
    """
    Class that represents the downloads list of a Device
    https://my.jdownloader.org/developers/#tag_127

    Not yet implemented:

    getStopMark -> long
    getStopMarkedLink  ->  DownloadLink
    getStructureChangeCounter (oldCounterValue) ->  long
    moveLinks (linkIds, afterLinkID, destPackageID)
    movePackages (packageIds, afterDestPackageId)
    removeStopMark
    setDownloadPassword (linkIds, packageIds, pass)
    setStopMark (linkId, packageId)
    splitPackageByHoster (linkIds, pkgIds)
    startOnlineStatusCheck (linkIds, packageIds)
    unskip (packageIds, linkIds, filterByReason) -> bool
    """

    def __init__(self, device):
        self.device = device
        self.url = "/downloadsV2"

    def cleanup(self, link_ids, package_ids, action, mode, selection_type):
        """
        Clean packages and/or links of the downloads list.
        Requires at least a package_ids or link_ids list, or both.

        :param link_ids: link UUID's.
        :type: list of strings

        :param package_ids: Package UUID's.
        :type: list of strings.

        :param action: Action to be done. Actions:
        :type: str: One of:
            DELETE_ALL
            DELETE_DISABLED
            DELETE_FAILED
            DELETE_FINISHED
            DELETE_OFFLINE
            DELETE_DUPE
            DELETE_MODE

        :param mode: Mode to use. Modes:
        :type: str: One of:
            REMOVE_LINKS_AND_DELETE_FILES
            REMOVE_LINKS_AND_RECYCLE_FILES
            REMOVE_LINKS_ONLY

        :param selection_type: Type of selection to use. Types:
        :type: str: One of:
            SELECTED
            UNSELECTED
            ALL
            NONE
        """
        params = [link_ids, package_ids]
        params += [action, mode, selection_type]
        resp = self.device.action(self.url + "/cleanup", params)
        return resp

    def force_download(self, link_ids, package_ids):
        """
        Enable force download for Links and/or Packages in downloads list

        :param link_ids: link UUID's.
        :type: list of strings

        :param package_ids: Package UUID's.
        :type: list of strings.

        :return: bool
        """
        params = [link_ids, package_ids]
        resp = self.device.action(self.url + "/forceDownload", params)
        return resp

    def get_download_urls(self, link_ids, package_ids, url_display_type):
        """
        Gets download urls from downloads list.

        :param link_ids: link UUID's.
        :type: List of strings

        :param package_ids: Package UUID's.
        :type: List of strings.

        :param url_display_type: No clue. Not documented
        :type: List of strings:
            CUSTOM
            REFERRER
            ORIGIN
            CONTAINER
            CONTENT

        :return:  Map<String, List<Long>>
        """
        params = [package_ids, link_ids, url_display_type]
        resp = self.device.action(self.url + "/getDownloadUrls", params)
        return resp

    def move_to_new_package(self, link_ids, package_ids, new_pkg_name, download_path):
        """
        Moves links and packages to new package in downloads list

        :param link_ids: Link UUID's.
        :type: list of strings.

        :param package_ids: Package UUID's.
        :type: list of strings.

        :param new_pkg_name: New Package Name
        :type: string.

        :param download_path: Overwrite old download path with this (optional)
        :type: string.
        """
        params = link_ids, package_ids, new_pkg_name, download_path
        resp = self.device.action(self.url + "/movetoNewPackage", params)
        return resp

    def get_package_count(self):
        """
        :return: int
        """
        resp = self.device.action("/linkgrabberv2/getPackageCount")
        return resp

    def query_links(self, queryParams):
        """
        Get the links in the download list
        :param queryParams: LinkQuery
            myLinkQuery =
                  {
                    "addedDate"        = (boolean),
                    "bytesLoaded"      = (boolean),
                    "bytesTotal"       = (boolean),
                    "comment"          = (boolean),
                    "enabled"          = (boolean),
                    "eta"              = (boolean),
                    "extractionStatus" = (boolean),
                    "finished"         = (boolean),
                    "finishedDate"     = (boolean),
                    "host"             = (boolean),
                    "jobUUIDs"         = (long[]),
                    "maxResults"       = (int),
                    "packageUUIDs"     = (long[]),
                    "password"         = (boolean),
                    "priority"         = (boolean),
                    "running"          = (boolean),
                    "skipped"          = (boolean),
                    "speed"            = (boolean),
                    "startAt"          = (int),
                    "status"           = (boolean),
                    "url"              = (boolean)
                  }

        :return  List<DownloadLink>:
          myDownloadLink =
                  {
                    "addedDate"        = (long),
                    "bytesLoaded"      = (long),
                    "bytesTotal"       = (long),
                    "comment"          = (String),
                    "downloadPassword" = (String),
                    "enabled"          = (boolean),
                    "eta"              = (long),
                    "extractionStatus" = (String),
                    "finished"         = (boolean),
                    "finishedDate"     = (long),
                    "host"             = (String),
                    "name"             = (String),
                    "packageUUID"      = (long),
                    "priority"         = (Priority),
                    "running"          = (boolean),
                    "skipped"          = (boolean),
                    "speed"            = (long),
                    "status"           = (String),
                    "statusIconKey"    = (String),
                    "url"              = (String),
                    "uuid"             = (long)
                  }

        Priority
        :type: str: One of:
            HIGHEST
            HIGHER
            HIGH
            DEFAULT
            LOW
            LOWER
            LOWEST
        """
        resp = self.device.action(self.url + "/queryLinks", queryParams)
        return resp

    def query_packages(
        self,
        queryParams,
    ):
        """
        Get the packages in the download list

        :param queryParams: PackageQuery
          myPackageQuery =
                  {
                    "bytesLoaded"  = (boolean),
                    "bytesTotal"   = (boolean),
                    "childCount"   = (boolean),
                    "comment"      = (boolean),
                    "enabled"      = (boolean),
                    "eta"          = (boolean),
                    "finished"     = (boolean),
                    "hosts"        = (boolean),
                    "maxResults"   = (int),
                    "packageUUIDs" = (long[]),
                    "priority"     = (boolean),
                    "running"      = (boolean),
                    "saveTo"       = (boolean),
                    "speed"        = (boolean),
                    "startAt"      = (int),
                    "status"       = (boolean)
                  }
        :return  List<FilePackage>:
          myFilePackage =
                  {
                    "activeTask"       = (String),
                    "bytesLoaded"      = (long),
                    "bytesTotal"       = (long),
                    "childCount"       = (int),
                    "comment"          = (String),
                    "downloadPassword" = (String),
                    "enabled"          = (boolean),
                    "eta"              = (long),
                    "finished"         = (boolean),
                    "hosts"            = (String[]),
                    "name"             = (String),
                    "priority"         = (Priority),
                    "running"          = (boolean),
                    "saveTo"           = (String),
                    "speed"            = (long),
                    "status"           = (String),
                    "statusIconKey"    = (String),
                    "uuid"             = (long)
                  }

        Priority
        :type: str: One of:
            HIGHEST
            HIGHER
            HIGH
            DEFAULT
            LOW
            LOWER
            LOWEST
        """
        resp = self.device.action(self.url + "/queryPackages", queryParams)
        return resp

    def remove_links(self, link_ids, package_ids):
        """
        Remove packages and/or links of the downloads list.
        NOTE: For more specific removal, like deleting the files etc, use the /cleanup api.
        Requires at least a link_ids or package_ids list, or both.

        :param link_ids: link UUID's.
        :type: list of strings

        :param package_ids: Package UUID's.
        :type: list of strings.
        """
        params = [link_ids, package_ids]
        resp = self.device.action(self.url + "/removeLinks", params)
        return resp

    def rename_link(self, link_id, new_name):
        """
        Renames files related with link_id in download list

        :param link_id: link UUID.
        :type: string

        :param new_name: New filename.
        :type: string.
        """
        params = [link_id, new_name]
        resp = self.device.action(self.url + "/renameLink", params)
        return resp

    def rename_package(self, package_id, new_name):
        """
        Rename package name with package_id in download list

        :param package_id: package UUID.
        :type: string

        :param new_name: New filename.
        :type: string.
        """
        params = [package_id, new_name]
        resp = self.device.action(self.url + "/renamePackage", params)
        return resp

    def reset_links(self, link_ids, package_ids):
        """
        Resets links and/or packages in download list

        :param link_ids: link UUID's.
        :type: list of strings

        :param package_ids: Package UUID's.
        :type: list of strings.
        """
        params = [link_ids, package_ids]
        resp = self.device.action(self.url + "/resetLinks", params)
        return resp

    def resume_links(self, link_ids, package_ids):
        """
        Resume links and/or packages in download list

        :param link_ids: link UUID's.
        :type: list of strings

        :param package_ids: Package UUID's.
        :type: list of strings.
        """
        params = [link_ids, package_ids]
        resp = self.device.action(self.url + "/resumeLinks", params)
        return resp

    def set_dl_location(self, directory, package_ids=None):
        """
        Changes the download directory of packages

        :param directory: New directory.
        :type: string.

        :param package_ids: packages UUID's.
        :type: list of strings
        """
        params = [directory, package_ids]
        resp = self.device.action(self.url + "/setDownloadDirectory", params)
        return resp

    def set_enabled(self, enable, link_ids, package_ids):
        """
        Enable or disable packages.

        :param enable: Enable or disable package.
        :type: boolean

        :param link_ids: Links UUID.
        :type: list of strings

        :param package_ids: Packages UUID.
        :type: list of strings.
        """
        params = [enable, link_ids, package_ids]
        resp = self.device.action(self.url + "/setEnabled", params)
        return resp

    def set_priority(self, priority, link_ids, package_ids):
        """
        Sets the priority of links or packages.

        :param package_ids: Package UUID's.
        :type: list of strings.

        :param link_ids: link UUID's.
        :type: list of strings

        Priority
        :type: str: One of:
            HIGHEST
            HIGHER
            HIGH
            DEFAULT
            LOW
            LOWER
            LOWEST
        """
        params = [priority, link_ids, package_ids]
        resp = self.device.action(self.url + "/setPriority", params)
        return resp


class Captcha:
    """
    Class that represents the captcha interface of a Device
    """

    def __init__(self, device):
        self.device = device
        self.url = "/captcha"

    def list(self):
        """
        Get the waiting captchas
        """
        resp = self.device.action(self.url + "/list", [])
        return resp

    def get(self, captcha_id):
        """
        Get the base64 captcha image
        """
        resp = self.device.action(self.url + "/get", (captcha_id,))
        return resp

    def solve(self, captcha_id, solution):
        """
        Solve a captcha
        """
        resp = self.device.action(self.url + "/solve", (captcha_id, solution))
        return resp


class Jddevice:
    """
    Class that represents a JDownloader device and it's functions
    """

    def __init__(self, jd, device_dict):
        """This functions initializates the device instance.
        It uses the provided dictionary to create the device.

        :param device_dict: Device dictionary
        """
        self.name = device_dict["name"]
        self.device_id = device_dict["id"]
        self.device_type = device_dict["type"]
        self.myjd = jd
        self.config = Config(self)
        self.linkgrabber = Linkgrabber(self)
        self.captcha = Captcha(self)
        self.downloads = Downloads(self)
        self.toolbar = Toolbar(self)
        self.downloadcontroller = DownloadController(self)
        self.update = Update(self)
        self.jd = Jd(self)
        self.system = System(self)
        self.__direct_connection_info = None
        self.__refresh_direct_connections()
        self.__direct_connection_enabled = True
        self.__direct_connection_cooldown = 0
        self.__direct_connection_consecutive_failures = 0

    def __refresh_direct_connections(self):
        response = self.myjd.request_api("/device/getDirectConnectionInfos", "POST", None, self.__action_url())
        if (
            response is not None
            and 'data' in response
            and 'infos' in response["data"]
            and len(response["data"]["infos"]) != 0
        ):
            self.__update_direct_connections(response["data"]["infos"])

    def __update_direct_connections(self, direct_info):
        """
        Updates the direct_connections info keeping the order.
        """
        tmp = []
        if self.__direct_connection_info is None:
            for conn in direct_info:
                tmp.append({'conn': conn, 'cooldown': 0})
            self.__direct_connection_info = tmp
            return
        #  We remove old connections not available anymore.
        for i in self.__direct_connection_info:
            if i['conn'] not in direct_info:
                tmp.remove(i)
            else:
                direct_info.remove(i['conn'])
        # We add new connections
        for conn in direct_info:
            tmp.append({'conn': conn, 'cooldown': 0})
        self.__direct_connection_info = tmp

    def enable_direct_connection(self):
        self.__direct_connection_enabled = True
        self.__refresh_direct_connections()

    def disable_direct_connection(self):
        self.__direct_connection_enabled = False
        self.__direct_connection_info = None

    def action(self, path, params=(), http_action="POST"):
        """Execute any action in the device using the postparams and params.
        All the info of which params are required and what are they default value, type,etc
        can be found in the MY.Jdownloader API Specifications ( https://goo.gl/pkJ9d1 ).

        :param params: Params in the url, in a list of tuples. Example:
        /example?param1=ex&param2=ex2 [("param1","ex"),("param2","ex2")]
        :param postparams: List of Params that are send in the post.
        """
        action_url = self.__action_url()
        if (
            not self.__direct_connection_enabled
            or self.__direct_connection_info is None
            or time.time() < self.__direct_connection_cooldown
        ):
            # No direct connection available, we use My.JDownloader api.
            response = self.myjd.request_api(path, http_action, params, action_url)
            if response is None:
                # My.JDownloader Api failed too we assume a problem with the connection or the api server
                # and throw an connection exception.
                raise (MYJDConnectionException("No connection established\n"))
            else:
                # My.JDownloader Api worked, lets refresh the direct connections and return
                # the response.
                if self.__direct_connection_enabled and time.time() >= self.__direct_connection_cooldown:
                    self.__refresh_direct_connections()
                return response['data']
        else:
            # Direct connection info available, we try to use it.
            for conn in self.__direct_connection_info:
                if time.time() > conn['cooldown']:
                    # We can use the connection
                    connection = conn['conn']
                    api = "http://" + connection["ip"] + ":" + str(connection["port"])
                    response = self.myjd.request_api(path, http_action, params, action_url, api)
                    if response is not None:
                        # This connection worked so we push it to the top of the list.
                        self.__direct_connection_info.remove(conn)
                        self.__direct_connection_info.insert(0, conn)
                        self.__direct_connection_consecutive_failures = 0
                        return response['data']
                    else:
                        # We don't try to use this connection for a minute.
                        conn['cooldown'] = time.time() + 60
            # None of the direct connections worked, we set a cooldown for direct connections
            self.__direct_connection_consecutive_failures += 1
            self.__direct_connection_cooldown = time.time() + (60 * self.__direct_connection_consecutive_failures)
            # None of the direct connections worked, we use the My.JDownloader api
            response = self.myjd.request_api(path, http_action, params, action_url)
            if response is None:
                # My.JDownloader Api failed too we assume a problem with the connection or the api server
                # and throw an connection exception.
                raise (MYJDConnectionException("No connection established\n"))
            # My.JDownloader Api worked, lets refresh the direct connections and return
            # the response.
            self.__refresh_direct_connections()
            return response['data']

    def __action_url(self):
        return "/t_" + self.myjd.get_session_token() + "_" + self.device_id


class MyJdApi:
    """
    Main class for connecting to JD API.

    """

    def __init__(self):
        """
        This functions initializates the myjdapi object.

        """
        self.__request_id = int(time.time() * 1000)
        self.__api_url = "https://api.jdownloader.org"
        self.__app_key = "http://git.io/vmcsk"
        self.__api_version = 1
        self.__devices = None
        self.__login_secret = None
        self.__device_secret = None
        self.__session_token = None
        self.__regain_token = None
        self.__server_encryption_token = None
        self.__device_encryption_token = None
        self.__connected = False

    def get_session_token(self):
        return self.__session_token

    def is_connected(self):
        """
        Indicates if there is a connection established.
        """
        return self.__connected

    def set_app_key(self, app_key):
        """
        Sets the APP Key.
        """
        self.__app_key = app_key

    def __secret_create(self, email, password, domain):
        """
        Calculates the login_secret and device_secret

        :param email: My.Jdownloader User email
        :param password: My.Jdownloader User password
        :param domain: The domain , if is for Server (login_secret) or Device (device_secret)
        :return: secret hash

        """
        secret_hash = hashlib.sha256()
        secret_hash.update(email.lower().encode('utf-8') + password.encode('utf-8') + domain.lower().encode('utf-8'))
        return secret_hash.digest()

    def __update_encryption_tokens(self):
        """
        Updates the server_encryption_token and device_encryption_token

        """
        if self.__server_encryption_token is None:
            old_token = self.__login_secret
        else:
            old_token = self.__server_encryption_token
        new_token = hashlib.sha256()
        new_token.update(old_token + bytearray.fromhex(self.__session_token))
        self.__server_encryption_token = new_token.digest()
        new_token = hashlib.sha256()
        new_token.update(self.__device_secret + bytearray.fromhex(self.__session_token))
        self.__device_encryption_token = new_token.digest()

    def __signature_create(self, key, data):
        """
        Calculates the signature for the data given a key.

        :param key:
        :param data:
        """
        signature = hmac.new(key, data.encode('utf-8'), hashlib.sha256)
        return signature.hexdigest()

    def __decrypt(self, secret_token, data):
        """
        Decrypts the data from the server using the provided token

        :param secret_token:
        :param data:
        """
        init_vector = secret_token[: len(secret_token) // 2]
        key = secret_token[len(secret_token) // 2 :]
        decryptor = AES.new(key, AES.MODE_CBC, init_vector)
        decrypted_data = UNPAD(decryptor.decrypt(base64.b64decode(data)))
        return decrypted_data

    def __encrypt(self, secret_token, data):
        """
        Encrypts the data from the server using the provided token

        :param secret_token:
        :param data:
        """
        data = PAD(data.encode('utf-8'))
        init_vector = secret_token[: len(secret_token) // 2]
        key = secret_token[len(secret_token) // 2 :]
        encryptor = AES.new(key, AES.MODE_CBC, init_vector)
        encrypted_data = base64.b64encode(encryptor.encrypt(data))
        return encrypted_data.decode('utf-8')

    def update_request_id(self):
        """
        Updates Request_Id
        """
        self.__request_id = int(time.time())

    def connect(self, email, password):
        """Establish connection to api

        :param email: My.Jdownloader User email
        :param password: My.Jdownloader User password
        :returns: boolean -- True if succesful, False if there was any error.

        """
        self.update_request_id()
        self.__login_secret = None
        self.__device_secret = None
        self.__session_token = None
        self.__regain_token = None
        self.__server_encryption_token = None
        self.__device_encryption_token = None
        self.__devices = None
        self.__connected = False

        self.__login_secret = self.__secret_create(email, password, "server")
        self.__device_secret = self.__secret_create(email, password, "device")
        response = self.request_api("/my/connect", "GET", [("email", email), ("appkey", self.__app_key)])
        self.__connected = True
        self.update_request_id()
        self.__session_token = response["sessiontoken"]
        self.__regain_token = response["regaintoken"]
        self.__update_encryption_tokens()
        self.update_devices()
        return response

    def reconnect(self):
        """
        Reestablish connection to API.

        :returns: boolean -- True if successful, False if there was any error.

        """
        response = self.request_api(
            "/my/reconnect", "GET", [("sessiontoken", self.__session_token), ("regaintoken", self.__regain_token)]
        )
        self.update_request_id()
        self.__session_token = response["sessiontoken"]
        self.__regain_token = response["regaintoken"]
        self.__update_encryption_tokens()
        return response

    def disconnect(self):
        """
        Disconnects from  API

        :returns: boolean -- True if successful, False if there was any error.

        """
        response = self.request_api("/my/disconnect", "GET", [("sessiontoken", self.__session_token)])
        self.update_request_id()
        self.__login_secret = None
        self.__device_secret = None
        self.__session_token = None
        self.__regain_token = None
        self.__server_encryption_token = None
        self.__device_encryption_token = None
        self.__devices = None
        self.__connected = False
        return response

    def update_devices(self):
        """
        Updates available devices. Use list_devices() to get the devices list.

        :returns: boolean -- True if successful, False if there was any error.
        """
        response = self.request_api("/my/listdevices", "GET", [("sessiontoken", self.__session_token)])
        self.update_request_id()
        self.__devices = response["list"]

    def list_devices(self):
        """
        Returns available devices. Use getDevices() to update the devices list.
        Each device in the list is a dictionary like this example:

        {
            'name': 'Device',
            'id': 'af9d03a21ddb917492dc1af8a6427f11',
            'type': 'jd'
        }

        :returns: list -- list of devices.
        """
        return self.__devices

    def get_device(self, device_name=None, device_id=None):
        """
        Returns a jddevice instance of the device

        :param deviceid:
        """
        if not self.is_connected():
            raise (MYJDConnectionException("No connection established\n"))
        if device_id is not None:
            for device in self.__devices:
                if device["id"] == device_id:
                    return Jddevice(self, device)
        elif device_name is not None:
            for device in self.__devices:
                if device["name"] == device_name:
                    return Jddevice(self, device)
        raise (MYJDDeviceNotFoundException("Device not found\n"))

    def request_api(self, path, http_method="GET", params=None, action=None, api=None):
        """
        Makes a request to the API to the 'path' using the 'http_method' with parameters,'params'.
        Ex:
        http_method=GET
        params={"test":"test"}
        post_params={"test2":"test2"}
        action=True
        This would make a request to "https://api.jdownloader.org"
        """
        if not api:
            api = self.__api_url
        data = None
        if not self.is_connected() and path != "/my/connect":
            raise (MYJDConnectionException("No connection established\n"))
        if http_method == "GET":
            query = [path + "?"]
            if params is not None:
                for param in params:
                    if param[0] != "encryptedLoginSecret":
                        query += ["%s=%s" % (param[0], quote(param[1]))]
                    else:
                        query += ["&%s=%s" % (param[0], param[1])]
            query += ["rid=" + str(self.__request_id)]
            if self.__server_encryption_token is None:
                query += [
                    "signature=" + str(self.__signature_create(self.__login_secret, query[0] + "&".join(query[1:])))
                ]
            else:
                query += [
                    "signature="
                    + str(self.__signature_create(self.__server_encryption_token, query[0] + "&".join(query[1:])))
                ]
            query = query[0] + "&".join(query[1:])
            encrypted_response = requests.get(api + query, timeout=50)
        else:
            params_request = []
            if params is not None:
                for param in params:
                    if not isinstance(param, list):
                        params_request += [orjson.dumps(param).decode('utf-8')]  # pylint: disable=maybe-no-member
                    else:
                        params_request += [param]
            params_request = {
                "apiVer": self.__api_version,
                "url": path,
                "params": params_request,
                "rid": self.__request_id,
            }
            data = orjson.dumps(params_request).decode('utf-8')  # pylint: disable=maybe-no-member
            # Removing quotes around null elements.
            data = data.replace('"null"', "null")
            data = data.replace("'null'", "null")
            encrypted_data = self.__encrypt(self.__device_encryption_token, data)
            if action is not None:
                request_url = api + action + path
            else:
                request_url = api + path
            try:
                encrypted_response = requests.post(
                    request_url,
                    headers={"Content-Type": "application/aesjson-jd; charset=utf-8"},
                    data=encrypted_data,
                    timeout=50,
                )
            except requests.exceptions.RequestException as error:
                print(error)
                return None
        if encrypted_response.status_code != 200:
            try:
                error_msg = orjson.loads(encrypted_response.text)  # pylint: disable=maybe-no-member
            except orjson.JSONDecodeError:  # pylint: disable=maybe-no-member
                try:
                    # pylint: disable=maybe-no-member
                    error_msg = orjson.loads(self.__decrypt(self.__device_encryption_token, encrypted_response.text))
                except orjson.JSONDecodeError:  # pylint: disable=maybe-no-member
                    raise MYJDDecodeException(f"Failed to decode response: {encrypted_response.text}")
            msg = (
                "\n\tSOURCE: "
                + error_msg["src"]
                + "\n\tTYPE: "
                + error_msg["type"]
                + "\n------\nREQUEST_URL: "
                + api
                + path
            )
            if http_method == "GET":
                msg += query
            msg += "\n"
            if data is not None:
                msg += "DATA:\n" + data
            raise (MYJDApiException.get_exception(error_msg["src"], error_msg["type"], msg))
        if action is None:
            if not self.__server_encryption_token:
                response = self.__decrypt(self.__login_secret, encrypted_response.text)
            else:
                response = self.__decrypt(self.__server_encryption_token, encrypted_response.text)
        else:
            response = self.__decrypt(self.__device_encryption_token, encrypted_response.text)
        jsondata = orjson.loads(response.decode('utf-8'))  # pylint: disable=maybe-no-member
        if jsondata['rid'] != self.__request_id:
            self.update_request_id()
            return None
        self.update_request_id()
        return jsondata
