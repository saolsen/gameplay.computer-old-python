# Gameplay

Gameplay is a bunch of experimental AI stuff for playing games

## Dependencies
* postgres
* rust (to build the native code)
* python 3.11
* tox (`pip install tox`)
* maturin (`pip install maturin`)


## Running
First build the rust code.
```
$ maturin build
```

Set up two databases, one for the web app and one for testing.
Set the environment variables `DATABASE_URL` and `TEST_DATABASE_URL`. Something like this.
```
$ createdb gameplay
$ createdb gameplay_test
$ export DATABASE_URL="postgresql://localhost:5432/gameplay"
$ export TEST_DATABASE_URL="postgresql://localhost:5432/gameplay_test"
```

Then, run the migrations on the two databases to get them up to date.

```
$ tox -e alembic -- upgrade head
$ DATABASE_URL=$TEST_DATABASE_URL tox -e alembic -- upgrade head
```

Try the tests and lint job
```
$ tox -e test
$ tox -e webtest
$ tox -e lint
```

Then you can run the web app locally.
```
$ tox -e web
```

If you want to create another virtual environment for your editor to use or local testing you can do that like this.

```
$ python3.11 -m venv .venv
$ . .venv/bin/activate
$ pip install --upgrade pip
$ pip install tox maturin
$ maturin build
$ pip install -e '.[test,lint,web,migrate]'
```
