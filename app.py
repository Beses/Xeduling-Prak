#!/usr/bin/env python3
import subprocess
import sys

from pandas.io.common import file_exists

from Datenanalyse.build_revolver_report import build_report
from db.extract_data import extract
from db.init_db import *

if __name__ == "__main__":
    if not file_exists("data.db"):
        init_db()        # create schema
        data = extract() # parse data.json
        import_data(data)# write to DB
        finalize_db()

    build_report()

    subprocess.run([sys.executable, "-m", "streamlit", "run", "viz/streamlit_app.py"])
