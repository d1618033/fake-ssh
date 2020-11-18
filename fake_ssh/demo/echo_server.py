import sys

from logbook import StreamHandler

from ..server import Server


def main():
    StreamHandler(sys.stdout).push_application()
    Server(command_handler=lambda c: c, port=5050).run_blocking()


if __name__ == "__main__":
    main()
