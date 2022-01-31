# ChartHall 0.0.3

To some extent it is replacement to chartmuseum, which is great piece of software, but unfortunately has its flaws and limitations.

Code found here is like "Cutting the grass with machete" and definitely could be prettier, but it simply gets the job done, so don't complain about it too much.

**Upsides**
- really quick start
- scales well with growing number of charts in repos
  - single repo
    - POST /{repo}/charts 
      - concurency=1
        - 200 charts: ~30/s
        - 130k charts: ~20/s
    - GET /{repo}/index.yaml 
      - concurency=1
        - 200 charts, 37k, ~550/s, 20MB/s
        - 130k charts, 28MB, ~0.7s, 20MB/s
      - concurency=100
        - 200 charts, 37k, ~920/s, 35MB/s
        - 130k charts, 28MB, ~25/s, 725MB/s
- compatible with chartmuseum
  - handles the same api endpoints as chartmuseum when DEPTH=1
  - handles the same environmental variables as chartmuseum
    - CHART_URL
    - CONTEXT_PATH
    - PORT
    - STORAGE_LOCAL_ROOTDIR
    - BASIC_AUTH_USER / BASIC_AUTH_PASSWORD / AUTH_ANONYMOUS_GET
    - ALLOW_OVERWRITE
    - CHART_POST_FORM_FIELD_NAME
    - PROV_POST_FORM_FIELD_NAME
    - CACHE_INTERVAL

**Downdsides**
- handles only environmental variables
- works only as a single replica
- supports only local storage (STORAGE=local)
- only single path level for repo is allowed (DEPTH=1)
- compatible, but probably not fully compliant with semantic versioning, silently ignores noncompliant files
- relies solely on filenames and does not provide any additional data in index.yaml and other api calls

## USAGE EXAMPLES

### building image image

    docker build -t charthall:latest .

### creating data directory

    mkdir -p /path/to/data/directory
    chown  -R 10000:10000 /path/to/data/directory

### runnig

    docker run \
        -d \
        -p 8080:8080 \
        -v /path/to/data/directory:/charthall_data \
        charthall:latest

### with rebuilding of cache with internal of 10m
    docker run \
        -d \
        -p 8080:8080 \
        -v /path/to/data/directory:/charthall_data \
        -e CACHE_INTERVAL=10m \
        charthall:latest

            
### with basic authentication

        docker run \
        -d \
        -p 8080:8080 \
        -e BASIC_AUTH_USER=myuser \
        -e BASIC_AUTH_PASS=mypassword \
        -v /path/to/data/directory:/charthall_data \
        charthall:latest

### when basic authentication needed only for chart manipulation
        docker run \
        -d \
        -p 8080:8080 \
        -e BASIC_AUTH_USER=myuser \
        -e BASIC_AUTH_PASS=mypassword \
        -e AUTH_ANONYMOUS_GET=true \
        -v /path/to/data/directory:/charthall_data \
        charthall:latest

### when youd dissallow overwrite of chars and prov files
    docker run \
        -d \
        -p 8080:8080 \
        -e ALLOW_OVERWRITE=false \
        -v /path/to/data/directory:/charthall_data \
        charthall:latest

### when you want to change form fields for posting chart and prov file
    docker run \
        -d \
        -p 8080:8080 \
        -e CHART_POST_FORM_FIELD_NAME=chart_field \
        -e PROV_POST_FORM_FIELD_NAME=prov_field \
        -v /path/to/data/directory:/charthall_data \
        charthall:latest

### when you hide charthall behind a reverse proxy
    docker run \
        -d \
        -p 8080:8080 \        
        -e CHART_URL=http://reverse-proxy/context-path \
        -v /path/to/data/directory:/charthall_data \
        charthall:latest

### use helm
adding repository

    helm repo add myrepo http://localhost:8080/myrepo

getting chart

    helm fetch myrepo/mychart --version 0.0.1

## API

### GET /
list of repos using yaml as an output

    curl http://localhost:8080/

    curl -u "$BASIC_AUTH_USER:$BASIC_AUTH_PASS" http://localhost:8080/
    
output:

    ---
    repos:
    - myrepo
    - myrepo2

### GET /info
name and version of the application

    curl http://localhost:8080/info

    curl -u "$BASIC_AUTH_USER:$BASIC_AUTH_PASS" http://localhost:8080/info

output:
    
    {"version":"v0.0.3"}

### GET /health
information about health of service, no basic authentication check here

    curl http://localhost:8080/health
    
output:
- in case removal went fine

    {"healthy":true}


### GET /{repo}/index.yaml
index.yaml file used by helm. provides only minimal set of inforation needed by helm to obtain the chart. environmental variable CHART_URL is a prefix for urls here.

    curl http://localhost:8080/myrepo/index.yaml

    curl -u "$BASIC_AUTH_USER:$BASIC_AUTH_PASS" http://localhost:8080/myrepo/index.yaml

output:

    apiVersion: v1
    entries:
      mychart:
        - apiVersion: v1
          appVersion: 0.0.1
          created: "2022-01-31T14:09:14.636198000+00:00"
          description: mychart 0.0.1
          digest: abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789
          name: mychart
          urls:
            - /myrepo/charts/mychart-0.0.2.tgz
          version: 0.0.1
        - apiVersion: v1
          appVersion: 0.0.2
          created: "2022-01-31T14:09:14.636198000+00:00"
          description: mychart 0.0.2
          digest: abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789
          name: mychart
          urls:
            - /myrepo/charts/mychart-0.0.2.tgz
          version: 0.0.2
      mychart2:
        - apiVersion: v1
          appVersion: 0.0.1
          created: "2022-01-31T14:09:14.636198000+00:00"
          description: mychart2 0.0.1
          digest: abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789
          name: mychart
          urls:
            - /myrepo/charts/mychart2-0.0.1.tgz
          version: 0.0.1
        - apiVersion: v1
          appVersion: 0.0.2
          created: "2022-01-31T14:09:14.636198000+00:00"
          description: mychart2 0.0.2
          digest: abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789
          name: mychart2
          urls:
            - /myrepo/charts/mychart2-0.0.2.tgz
          version: 0.0.2
    generated: "2022-01-31T17:32:24+00:00"
    serverInfo: {}

