import sys, os.path
from boto.s3.connection import S3Connection
#s3conn = eventlet.import_patched("boto.s3.connection")
#S3Connection = s3conn.S3Connection
from boto.s3.key import Key
import os
import mimetypes
import gzip
import tempfile
import logging
import shutil

AWS_ACCESS_KEY_ID = "PUT_YOURS_HERE"
AWS_SECRET_ACCESS_KEY = "PUT_YOURS_HERE"
CONCURRENCY = 32

def _s3conn(aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY):
    return S3Connection(aws_access_key_id, aws_secret_access_key)

def s3_upload_flo(flo, bucket_name, key_name, mimetype):
    conn = _s3conn()
    bucket = conn.get_bucket(bucket_name)

    options = { 'Content-Type' : mimetype }

    k = Key(bucket)
    k.key = key_name
    k.set_contents_from_file(flo, options, policy='public-read')
    return 'http://%s/%s' % (bucket_name,key_name)

