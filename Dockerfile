# Copyright 2022 Rafal Prasal <rafal.prasal@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM  registry.access.redhat.com/ubi8/ubi:latest

COPY src/ /charthall

RUN mkdir -p /charthall_data \
    && chown 10000:10000 /charthall_data /charthall \
    && yum install -y python39-pip \
    && pip-3.9 install \
        Flask \
        Flask-HTTPAuth \
        flask-log-request-id \
        waitress \
        paste \
    && yum clean all \
    && rm -rf /var/cache/yum/*

ENV STORAGE=local
ENV STORAGE_LOCAL_ROOTDIR=/charthall_data
ENV PORT=8080
ENV CHART_POST_FORM_FIELD_NAME=chart
ENV PROV_POST_FORM_FIELD_NAME=prov
ENV CACHE_INTERVAL=10m
ENV INDEX_LIMIT=50
ENV ALLOW_OVERWRITE=true

# BASIC_AUTH_USER=user
# BASIC_AUTH_PASSWORD=password
# AUTH_ANONYMOUS_GET=true/false

USER 10000

WORKDIR /charthall
ENTRYPOINT [ "python3.9", "./charthall.py" ]
