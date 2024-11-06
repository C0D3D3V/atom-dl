from os import path

from setuptools import find_packages, setup

# Get the version from atom_dl/version.py without importing the package
exec(compile(open('atom_dl/version.py').read(), 'atom_dl/version.py', 'exec'))


def readme():
    this_directory = path.abspath(path.dirname(__file__))
    with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
        return f.read()


setup(
    name='atom-dl',
    version=__version__,
    description='A tiny universal atom downloader',
    long_description=readme(),
    long_description_content_type='text/markdown',
    url='https://github.com/c0d3d3v/atom-dl',
    author='c0d3d3v',
    author_email='c0d3d3v@mag-keinen-spam.de',
    license='MIT',
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'atom-dl = atom_dl.main:main',
        ],
    },
    python_requires='>=3.7',
    install_requires=[
        'aiofiles>=0.6.0',
        'aiohttp>=3.8.1',
        'beautifulsoup4>=4.12.3',  # for fixing broken xml (optional dep of lxml)
        'colorama>=0.4.6',
        'colorlog>=6.7.0',
        'lxml>=4.9.1',
        'orjson>=3.8.3',
        'pycryptodomex>=3.20.0',
        'psutil>=6.1.0',
        'rarfile>=4.2',
        'requests>2.28.1',
        'sentry_sdk>=0.13.5',
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License (MIT)',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Education',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search',
        'Topic :: Multimedia :: Video',
        'Topic :: Multimedia :: Sound/Audio',
        'Topic :: Utilities',
    ],
    zip_safe=False,
)