### GET /{repo}/charts/{chart}-{version}.tgz
provides a helm chart file to helm when helm fetch is executed

### GET /{repo}/charts/{chart}-{version}.trov
provides a prov file to helm

### GET /api/{repo}/charts
provides list of charts in repo using json as an output

    curl -u http://localhost:8080/api/myrepo/charts

    curl -u "$BASIC_AUTH_USER:$BASIC_AUTH_PASS" http://localhost:8080/api/myrepo/charts

output:

    {
        "mychart": [
            {
                "apiVersion": "v1",
                "name": "mychart",
                "version": "0.0.1",
                "description": "mychart 0.0.1",
                "digest": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
                "urls": [
                    "/myrepo/charts/mychart-0.0.1.tgz"
                ],
                "created": "2022-01-31T14:09:14.636198000+00:00"
            },
            {
                "apiVersion": "v1",
                "name": "mychart",
                "version": "0.0.2",
                "description": "mychart 0.0.2",
                "digest": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
                "urls": [
                    "/myrepo/charts/mychart-0.0.2.tgz"
                ],
                "created:": "2022-01-31T14:09:14.636198000+00:00"
            }
        ],
        "mychart2": [
            {
                "apiVersion": "v1",
                "name": "mychart2",
                "version": "0.0.1",
                "description": "mychart2 0.0.1",
                "digest": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
                "urls": [
                    "/myrepo/charts/mychart2-0.0.1.tgz"
                ],
                "created:": "2022-01-31T14:09:14.636198000+00:00"
            },
            {
                "apiVersion": "v1",
                "name": "mychart2",
                "version": "0.0.2",
                "description": "mychart2 0.0.2",
                "digest": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
                "urls": [
                    "/myrepo/charts/mychart2-0.0.2.tgz"
                ],
                "created:": "2022-01-31T14:09:14.636198000+00:00"
            }
        ]
    }

### GET /api/{repo}/charts/{chart}
provides list of versions of **chart** in **repo** using json as an output

    curl -u http://localhost:8080/api/myrepo/charts/mychart

    curl -u "$BASIC_AUTH_USER:$BASIC_AUTH_PASS" http://localhost:8080/api/myrepo/charts/mychart

output:

    [
        {
            "apiVersion": "v1",
            "name": "mychart",
            "version": "0.0.1",
            "description": "mychart 0.0.1",
            "digest": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
            "urls": [
                "/myrepo/charts/mychart-0.0.1.tgz"
            ],
            "created": "2022-01-31T14:09:14.636198000+00:00"
        },
        {
            "apiVersion": "v1",
            "name": "mychart",            
            "version": "0.0.2",
            "description": "mychart 0.0.2",
            "digest": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
            "urls": [
                "/myrepo/charts/mychart-0.0.2.tgz"
            ],
            "created": "2022-01-31T14:09:14.636198000+00:00"
        }
    ]

### GET /api/{repo}/charts/{chart}/{version}
describes particular **version** of **chart** in **repo** using json as an output

    curl http://localhost:8080/api/myrepo/charts/mychart/0.0.1

    curl -u "$BASIC_AUTH_USER:$BASIC_AUTH_PASS" http://localhost:8080/api/myrepo/charts/mychart/0.0.1


output:

    {
        "apiVersion": "v1",
        "name": "mychart",
        "version": "0.0.1",
        "description": "mychart 0.0.1",
        "urls": [
            "/myrepo/charts/mychart-0.0.1.tgz"
        ],
        "digest": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
        "created": "2022-01-31T14:09:14.636198000+00:00"
    }

### POST /api/{repo}/charts
adds **chart** with **prov** file to the repo. if **repo** does not exist it will create it on the spot

    curl \
        -X POST \
        -F $CHART_POST_FORM_FIELD_NAME=@mychart-0.0.1.tar.gz \
        -F $PROV_POST_FORM_FIELD_NAME=@mychart-0.0.1.prov \ 
        http://localhost:8080/api/myrepo/charts

    curl \-X POST 
        -u "$BASIC_AUTH_USER:$BASIC_AUTH_PASS" \        
        -F $CHART_POST_FORM_FIELD_NAME=@mychart-0.0.1.tar.gz \
        -F $PROV_POST_FORM_FIELD_NAME=@mychart-0.0.1.prov \ 
        http://localhost:8080/api/myrepo/charts

output:
- in case adding chart + prov file went fine

    { "saved": true }

- or in case if not

    { "saved": false }

### DELETE /api/{repo}/charts/{chart}/{version}
removes **chart** archive and prov file for particular **version** from **repo**. if **chart** will stay with no **version** then it will also remove it.

    curl \
        -X DELETE \        
        http://localhost:8080/api/myrepo/charts/mychart/0.0.1

    curl \
        -u "$BASIC_AUTH_USER:$BASIC_AUTH_PASS" \
        -X DELETE \
        http://localhost:8080/api/myrepo/charts/mychart/0.0.1


output:
- in case removal went fine

    { "deleted": true }

- or if not

    { "deleted": false }
