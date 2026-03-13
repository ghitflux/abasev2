FROM mysql:8.0

COPY docker/mysql/init/10-dev-grants.sh /docker-entrypoint-initdb.d/10-dev-grants.sh
COPY docker/mysql/init/20-import-abasedb1203.sh /docker-entrypoint-initdb.d/20-import-abasedb1203.sh
COPY scriptsphp/abasedb1203.sql /docker-entrypoint-initdb.d/abasedb1203.sql

RUN chmod 755 /docker-entrypoint-initdb.d/10-dev-grants.sh \
    /docker-entrypoint-initdb.d/20-import-abasedb1203.sh \
 && sed -i 's/\r$//' /docker-entrypoint-initdb.d/10-dev-grants.sh /docker-entrypoint-initdb.d/20-import-abasedb1203.sh \
 && chmod 644 /docker-entrypoint-initdb.d/abasedb1203.sql
