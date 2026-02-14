## Set up a Python Virtual Environment

```zsh
python -m venv venv
. venv/bin/activate
```

## Install the dependencies
```zsh
pip install -r requirements.txt
```

## Install FastAPI

```zsh
pip install "fastapi[standard]"
```

## Running the application
```zsh
fastapi dev --host 127.0.0.1 --port 8000 app/main.py
```

fastapi run app/main.py --host 127.0.0.1 --port 8000