from atom_dl.types import AtomDlOpts


def gen_extractor_classes():
    """Return a list of supported extractors.
    The order does matter; the first extractor matched is the one handling the URL.
    """
    from .extractors import _ALL_CLASSES

    return _ALL_CLASSES


def gen_extractors(opts: AtomDlOpts):
    """Return a list of an instance of every supported extractor.
    The order does matter; the first extractor matched is the one handling the URL.
    """
    return [klass(opts) for klass in gen_extractor_classes()]


def get_feed_extractor(ie_name):
    """Returns the feed extractor class with the given ie_name"""
    from . import extractors

    return getattr(extractors, f'{ie_name}FIE')
