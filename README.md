## Set up a Python Virtual Environment

```zsh
python3 -m venv venv
. venv/bin/activate
```

## Install the dependencies
```zsh
pip3 install -r requirements.txt
```

## Install FastAPI

```zsh
pip install "fastapi[standard]"
```

## Running the application
```zsh
fastapi dev --host 127.0.0.1 --port 8001 main.py
```

