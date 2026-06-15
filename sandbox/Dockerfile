FROM python:3.12-slim

RUN pip install --no-cache-dir pandas numpy scipy matplotlib

WORKDIR /sandbox
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
