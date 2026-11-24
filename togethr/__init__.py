# Use the pure-Python PyMySQL driver as Django's "MySQLdb" backend. This avoids
# needing a C compiler / MySQL client headers (especially painful on Windows).
try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:  # pragma: no cover - PyMySQL is listed in requirements.txt
    pass
