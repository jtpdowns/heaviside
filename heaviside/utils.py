# Copyright 2016 The Johns Hopkins University Applied Physics Laboratory
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from io import IOBase, StringIO
from collections import Mapping
from pathlib import Path
from contextlib import contextmanager

from boto3.session import Session

@contextmanager
def read(obj):
    """Context manager for reading data from multiple sources as a file object

    Args:
        obj (string|Path|file object): Data to read / read from
                                  If obj is a file object, this is just a pass through
                                  If obj is a Path object, this is similar to obj.open()
                                  If obj is a string, this creates a StringIO so
                                     the data can be read like a file object

    Returns:
        file object: File handle containing data
    """
    is_open = False
    if isinstance(obj, Path):
        fh = obj.open()
        is_open = True
    elif isinstance(obj, str):
        fh = StringIO(obj)
        fh.name = '<string>'
    elif isinstance(obj, IOBase):
        fh = obj
    else:
        raise Exception("Unknown input type {}".format(type(obj).__name__))
    
    try:
        yield fh
    finally:
        if is_open:
            fh.close()

def create_session(**kwargs):
    """Create a Boto3 session from multiple different sources

    Basic file format / dictionary format:
    {
        'aws_secret_key': '',
        'aws_access_key': '',
        'aws_region': '',
        'aws_account_id': ''
    }

    Note: If no arguments are given, a Boto3 session is created and it will attempt
          to figure out this information for itself, from predefined locations.

    Args:
        credentials (dict|fh|Path|json string): source to load credentials from
                                                If a dict, used directly
                                                If a fh, read and parsed as a Json object
                                                If a Path, opened, read, and parsed as a Json object
                                                If a string, parsed as a Json object

        Note: The following will override the values in credentials if they exist
        region / aws_region (string): AWS region to connect to
        secret_key / aws_secret_key (string): AWS Secret Key
        access_key / aws_access_key (string): AWS Access Key

        Note: The following will be derived from the AWS Session if not provided
        account_id / aws_account_id (string): AWS Account ID

    Returns:
        (Boto3 Session, account_id) : Boto3 session populated with given credentials and
                                      AWS Account ID (either given or derived from session)
    """
    if len(kwargs) == 0:
        session = Session() # Let boto3 try to resolve the keys iteself, potentially from EC2 meta data
        account_id = None
    else:
        credentials = kwargs.get('credentials', {})
        if isinstance(credentials, Mapping):
            pass
        if isinstance(credentials, Path):
            with credentials.open() as fh:
                credentials = json.load(fh)
        elif isinstance(credentials, str):
            credentials = json.loads(credentials)
        elif isinstance(credentials, IOBase):
            credentials = json.load(credentials)
        else:
            raise Exception("Unknown credentials type: {}".format(type(credentials).__name__))

        def locate(names, locations):
            for location in locations:
                for name in names:
                    if name in location:
                        return location[name]
            names = " or ".join(names)
            raise Exception("Could not find credentials value for {}".format(names))

        access = locate(('access_key', 'aws_access_key'), (kwargs, credentials))
        secret = locate(('secret_key', 'aws_secret_key'), (kwargs, credentials))
        region = locate(('region', 'aws_region'), (kwargs, credentials))

        session = Session(aws_access_key_id = access,
                          aws_secret_access_key = secret,
                          region_name = region)

        try:
            account_id = locate(('account_id', 'aws_account_id'), (kwargs, credentials))
        except:
            account_id = None

    if account_id is None:
        # From boss-manage.git/lib/aws.py:get_account_id_from_session()
        account_id = session.client('iam').list_users(MaxItems=1)["Users"][0]["Arn"].split(':')[4]

    return session, account_id

