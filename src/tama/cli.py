"""Command-line entry point (``tama``)."""

from typing import Annotated

import typer

from tama import __version__

app = typer.Typer(add_completion=False, no_args_is_help=False)


def _version_callback(value: bool) -> None:  # noqa: FBT001 - signature dictated by Typer
    if value:
        typer.echo(f"tama-go-chi {__version__}")
        raise typer.Exit


@app.callback(invoke_without_command=True)
def root(
    *,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """Look after your terminal pet."""
    del version  # handled eagerly by its callback
    typer.echo("The tama-go-chi TUI is not implemented yet.")
    raise typer.Exit(code=1)


def main() -> None:
    """Run the CLI."""
    app()
