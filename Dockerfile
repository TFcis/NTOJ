FROM python:3.14-slim
SHELL ["/bin/bash", "-c"]

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

COPY pyproject.toml .

RUN apt update \
    && apt upgrade -y \
    && apt install curl dos2unix xxd xz-utils gcc postgresql-client libpq-dev -y \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && /root/.local/bin/poetry self add poetry-plugin-export \
    && /root/.local/bin/poetry export --without-hashes --output requirements.txt \
    && curl -sSL https://install.python-poetry.org | python3 - --uninstall \
    && pip install -r requirements.txt && rm requirements.txt \
    && apt autoremove --purge -y gcc libpq-dev \
    && apt clean -y

COPY src /ntoj
COPY migration /ntoj/migration
COPY scripts /ntoj/scripts
WORKDIR /ntoj

# TODO: WEB_PROBLEM_STATIC_FILE_DIRECTORY

RUN UNLOCK_PASSWORD_PROCESSED=$(python3 scripts/get_unlock_pwd.py <<<${UNLOCK_PASSWORD}) \
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
COOKIE_SEC = '$(head -c 32 /dev/urandom | xxd -ps -c 128)'\n\
SITE_TITLE = '${SITE_TITLE}'\n\
can_see_code_user = [1]\n\
unlock_pwd = ${UNLOCK_PASSWORD_PROCESSED}\n\
JUDGE_SERVER_LIST = [{'name': 'NTOJ Judge Rewrite (Docker Compose)', 'url': 'ws://judge:2502/judge', 'codes_path': '/code', 'problems_path': '/problem'}]\n\
WEB_PROBLEM_STATIC_FILE_DIRECTORY = ''\n\
BASE_URL = '${BASE_URL}'"\
> config-tmp.py

RUN echo -e "DB_PASSWORD=${DB_PASSWORD}\n\
ADMIN_NAME=${ADMIN_NAME}\n\
ADMIN_MAIL=${ADMIN_MAIL}\n\
ADMIN_PASSWORD=${ADMIN_PASSWORD}"\
> scripts/.env

CMD /ntoj/scripts/runserver.sh
