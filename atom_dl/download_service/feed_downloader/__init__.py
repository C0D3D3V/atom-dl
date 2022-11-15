def gen_downloader_classes():
    """Return a list of supported downloaders.
    The order does matter; the first downloader matched is the one handling the URL.
    """
    from .downloaders import _ALL_CLASSES

    return _ALL_CLASSES


def gen_downloaders():
    """Return a list of an instance of every supported downloader.
    The order does matter; the first downloader matched is the one handling the URL.
    """
    return [klass() for klass in gen_downloader_classes()]


def get_feed_downloader(ie_name):
    """Returns the feed downloader class with the given ie_name"""
    from . import downloaders

    return getattr(downloaders, f'{ie_name}FD')
