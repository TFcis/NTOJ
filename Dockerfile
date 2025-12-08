# TODO: fix upgrade.py, install.sh

# == development image ==

FROM python:3.14-slim AS development
SHELL ["/bin/bash", "-c"]

WORKDIR /ntoj
ENV PATH="/root/.local/bin:$PATH"
COPY pyproject.toml .
RUN apt update \
    && apt upgrade -y \
    && apt install curl dos2unix xz-utils gcc postgresql-client libpq-dev -y \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && poetry install && poetry add coverage requests \
    && apt autoremove --purge -y gcc libpq-dev curl \
    && apt clean -y \
    && rm -rf /var/lib/apt/lists/

COPY src /ntoj
COPY migration /ntoj/migration
COPY scripts /ntoj/scripts

RUN UNLOCK_PASSWORD_PROCESSED=$(echo "UNLOCK_PASSWORD" | poetry run python3 scripts/get_unlock_pwd.py) \
COOKIE_SEC=$(python3 -c "import sys; print(open('/dev/urandom','rb').read(32).hex())") \
&& mv /ntoj/static /ntoj/static-tmp \
&& echo -e "import datetime\n\
TIMEZONE   = datetime.timezone(datetime.timedelta(hours=+8))\n\
PORT       = 5500\n\
REDIS_DB   = 1\n\
REDIS_HOST = 'cache'\n\
DBNAME_OJ  = 'ntoj'\n\
DBUSER_OJ  = 'ntoj'\n\
DBHOST_OJ  = 'db'\n\
DBPW_OJ    = 'ntoj'\n\
COOKIE_SEC = '${COOKIE_SEC}'\n\
SITE_TITLE = 'NTOJ-Dev'\n\
can_see_code_user = [1]\n\
unlock_pwd = ${UNLOCK_PASSWORD_PROCESSED}\n\
JUDGE_SERVER_LIST = [{'name': 'NTOJ Judge Rewrite (Docker Compose)', 'url': 'ws://judge:2502/judge', 'codes_path': '/code', 'problems_path': '/problem'}]\n\
BASE_URL = '/'"\
> config-tmp.py \
&& echo -e "DB_PASSWORD=ntoj\n\
ADMIN_NAME=admin\n\
ADMIN_MAIL=admin@admin\n\
ADMIN_PASSWORD=admin1234"\
> scripts/.env \
&& echo "" > docker-dev

EXPOSE 5500
CMD bash

# == release image ==

FROM python:3.14-alpine AS builder
COPY pyproject.toml .

RUN apk add --no-cache curl gcc musl-dev libpq-dev build-base python3-dev \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && /root/.local/bin/poetry self add poetry-plugin-export \
    && /root/.local/bin/poetry export --without-hashes --output requirements.txt \
    && curl -sSL https://install.python-poetry.org | python3 - --uninstall \
    && pip install --user -r requirements.txt

FROM python:3.14-alpine AS release
COPY --from=builder /root/.local /root/.local
RUN apk add --no-cache postgresql17-client dos2unix tar xz

COPY src /ntoj
COPY migration /ntoj/migration
COPY scripts /ntoj/scripts
WORKDIR /ntoj

ARG DB_PASSWORD
ARG UNLOCK_PASSWORD
ARG TIMEDELTA
ARG SITE_TITLE
ARG ADMIN_NAME
ARG ADMIN_MAIL
ARG ADMIN_PASSWORD
ARG BASE_URL

RUN UNLOCK_PASSWORD_PROCESSED=$(echo "${UNLOCK_PASSWORD}" | python3 scripts/get_unlock_pwd.py) \
&& COOKIE_SEC=$(python3 -c "import sys; print(open('/dev/urandom','rb').read(32).hex())") \
&& rm -rf tests \
&& rm runintegratedtest.sh runintegratedtest.py \
&& rm rununittest.sh rununittest.py upgrade.py \
&& mv /ntoj/static /ntoj/static-tmp \
&& echo -e "import datetime\n\
TIMEZONE   = datetime.timezone(datetime.timedelta(hours=${TIMEDELTA}))\n\
PORT       = 5500\n\
REDIS_DB   = 1\n\
REDIS_HOST = 'cache'\n\
DBNAME_OJ  = 'ntoj'\n\
DBUSER_OJ  = 'ntoj'\n\
DBHOST_OJ  = 'db'\n\
DBPW_OJ    = '${DB_PASSWORD}'\n\
COOKIE_SEC = '${COOKIE_SEC}'\n\
SITE_TITLE = '${SITE_TITLE}'\n\
can_see_code_user = [1]\n\
unlock_pwd = ${UNLOCK_PASSWORD_PROCESSED}\n\
JUDGE_SERVER_LIST = [{'name': 'NTOJ Judge Rewrite (Docker Compose)', 'url': 'ws://judge:2502/judge', 'codes_path': '/code', 'problems_path': '/problem'}]\n\
BASE_URL = '${BASE_URL}'"\
> config-tmp.py \
&& echo -e "DB_PASSWORD=${DB_PASSWORD}\n\
ADMIN_NAME=${ADMIN_NAME}\n\
ADMIN_MAIL=${ADMIN_MAIL}\n\
ADMIN_PASSWORD=${ADMIN_PASSWORD}"\
> scripts/.env \
&& echo "" > docker-release

EXPOSE 5500
CMD /ntoj/scripts/runserver.sh
