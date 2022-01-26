#!/usr/bin/env python3

import os
from pickle import APPEND
import sys
import io
import datetime
import distutils
import threading
import time

from threading import Lock

from flask import Flask, after_this_request, request, send_file
from flask_log_request_id import RequestID, current_request_id
from flask_httpauth import HTTPBasicAuth
from werkzeug.datastructures import Headers
from werkzeug.security import generate_password_hash, check_password_hash
import re

CHARTHALL_VERSION="0.0.2"

CHARTHALL_STORAGE='local'
CHARTHALL_STORAGE_LOCAL_ROOTDIR='/data/storage'
CHARTHALL_DEPTH=1
CHARTHALL_CHART_POST_FORM_FIELD_NAME='chart'
CHARTHALL_PROV_POST_FORM_FIELD_NAME='prov'
CHARTHALL_CHART_URL=''

CHARTHALL_BASIC_AUTH_USER=None
CHARTHALL_BASIC_AUTH_PASS=None
CHARTHALL_AUTH_ANONYMOUS_GET=False

CHARTHALL_CACHE_INTERVAL=0
CHARTHALL_ALLOW_OVERWRITE=True

CACHE={
    'info': '{{"version":"v{version}"}}'.format(
                 version=CHARTHALL_VERSION
    ),
    'index': {},
    'repos': """---
repos: []
""",
    'mutexes' : {}
}
    
RE_VERSION=re.compile('([0-9]+\.){2,}[0-9]+')

MUTEX = Lock()

def log_print(_type, _msg):
    print(
        '[{stamp}] [{type}] {msg}'.format(
        #[25/Jan/2022:11:48:46 +0000]
            stamp=datetime.datetime.now().strftime("%d/%B/%Y:%H:%M:%S %z"),
            type=_type,
            msg=_msg
        )
    )

def extract_name_version(_filename):
    parts=_filename.split('-')

    chart_name=[]
    chart_version=[]
    
    isName=True
    for p in parts:
        if isName and RE_VERSION.match(p):
            isName=False

        if isName:
            chart_name.append(p)
        else:
            chart_version.append(p)

    return {
        'chart': '-'.join(chart_name), 
        'version': '-'.join(chart_version)
    }

def cache_rebuild():
    repos=os.listdir(CHARTHALL_STORAGE_LOCAL_ROOTDIR)
    
    log_print('INFO', 'Rebuilding Cache start')
    for r in repos:
        if os.path.isdir(os.path.join(CHARTHALL_STORAGE_LOCAL_ROOTDIR, r)):
            cache_add_repo(r)
            CACHE['mutexes'][r].acquire()
            cache_rebuild_repo_charts(r)
            CACHE['mutexes'][r].release()
    log_print('INFO', 'Rebuilding Cache finish')
    
def cache_add_repo(_repo):

    if _repo in CACHE['mutexes']:
        return

    MUTEX.acquire()
    repo_dir=os.path.join(CHARTHALL_STORAGE_LOCAL_ROOTDIR,_repo)

    if not os.path.exists(repo_dir):
        os.mkdir(repo_dir)
    
    CACHE['index'][_repo] = {
        'yaml_chart_version':{},
        'yaml_chart':{},        
        'yaml':'---',
        'json_chart_version':{},
        'json_chart': {},
        'json':'{}'
    }

    CACHE['mutexes'][_repo] = Lock()     
    str_repos="""---
repos:
"""
    for p in CACHE['mutexes']:
        str_repos=str_repos+"""- {repo}
""".format(repo=p)

    CACHE['repos']=str_repos

    MUTEX.release()

