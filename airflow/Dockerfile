# Airflow image for the openfda_daily DAG: the official image plus the
# SQL Server ODBC driver and the pipeline's few extra Python packages.
FROM apache/airflow:3.3.2-python3.12

USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg ca-certificates && \
    . /etc/os-release && \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/${VERSION_ID}/prod ${VERSION_CODENAME} main" \
        > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 && \
    rm -rf /var/lib/apt/lists/*
USER airflow

# requests and SQLAlchemy already ship with Airflow. Install the rest against
# Airflow's constraints file so nothing Airflow depends on gets upgraded.
COPY requirements-airflow.txt /tmp/requirements-airflow.txt
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /tmp/requirements-airflow.txt \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-3.12.txt"
