from dataclasses import dataclass
from pathlib import Path
import csv
import os
import re
import sys 
import datetime
import shutil

from platformdirs import user_data_dir, user_desktop_path
from rich.console import Console 
from rich.table import Table 

FOOD_LABEL = '-- food'
GF_LABEL = '-- guilt free'

def get_amount(t): 
    for date, amount, description in ZERO_AMOUNTS: 
        if t.trans_date == date and t.amount == amount and t.description == description: 
            return 0 
    return t.amount

@dataclass
class DTransaction: 
    trans_date: str 
    amount: float 
    description: str 
    category: str

    def get_renderable_tuple(self): 
        return (self.trans_date, str(self.amount), self.description, self.category)

def make_discover_transaction(line): 
    t =  DTransaction(line[0], float(line[3]), line[2], line[4])
    t.amount = get_amount(t)
    if not t.category.startswith('Payment'):
        if (t.description.startswith('TARGET')
            or t.category.startswith('Supermarket')
            or t.description.startswith('TST*HABANERO')
            or t.description.startswith('POTBELLY')): 
            t.category = FOOD_LABEL

    for date, amount, description in TO_GUILT_FREE: 
        if t.trans_date == date and t.amount == amount and t.description == description: 
            t.category = GF_LABEL

    if t.description.startswith('DIRECTPAY'): 
        t.amount = 0 
    return t

@dataclass 
class CTransaction: 
    trans_date: str 
    amount: float 
    description: str 
    category: str 
    type: str
    memo: str

    def get_renderable_tuple(self): 
        return (self.trans_date, str(self.amount), self.description, self.category, self.type, self.memo)

def make_chase_transaction(line): 
    t = CTransaction(line[0], -1 * float(line[5]), line[2], line[3], line[4], line[6])
    t.amount = get_amount(t)
    if t.description.startswith('AUTOMATIC'): 
        t.amount = 0 
    return t

@dataclass 
class ATransaction: 
    trans_date: str 
    amount: float
    description: str 
    merchant: str 
    category: str
    type: str 
    purchased_by: str

    def get_renderable_tuple(self): 
        return (self.trans_date, str(self.amount), self.description, self.merchant, self.category, self.type, self.purchased_by)

def make_apple_transaction(line): 
    t = ATransaction(line[0], float(line[6]), line[2], line[3], line[4], line[5], line[7])
    t.amount = get_amount(t)
    if t.category == 'Payment' or t.merchant == 'Credit Adjustment':
        t.amount = 0 
    return t

FILES = [ 
    'Discover', 
    'Chase', 
    'Apple'
]

# Whitelist arrays for changing how some files are parsed
TO_GUILT_FREE = []
ZERO_AMOUNTS = []

def usage(console: Console): 
    console.print('[bold]DOWNLOAD LINKS: [/bold]')
    console.print('Use the following links to download activity CSV files and place them in ~/Desktop:')
    console.print('Discover : https://card.discover.com/cardmembersvcs/statements/app/activity?view=R#/ytd')
    console.print('Chase    : https://secure.chase.com/web/auth/dashboard#/dashboard/transactions/1030825251/CARD/BAC')
    console.print('Apple    : Airdop from Wallet app')
    console.print('')

    console.print('[bold]USAGE: [/bold]')
    console.print('$ python main.py \\[month] \\[options]')
    console.print('[bold]\nOPTIONS: [/bold]')
    console.print('-c | --clean  : Move data file to archive directory')
    console.print('-h | --help   : Print usage and exit')
    
def main(): 
    console = Console()
    if '--help' in sys.argv or '-h' in sys.argv: 
        usage(console) 
        sys.exit(1)

    # load whitelist data from separate file 
    whitelist_fn = Path(__file__).resolve().parent.joinpath('whitelists/to_guilt_free.csv')
    whitelist_file = whitelist_fn.open()
    for line in whitelist_file.readlines(): 
        l = [ value.strip() for value in line.split(chr(9474)) ]
        TO_GUILT_FREE.append((l[0], float(l[1]), l[2]))

    # load whitelist data from separate file 
    whitelist_fn = Path(__file__).resolve().parent.joinpath('whitelists/zero_amounts.csv')
    whitelist_file = whitelist_fn.open()
    for line in whitelist_file.readlines(): 
        l = [ value.strip() for value in line.split(chr(9474)) ]
        ZERO_AMOUNTS.append((l[0], float(l[1]), l[2]))

    # set up month to analyze
    curr_month = str(datetime.datetime.now().month)
    try: 
        if len(sys.argv) > 1 and not sys.argv[1].startswith('--') and 1 <= int(sys.argv[1]) <= 12: 
            curr_month = sys.argv[1]
        else:
            console.print(f'[ INFO ] Did not provide valid month in CLI... defaulting to month: {curr_month}')
    except: 
        print(f'[ ERROR ] Failed to parse arugments: {sys.argv}')
        usage(console)
        sys.exit(1)

    # setup user data path with app name
    appname = 'credit-transaction-parser'
    data_path = user_data_dir(appname)
    if not os.path.exists(data_path): 
        os.mkdir(data_path)
        console.print(f'[ INFO ] Created data path: {data_path}')

    # Load Transactions
    transactions = { 
        'Discover': [], 
        'Chase': [], 
        'Apple': []
    }
    data_files = [
        file for file in os.listdir(user_desktop_path()) if file.lower().endswith('.csv')
    ]
    for filename in data_files:
        file = Path(user_desktop_path(), filename).open()
        next(file) # skip the first line of headers
        reader = csv.reader(file)

        if filename.startswith('Discover'): 
            transactions['Discover'] = [ make_discover_transaction(line) for line in reader ]
            
        elif filename.startswith('Chase'):
            transactions['Chase'] = [ make_chase_transaction(line) for line in reader ]
            transactions['Chase'].reverse()

        elif filename.startswith('Apple'): 
            transactions['Apple'] = [ make_apple_transaction(line) for line in reader ]
    console.print()

    # filter transactions for month
    for k, v in transactions.items(): 
        transactions[k] = list(filter(lambda x: x.trans_date.startswith(curr_month), v))
        
    print_transaction_tables(console, transactions)

    print_totals_tables(console, transactions)

    # Save Parsed Data 

    # Move Original and Parsed Data into Archive
    if '--clean' in sys.argv: 
        for file in data_files: 
            shutil.move(f'{user_desktop_path()}/{file}', f'{user_data_dir(appname)}/{file}')
        console.print(f'[ INFO ] Moved data files from "{user_desktop_path()}" to "{user_data_dir(appname)}"')

