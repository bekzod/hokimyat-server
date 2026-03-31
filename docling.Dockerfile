FROM ghcr.io/docling-project/docling-serve-cpu:v1.14.0

USER root

RUN dnf install -y \
    tesseract-langpack-rus \
    tesseract-langpack-uzb \
    tesseract-langpack-uzb_cyrl && \
    dnf clean all && \
    echo "docling:x:1000:0:docling:/opt/app-root:/bin/bash" >> /etc/passwd

USER 1000
