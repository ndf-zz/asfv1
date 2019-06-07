import setuptools
import sys
if sys.version_info < (3,0):
    sys.exit('Python >= 3.0 required.')

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="asfv1",
    version="1.0.8",
    author="Nathan Fraser",
    author_email="ndf@metarace.com.au",
    description="Alternate FV-1 Assembler",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ndf-zz/asfv1",
    entry_points={
        'console_scripts': [
            'asfv1=asfv1:main',
        ],
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
	'Environment :: Console',
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development :: Assemblers',
    ],
)

