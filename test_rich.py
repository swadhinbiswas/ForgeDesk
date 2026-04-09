from rich.console import Console
from rich.theme import Theme
import time

custom_theme = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "danger": "bold red"
})
console = Console(theme=custom_theme)
console.print("hello [info]world[/info]")
