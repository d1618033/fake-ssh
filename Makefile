FOLDER = fake_ssh

.PHONY: format do_format lint test check

format:
	poetry run black --check ${FOLDER}

do_format:
	poetry run isort ${FOLDER}
	poetry run black ${FOLDER}

lint:
	poetry run flake8 ${FOLDER}
	poetry run pylint ${FOLDER}

test:
	poetry run pytest tests

check: format lint test
