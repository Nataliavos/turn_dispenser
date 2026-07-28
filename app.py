# app.py
from utils.logging_setup import setup_logging
from views.console_view import main

if __name__ == "__main__":
    setup_logging()
    main()
