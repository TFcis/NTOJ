FROM python:3.14-alpine AS builder
COPY pyproject.toml .

RUN apk add --no-cache curl gcc musl-dev libpq-dev build-base python3-dev \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && /root/.local/bin/poetry self add poetry-plugin-export \
    && /root/.local/bin/poetry export --without-hashes --output requirements.txt \
    && curl -sSL https://install.python-poetry.org | python3 - --uninstall \
    && pip install --user -r requirements.txt

# TODO: add develop version image, use python3.14-slim, start from bash, contain tests code

FROM python:3.14-alpine AS release
COPY --from=builder /root/.local /root/.local

ARG DB_PASSWORD
ARG UNLOCK_PASSWORD
ARG TIMEDELTA
ARG SITE_TITLE
ARG ADMIN_NAME
ARG ADMIN_MAIL
ARG ADMIN_PASSWORD
ARG BASE_URL
ENV DB_PASSWORD=$DB_PASSWORD
ENV UNLOCK_PASSWORD=$UNLOCK_PASSWORD
ENV TIMEDELTA=$TIMEDELTA
ENV SITE_TITLE=$SITE_TITLE
ENV ADMIN_NAME=$ADMIN_NAME
ENV ADMIN_MAIL=$ADMIN_MAIL
ENV ADMIN_PASSWORD=$ADMIN_PASSWORD
ENV BASE_URL=$BASE_URL

COPY src /ntoj
COPY migration /ntoj/migration
COPY scripts /ntoj/scripts
WORKDIR /ntoj

RUN apk add --no-cache postgresql17-client dos2unix tar xz \
    && UNLOCK_PASSWORD_PROCESSED=$(echo "${UNLOCK_PASSWORD}" | python3 scripts/get_unlock_pwd.py) \
    && COOKIE_SEC=$(python3 -c "import sys; print(open('/dev/urandom','rb').read(32).hex())") \
    && rm -rf /ntoj/tests && mv /ntoj/static /ntoj/static-tmp \
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
    > scripts/.env

CMD /ntoj/scripts/runserver.sh
