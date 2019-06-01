from setuptools import setup
import sys
if sys.version_info < (3,0):
    sys.exit('Python >= 3.0 required.')
setup(
    name='asfv1',
    version='1.0.7',
    description='Alternate FV-1 Assembler',
    py_modules=['asfv1',],
    url='https://github.com/ndf-zz/asfv1',
    license='GPL',
    author='Nathan Fraser',
    author_email='ndf@metarace.com.au',
    entry_points={
        'console_scripts': [
            'asfv1=asfv1:main',
        ],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development :: Assemblers',
    ],
)