def cache_render_chart_version(_cache, _repo, _data):
    global CHARTHALL_CHART_URL

    c=_data['chart']
    v=_data['version']

    if c not in _cache['yaml_chart_version']:
        _cache['yaml_chart_version'][c] = {}
        _cache['json_chart_version'][c] = {}
    
    _cache['yaml_chart_version'][ c ][ v ]="""  - apiVersion: v1
    name: {chart}
    version: {version}
    appVersion: {version}
    urls:
    - {chart_url}/{repo}/charts/{filename}
    dependencies: []
    created: {created}
""".format(
        chart=_data['chart'],
        version=_data['version'],
        filename=_data['filename'],
        created=_data['created_yaml'],
        chart_url=CHARTHALL_CHART_URL,
        repo=_repo
    )

    _cache['json_chart_version'][ c ][ v ]='{{"apiVersion" : "v1", "appVersion": "{version}", "dependencies": [], "name": "{chart}", "version": "{version}", "urls": [ "{chart_url}/{repo}/charts/{filename}" ], "created:": "{created}"}}'.format(
        chart=_data['chart'],
        version=_data['version'],
        filename=_data['filename'],
        created=_data['created_json'],
        chart_url=CHARTHALL_CHART_URL,
        repo=_repo        
    ) 

def cache_render_chart(_cache, _chart):

    _cache['yaml_chart'][ _chart ]="""  {chart}:
{list}""".format(
        chart=_chart,
        list="".join(
            _cache['yaml_chart_version'][_chart].values()
        )
    )

    _cache['json_chart'][ _chart ]='[{list}]'.format(
        chart=_chart,
        list=",".join(
            _cache['json_chart_version'][_chart].values()
        )
    )

def cache_render(_cache):

    if len( _cache['yaml_chart'].values())==0: 

        _cache['yaml']="""---
apiVersion: v1
entries: {}"""

        _cache['json']="{}"

        return

    _cache['yaml']="""---
apiVersion: v1
entries:
{list}""" .format(
        list="".join(
            _cache['yaml_chart'].values()
        )
    )

    list=[]
    for c in _cache['json_chart']:
        list.append( '"'+c+'": '+_cache['json_chart'][c])

    _cache['json']='{{{list}}}' .format(
        list=",".join(
            list
        )
    )

