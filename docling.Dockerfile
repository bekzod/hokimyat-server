FROM ghcr.io/docling-project/docling-serve-cpu:v1.15.1

USER root

RUN dnf install -y \
    tesseract-langpack-rus \
    tesseract-langpack-uzb \
    tesseract-langpack-uzb_cyrl && \
    dnf clean all

USER 1000
