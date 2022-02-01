#!/usr/bin/env python3.9

import os
import waitress
import charthall_py
import paste.translogger

if __name__ == "__main__":

    context_path=os.getenv('CONTEXT_PATH')
    if context_path is None:
        context_path=''

    port=os.getenv('PORT')
    if port is None:
        port=8080

    waitress.serve(
        paste.translogger.TransLogger(
            charthall_py.create_app(                
                _storage_local_rootdir=os.getenv('STORAGE_LOCAL_ROOTDIR'),
                _chart_post_form_field_name=os.getenv('CHART_POST_FORM_FIELD_NAME'),
                _prov_post_form_field_name=os.getenv('PROV_POST_FORM_FIELD_NAME'),
                _basic_auth_user=os.getenv('BASIC_AUTH_USER'),
                _basic_auth_pass=os.getenv('BASIC_AUTH_PASS'),
                _auth_anonymous_get=os.getenv('AUTH_ANONYMOUS_GET'),
                _allow_overwrite=os.getenv('ALLOW_OVERWRITE'),
                _chart_url=os.getenv('CHART_URL'),
                _cache_interval=os.getenv('CACHE_INTERVAL'),
                _index_limit=os.getenv('INDEX_LIMIT'),
        #do not do anything
                _storage=os.getenv('STORAGE'),   #ALWAYS =LOCAL             
                _depth=os.getenv('DEPTH')        #ALWAYS =1
            )
        ),
        port=port,
        host="0.0.0.0",
        url_prefix=context_path
    )
