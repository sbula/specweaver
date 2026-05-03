import typer

app = typer.Typer()
sub = typer.Typer()

@sub.command()
def hello():
    print("hello")

@sub.command()
def world():
    print("world")

app.add_typer(sub)

if __name__ == "__main__":
    app()
