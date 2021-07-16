import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    python_requires='>=2.6',
    name="asfv1",
    version="1.2.7",
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
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Topic :: Software Development :: Assemblers',
    ],
    py_modules=['asfv1',],
)

