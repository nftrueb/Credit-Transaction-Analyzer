#! /bin/bash

./venv/bin/pyinstaller \
    --noconfirm \
    --clean \
    --name credit-transaction-parser \
    --onefile \
    main.py

sudo cp dist/credit-transaction-parser /usr/local/bin
