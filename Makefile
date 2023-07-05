FOLDER = fake_ssh tests

.PHONY: format do_format lint test check

format:
	poetry run black --check ${FOLDER}

do_format:
	poetry run isort ${FOLDER}
	poetry run black ${FOLDER}

lint:
	poetry run flake8 fake_ssh
	poetry run pylint fake_ssh

test:
	poetry run pytest -s -vvv tests

check: format lint test
