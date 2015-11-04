from setuptools import setup, find_packages

setup(
    name='planner',
    version='0.1',
    description='Plan/Task/WorkOrder model',
    maintainer='Derek Chu',
    maintainer_email='derekzchu@gmail.com',
    packages = find_packages(),

    install_requires=[
        'Flask',
        'sqlalchemy >= 0.9.0',
        'gevent'
    ]
)
