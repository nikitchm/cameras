import colorama

colorama.init(autoreset=True)   # autoreset=True ensures that after each print, the styling is reset back to the default terminal color, so you don't have to manually add Style.RESET_ALL.

def print_error(s: str):
    print(colorama.Fore.RED + colorama.Style.BRIGHT + s)

def print_warning(s: str):
    print(colorama.Fore.YELLOW + colorama.Style.BRIGHT + s)
