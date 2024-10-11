from setuptools import setup, find_packages

setup(
    name='appsync_ws_client',
    version='0.1.1',
    packages=find_packages(),
    install_requires=[
        'websocket-client',
    ],
    tests_require=[
        "pytest",
        "pytest-mock",
        "pytest-cov",
    ],
    setup_requires=["pytest-runner"],
    test_suite="tests",
    author='Dhinesh Kumar Sundaram',
    author_email='dhinesh.gs@gmail.com',
    description='A package for connecting to AWS AppSync WebSocket API using graphql subscriptions',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/dhinesh03/python-appsync-ws-client',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.9',
)
