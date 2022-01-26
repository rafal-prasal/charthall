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

ENV STORAGE_LOCAL_ROOTDIR=/charthall_data
ENV PORT=8080
ENV CHART_POST_FORM_FIELD_NAME=chart
ENV PROV_POST_FORM_FIELD_NAME=prov
ENV CACHE_INTERVAL=10m

USER 10000

WORKDIR /charthall
ENTRYPOINT [ "python3.9", "./charthall.py" ]
