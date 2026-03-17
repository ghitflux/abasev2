#!/bin/sh
set -eu

if [ -n "${MYSQL_USER:-}" ]; then
  mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" <<SQL
GRANT CREATE, DROP ON *.* TO '${MYSQL_USER}'@'%';
GRANT ALL PRIVILEGES ON \`test_${MYSQL_DATABASE}\`.* TO '${MYSQL_USER}'@'%';
FLUSH PRIVILEGES;
SQL
fi