def set_transaction_style(transaction): 
    if transaction.amount < 0: 
        return 'blue'
    elif transaction.amount == 0: 
        return 'black'
    elif transaction.category == FOOD_LABEL: 
        return 'bright_black'
    return 'yellow'

def print_transaction_tables(console, transactions): 
    discover_trans_table = Table(title='Discover Transactions', expand=True, border_style='bright_black', title_style='bold')
    discover_trans_table.add_column('Transaction Date', header_style='white', style='white')
    discover_trans_table.add_column('Amount',           header_style='white', style='white')
    discover_trans_table.add_column('Description',      header_style='white', style='white')
    discover_trans_table.add_column('Category',         header_style='white', style='white')
    for transaction in transactions['Discover']: 
        discover_trans_table.add_row(*transaction.get_renderable_tuple(), style=set_transaction_style(transaction))
    console.print(discover_trans_table)

    chase_trans_table = Table(title='Chase Transactions', expand=True, border_style='bright_black', title_style='bold')
    chase_trans_table.add_column('Transaction Date', header_style='white', style='white')
    chase_trans_table.add_column('Amount',           header_style='white', style='white')
    chase_trans_table.add_column('Description',      header_style='white', style='white')
    chase_trans_table.add_column('Category',         header_style='white', style='white')
    chase_trans_table.add_column('Type',             header_style='white', style='white')
    chase_trans_table.add_column('Memo',             header_style='white', style='white')
    for transaction in transactions['Chase']: 
        chase_trans_table.add_row(*transaction.get_renderable_tuple(), style=set_transaction_style(transaction))
    console.print(chase_trans_table)

    apple_trans_table = Table(title='Apple Transactions', expand=True, border_style='bright_black', title_style='bold')
    apple_trans_table.add_column('Transaction Date', header_style='white', style='white')
    apple_trans_table.add_column('Amount',           header_style='white', style='white')
    apple_trans_table.add_column('Description',      header_style='white', style='white')
    apple_trans_table.add_column('Merchant',         header_style='white', style='white')
    apple_trans_table.add_column('Category',         header_style='white', style='white')
    apple_trans_table.add_column('Type',             header_style='white', style='white')
    apple_trans_table.add_column('Purchased By',     header_style='white', style='white')
    for transaction in transactions['Apple']: 
        style = 'green' if transaction.amount < 0 else 'white'
        apple_trans_table.add_row(*transaction.get_renderable_tuple(), style=set_transaction_style(transaction))
    console.print(apple_trans_table)

def print_totals_tables(console, transactions): 
    total = 0 
    groceries = 0 
    for _, v in transactions.items():
        for transaction in v:
            if transaction.category == FOOD_LABEL: 
                groceries += transaction.amount 
            total += transaction.amount

    # print formatted tables
    account_table = Table(title='Account Totals', border_style='bright_black', title_style='bold') 
    account_table.add_column('Account',      header_style='white', style='white', justify='left')
    account_table.add_column('Amount (USD)', header_style='white', style='white', justify='right')
    account_table.add_row('Discover', f'{sum([transaction.amount for transaction in transactions['Discover']]):.{0}f}' )
    account_table.add_row('Chase',    f'{sum([transaction.amount for transaction in transactions['Chase']]):.{0}f}' )
    account_table.add_row('Apple',    f'{sum([transaction.amount for transaction in transactions['Apple']]):.{0}f}' )
    console.print(account_table)

    general_table = Table(title='Monthly Totals', border_style='bright_black', title_style='bold') 
    general_table.add_column('Category',     header_style='white', justify='left',  style='white')
    general_table.add_column('Amount (USD)', header_style='white', justify='right', style='green')
    general_table.add_row('Guilt Free',  f'{total-groceries:.{0}f}' )
    general_table.add_row('Groceries',   f'{groceries:.{0}f}' )
    general_table.add_row('Grand Total', f'{total:.{0}f}' )
    console.print(general_table)

if __name__ == '__main__': 
    main() 