def cache_rebuild_repo_charts(_repo):
    repo_path = os.path.join(CHARTHALL_STORAGE_LOCAL_ROOTDIR, _repo )
    files=os.listdir(repo_path)
    
    cache= {
        'yaml_chart_version':{},
        'yaml_chart':{},        
        'yaml':'---',
        'json_chart_version':{},
        'json_chart': {},
        'json':'{}'
    }

    for f in files:        
        if not f.endswith('.tgz'):
            continue

        file_path = os.path.join(repo_path, f)

        if not os.path.isfile(file_path):
            continue

        data=extract_name_version(
            f.replace('.tgz','')
        )

        if data is not None and data['version'] == '':
            continue
                                
        data['created']=datetime.datetime.fromtimestamp(
            os.lstat(file_path).st_ctime,
            tz=datetime.timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        data['filename'] = f

        cache_render_chart_version(cache, _repo, data)

    for c in cache['yaml_chart_version']:
        cache_render_chart(cache, c)
    
    cache_render(cache)

    CACHE['index'][_repo]=cache
                    
def put_file(_repo, _extension, _req_file):
    global CHARTHALL_ALLOW_OVERWRITE
    
    if _req_file is None:
        return

    basename=os.path.basename(_req_file.filename)
    data=extract_name_version(basename.replace(_extension,''))

    repo_dir = os.path.join(CHARTHALL_STORAGE_LOCAL_ROOTDIR,_repo)
    filename=os.path.join(repo_dir,basename)

    if CHARTHALL_ALLOW_OVERWRITE == False \
        and _repo in CACHE['index'] \
        and data['chart'] in CACHE['index'][_repo]['json_chart_version'] \
        and data['version'] in CACHE['index'][_repo]['json_chart_version'][ data['chart'] ]:
        raise Exception("chart overwriting not allowed "+filename)

    if not filename.endswith(_extension):
        raise Exception('incorrect extension('+_extension+') '+basename)

    if data['version']=='':
        raise Exception('non semantic versioning '+basename)

    _req_file.save(filename)    

    data['filename']=basename

    os_lstat_st_ctime=os.lstat(filename).st_ctime

    data['created_yaml']=datetime.datetime.fromtimestamp(
        os_lstat_st_ctime,
        tz=datetime.timezone.utc        
    ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    data['created_json']=datetime.datetime.fromtimestamp(
        os_lstat_st_ctime,
        tz=datetime.timezone.utc        
    ).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")

    return data

################ REQUESTS ################
def request_post_api_repo_charts(_repo, _req_chart, _req_prov):
            
    if _req_chart is None:
        return ('{"saved":false}', 400)
    
    try:
        cache_add_repo(_repo)
        
        CACHE['mutexes'][_repo].acquire()

        cache=CACHE['index'][_repo]

        data=put_file(_repo, '.tgz', _req_chart)
        if _req_prov is not None:
            put_file(_repo, '.tgz.prov', _req_prov)
        
        cache_render_chart_version(cache, _repo, data)
        cache_render_chart(cache, data['chart'])
        cache_render(cache)
        
    except Exception as e:
        log_print(
            'ERROR', 'request_post_api_repo_charts({repo}): {msg}'.format(
                repo=_repo,
                msg=str(e)
            )
        )
        return('{"saved":false}', 400)
    finally:
        CACHE['mutexes'][_repo].release()
            
    return ('{"saved":true}', 201)

def request_get_repo_charts_file(_repo, _file):
    try:
        mimetype='text/plain; charset=utf-8'

        if _file.endswith('.tgz'):
            mimetype='application/x-tar'

        file_path=os.path.join(CHARTHALL_STORAGE_LOCAL_ROOTDIR, _repo, _file)        
        
        with open(file_path, "rb") as bites:
            return send_file(
                io.BytesIO(bites.read()),
                as_attachment=True,
                attachment_filename=_file,
                mimetype=mimetype
            )

    except Exception as e:
        log_print(
            'ERROR',
            'request_get_repo_charts_file({repo}, {file}): {msg}'.format(
                repo=_repo,
                file=_file,
                msg=str(e)
            )
        )
        return str(e),404

def request_delete_api_repo_charts_chart_version(_repo, _chart, _version):
    if _repo not in CACHE['index']:
        log_print(
            'WARNING', 
            'request_delete_api_repo_charts_chart_version({repo}, {chart}, {version}): repo() does not exist'.format(
                repo=_repo,
                chart=_chart,
                version=_version
            )
        )
        return ('{"deleted":false}', 404 )
    
    CACHE['mutexes'][_repo].acquire()

    try: 
        if _chart not in CACHE['index'][_repo]['json_chart_version']:        
            raise Exception('chart not in repo')
    
        if _version not in CACHE['index'][_repo]['json_chart_version'][_chart]:
            raise Exception('version not in chart in project')

        try:            
            os.remove(os.path.join(CHARTHALL_STORAGE_LOCAL_ROOTDIR, _repo, _chart+'-'+_version+'.tgz'))
            os.remove(os.path.join(CHARTHALL_STORAGE_LOCAL_ROOTDIR, _repo, _chart+'-'+_version+'.tgz.prov'))
        except Exception as e:
            log_print(
                'WARNING', 
                'request_delete_api_repo_charts_chart_version({repo}, {chart}, {version}): {msg}'.format(
                    repo=_repo,
                    chart=_chart,
                    version=_version,
                    msg=str(e)
                )
            )
            pass

        cache= CACHE['index'][_repo]

        del cache['yaml_chart_version'][_chart][_version]
        del cache['json_chart_version'][_chart][_version]

        if len(cache['yaml_chart_version'][_chart]) == 0:
            del cache['yaml_chart_version'][_chart]
            del cache['yaml_chart'][_chart]
            del cache['json_chart_version'][_chart]
            del cache['json_chart'][_chart]
        else:
            cache_render_chart(cache, _chart)

        cache_render(cache)

        return '{"deleted":true}'

    except Exception as e:
        log_print(
            'WARNING',
            'request_delete_api_repo_charts_chart_version({repo}, {chart}, {version}): {msg}'.format(
                repo=_repo,
                chart=_chart,
                version=_version,
                msg=str(e)
            )
        )
        return ('{"deleted":false}', 404 )
    finally:    
        CACHE['mutexes'][_repo].release()

def request_head_api_repo_charts_chart_version(_repo, _chart, _version):
    if _repo not in CACHE['index']:
        return ('{{"error":"{repo} not found"}}'.format(repo=_repo), 404)

    if _chart not in CACHE['index'][_repo]['json_chart_version']:
        return ('{{"error":"{repo}/{chart} not found"}}'.format(repo=_repo, chart=_chart), 404)
    
    if _version not in CACHE['index'][_repo]['json_chart_version'][_chart]:
        return ('{{"error":"{repo}/{chart}-{version} not found"}}'.format(repo=_repo, chart=_chart, version=_version), 404)

    return ('{}', 200)

def request_get_api_repo_charts(_repo):
    if _repo not in CACHE['index']:        
        return ('{}', 200)

    return CACHE['index'][_repo]['json']

def request_get_api_repo_charts_chart_version(_repo, _chart, _version):
    if _repo not in CACHE['index']:
        return ('{{"error":"{repo} not found"}}'.format(repo=_repo), 404)

    if _chart not in CACHE['index'][_repo]['json_chart_version']:
        return ('{{"error":"{repo}/{chart} not found"}}'.format(repo=_repo, chart=_chart), 404)
    
    if _version not in CACHE['index'][_repo]['json_chart_version'][_chart]:
        return ('{{"error":"{repo}/{chart}-{version} not found"}}'.format(repo=_repo, chart=_chart, version=_version), 404)
        
    return CACHE['index'][_repo]['json_chart_version'][_chart][_version]

def request_get_api_repo_charts_chart(_repo, _chart):
    if _repo not in CACHE['index']:
        return ('{{"error":"{repo} not found"}}'.format(repo=_repo), 404)

    if _chart not in CACHE['index'][_repo]['json_chart_version']:
        return ('{{"error":"{repo}/{chart} not found"}}'.format(repo=_repo, chart=_chart), 404)
    
    return CACHE['index'][_repo]['json_chart'][_chart]

################ ROUTES ################
def app_build():

    global app
    global auth

    app = Flask(__name__)
    RequestID(app)
    auth = HTTPBasicAuth()

    global CHARTHALL_BASIC_AUTH_USER
    global CHARTHALL_BASIC_AUTH_PASS
    global CHARTHALL_AUTH_ANONYMOUS_GET
    
    allow_anonymous_get=False
    allow_anonymous_nonget=False

    if CHARTHALL_BASIC_AUTH_USER is not None and CHARTHALL_BASIC_AUTH_PASS is not None:
        allow_anonymous_nonget=False

        if CHARTHALL_AUTH_ANONYMOUS_GET:
            allow_anonymous_get=True
    else:
        allow_anonymous_get=True
        allow_anonymous_nonget=True
    
    @auth.verify_password
    def verify_password(_user, _password):
        global CHARTHALL_BASIC_AUTH_USER
        global CHARTHALL_BASIC_AUTH_PASS

        if CHARTHALL_BASIC_AUTH_USER is None or CHARTHALL_BASIC_AUTH_PASS is None:
            return 'anonymous'

        if _user == CHARTHALL_BASIC_AUTH_USER and _password == CHARTHALL_BASIC_AUTH_PASS:
            return _user
            
        return None

    #GET /health
    @app.route('/health')
    def route_get_health():
        @after_this_request
        def add_header(_response):
            _response.headers['X-Request-Id'] = current_request_id()
            _response.headers['Content-Type']='application/json; charset=utf-8'
            return _response

        return '{"healthy":true}'

    #GET /    
    @app.route('/')
    @auth.login_required(optional=allow_anonymous_get)
    def route_get_repos():
        @after_this_request
        def add_header(_response):
            _response.headers['X-Request-Id'] = current_request_id()
            _response.headers['Content-Type']='text/x-yaml; charset=utf-8'
            return _response
    
        return CACHE['repos']
    
    #GET /info
    @app.route('/info')
    @auth.login_required(optional=allow_anonymous_get)
    def route_get_info():
        @after_this_request
        def add_header(_response):
            _response.headers['X-Request-Id'] = current_request_id()
            _response.headers['Content-Type']='application/json; charset=utf-8'
            return _response

        return CACHE['info']

    #GET /index.yaml
    @app.route('/<_repo>/index.yaml', methods=['GET'])
    @auth.login_required(optional=allow_anonymous_get)
    def route_repo_index_yaml(_repo):
        @after_this_request
        def add_header(_response):
            _response.headers['X-Request-Id'] = current_request_id()
            _response.headers['Content-Type']='text/x-yaml; charset=utf-8'
            return _response
        
        if _repo not in CACHE['index']:
            return ("""---
apiVersion: v1
entries: {}
""", 200)

        return CACHE['index'][_repo]['yaml']

    #GET /charts/<_file>
    @app.route('/<_repo>/charts/<_file>', methods=['GET'])
    @auth.login_required(optional=allow_anonymous_get)
    def route_repo_charts_file(_repo,_file):
        @after_this_request
        def add_header(_response):            
            _response.headers['X-Request-Id'] = current_request_id()
            return _response

        return request_get_repo_charts_file(_repo, _file)

    @app.route('/api/<_repo>/charts', methods=['GET'])
    @auth.login_required(optional=allow_anonymous_get)
    def route_api_repo_charts(_repo):
        @after_this_request
        def add_header(_response):
            _response.headers['X-Request-Id'] = current_request_id()
            _response.headers['Content-Type']='application/json; charset=utf-8'
            return _response

        if request.method == 'GET':
            return request_get_api_repo_charts(_repo)

        return ( '{"error":"unknown method"}', 400 )

    #POST /api/charts
    @app.route('/api/<_repo>/charts', methods=['POST'])
    @auth.login_required(optional=allow_anonymous_nonget)
    def route_POST_api_repo_charts(_repo):
        @after_this_request
        def add_header(_response):
            _response.headers['X-Request-Id'] = current_request_id()
            _response.headers['Content-Type']='application/json; charset=utf-8'
            return _response

        if request.method == 'POST':
            req_chart=None
            if CHARTHALL_CHART_POST_FORM_FIELD_NAME in request.files:
                req_chart=request.files[CHARTHALL_CHART_POST_FORM_FIELD_NAME]

            req_prov=None
            if CHARTHALL_PROV_POST_FORM_FIELD_NAME in request.files:
                req_prov=request.files[CHARTHALL_PROV_POST_FORM_FIELD_NAME]

            return request_post_api_repo_charts(_repo, req_chart, req_prov)

        return ( '{"error":"unknown method"}', 400 )

    #GET /api/charts/<_chart>
    @app.route('/api/<_repo>/charts/<_chart>', methods=['GET'])
    @auth.login_required(optional=allow_anonymous_get)
    def route_api_repo_charts_chart(_repo,_chart):
        @after_this_request
        def add_header(_response):
            _response.headers['X-Request-Id'] = current_request_id()
            _response.headers['Content-Type']='application/json; charset=utf-8'
            return _response

        if request.method == 'GET':
            return request_get_api_repo_charts_chart(_repo,_chart)

        return ( '{"error":"unknown method"}', 400 )

    #GET /api/charts/<chart>/<version>
    @app.route("/api/<_repo>/charts/<_chart>/<_version>", methods=['GET', 'HEAD'])
    @auth.login_required(optional=allow_anonymous_get)
    def route_api_repo_charts_chart_version(_repo, _chart, _version):
        @after_this_request
        def add_header(_response):
            _response.headers['X-Request-Id'] = current_request_id()
            _response.headers['Content-Type']='text/x-yaml; charset=utf-8'
            return _response
        
        if request.method == 'HEAD':
            return request_head_api_repo_charts_chart_version(_repo, _chart, _version)

        if request.method == 'GET':
            return request_get_api_repo_charts_chart_version(_repo, _chart, _version)

        return ( '{"error":"unknown method"}', 400 )

    #DELETE /api/charts/<chart>/<version>
    @app.route("/api/<_repo>/charts/<_chart>/<_version>", methods=['DELETE'])
    @auth.login_required(optional=allow_anonymous_nonget)
    def route_DELETE_api_repo_charts_chart_version(_repo, _chart, _version):
        @after_this_request
        def add_header(_response):
            _response.headers['X-Request-Id'] = current_request_id()
            _response.headers['Content-Type']='text/x-yaml; charset=utf-8'
            return _response

        if request.method == 'DELETE':
            return request_delete_api_repo_charts_chart_version(_repo, _chart, _version)
                
        return ( '{"error":"unknown method"}', 400 )

    return app

def rebuild_cache_on_timer():

    sleep_time=0

    try:
        sleep_time=int(CHARTHALL_CACHE_INTERVAL.replace('m',''))*60
    except:
        log_print('WARNING', 'CACHE_INTERVAL not set or not an integer, assuming no CACHE_REBUILD')
        pass

        
    while sleep_time>0:
        time.sleep(sleep_time)
        cache_rebuild()

def create_app(
        _storage=None, 
        _storage_local_rootdir=None, 
        _depth=None,
        _chart_post_form_field_name=None,
        _prov_post_form_field_name=None,        
        _basic_auth_user=None,
        _basic_auth_pass=None,
        _cache_interval=None,
        _allow_overwrite=None,
        _auth_anonymous_get=None,
        _chart_url=None
    ):

    global CHARTHALL_STORAGE_LOCAL_ROOTDIR
    global CHARTHALL_STORAGE
    global CHARTHALL_DEPTH
    global CHARTHALL_CHART_POST_FORM_FIELD_NAME
    global CHARTHALL_PROV_POST_FORM_FIELD_NAME
    global CHARTHALL_BASIC_AUTH_USER
    global CHARTHALL_BASIC_AUTH_PASS
    global CHARTHALL_CACHE_INTERVAL
    global CHARTHALL_ALLOW_OVERWRITE
    global CHARTHALL_AUTH_ANONYMOUS_GET
    global CHARTHALL_CHART_URL

    if _storage_local_rootdir is not None:
        CHARTHALL_STORAGE_LOCAL_ROOTDIR=_storage_local_rootdir

    if _chart_post_form_field_name is not None:
        CHARTHALL_CHART_POST_FORM_FIELD_NAME=_chart_post_form_field_name

    if _prov_post_form_field_name is not None:
        CHARTHALL_PROV_POST_FORM_FIELD_NAME=_prov_post_form_field_name

    if _chart_url is not None:
        CHARTHALL_CHART_URL = _chart_url

    if _basic_auth_user is not None and _basic_auth_pass is not None:
        CHARTHALL_BASIC_AUTH_USER=_basic_auth_user
        CHARTHALL_BASIC_AUTH_PASS=_basic_auth_pass

    if _cache_interval is not None:
        CHARTHALL_CACHE_INTERVAL=_cache_interval

    if _allow_overwrite is not None:
        try:
            CHARTHALL_ALLOW_OVERWRITE=distutils.util.strtobool(_allow_overwrite)
        except:            
            pass

    if _auth_anonymous_get is not None:
        try:
            CHARTHALL_AUTH_ANONYMOUS_GET = distutils.util.strtobool(_auth_anonymous_get)
        except:            
            pass

    cache_rebuild()
    app_build()

    rebuild_cache_thread = threading.Thread(target=rebuild_cache_on_timer)
    rebuild_cache_thread.start()

    return app