# Shadow module that blocks pandas imports for dbt-snowflake invocations.
#
# The pandas install in this python is binary-incompatible with numpy and
# raises ValueError at import time. snowflake-connector-python imports pandas
# eagerly but only handles ImportError (falling back to a MissingPandas stub,
# which is fine for SQL-only dbt work). Prepending this directory to
# PYTHONPATH converts the crash into the ImportError the connector expects:
#
#   PYTHONPATH=tools/pandas_disabled python3 -m dbt.cli.main <cmd> --profiles-dir .
raise ImportError("pandas is disabled for dbt runs in this environment")
