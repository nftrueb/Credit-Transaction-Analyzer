from dataclasses import dataclass
import os
import re
import sys 
import datetime
import shutil

from platformdirs import user_data_dir, user_desktop_path
from rich.console import Console 
from rich.table import Table 

@dataclass
class DTransaction: 
    trans_date: str 
    amount: float 
    description: str 
    category: str

    def get_renderable_tuple(self): 
        return (self.trans_date, str(self.amount), self.description, self.category)

def make_discover_transaction(line): 
    parsed = line.split(',')
    t =  DTransaction(parsed[0], float(parsed[3]), parsed[2], parsed[4])
    if not t.category.startswith('Payment'):
        if (t.description.startswith('TARGET')
            or t.category.startswith('Supermarket')
            or t.description.startswith('TST*HABANERO')
            or t.description.startswith('POTBELLY')): 
            t.category = 'food'

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
    parsed = line.split(',')
    t = CTransaction(parsed[0], -1 * float(parsed[5]), parsed[2], parsed[3], parsed[4], parsed[6])
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
    parsed = line.split(',')
    t = ATransaction(parsed[0], float(parsed[6]), parsed[2], parsed[3], parsed[4], parsed[5], parsed[7])
    if t.category == 'Payment': 
        t.amount = 0 
    return t

FILES = [ 
    'Discover', 
    'Chase', 
    'Apple'
]

def main(): 
    console = Console()

    # set up month to analyze
    curr_month = str(datetime.datetime.now().month)
    if len(sys.argv) > 1 and 1 <= int(sys.argv[1]) <= 12: 
        curr_month = sys.argv[1]
    else:
        console.print(f'[ INFO ] Did not provide valid month in CLI... defaulting to month: {curr_month}')

    # setup user data path with app name
    appname = 'credit-transaction-parser'
    data_path = user_data_dir(appname)
    if not os.path.exists(data_path): 
        os.mkdir(data_path)
        console.print(f'[ INFO ] Created data path: {data_path}')

    # Load Transactions
    transactions = { }
    data_files = [
        file for file in os.listdir(user_desktop_path()) if file.lower().endswith('.csv')
    ]
    for file in data_files:
        with open(f'{user_desktop_path()}/{file}', 'r') as f: 
            console.print(f'[ DEBUG ] Opening "{user_desktop_path()}/{file}"')
            contents = f.read()
            scrubbed, _ = re.subn(r'"', '', contents)
            lines = scrubbed.split('\n')[1:-1]

        if file.startswith('Discover'): 
            transactions['Discover'] = [ make_discover_transaction(line) for line in lines ]
            
        elif file.startswith('Chase'):
            transactions['Chase'] = [ make_chase_transaction(line) for line in lines ]
            transactions['Chase'].reverse()

        elif file.startswith('Apple'): 
            transactions['Apple'] = [ make_apple_transaction(line) for line in lines ]
    console.print()

    # filter transactions for month
    for k, v in transactions.items(): 
        transactions[k] = list(filter(lambda x: x.trans_date.startswith(curr_month), v))
        
    print_transaction_tables(console, transactions)

    print_totals_tables(console, transactions)

    # Save Parsed Data 

    # Move Original and Parsed Data into Archive
    for file in data_files: 
        shutil.move(f'{user_desktop_path()}/{file}', f'{user_data_dir(appname)}/{file}')
    console.print(f'[ INFO ] Moved data files from "{user_desktop_path()}" to "{user_data_dir(appname)}"')

def print_transaction_tables(console, transactions): 
    discover_trans_table = Table(title='Discover Transactions', expand=True)
    discover_trans_table.add_column('Transaction Date', 'white')
    discover_trans_table.add_column('Amount', 'white')
    discover_trans_table.add_column('Description', 'white')
    discover_trans_table.add_column('Category', 'white')
    for transaction in transactions['Discover']: 
        discover_trans_table.add_row(*transaction.get_renderable_tuple())
    console.print(discover_trans_table)

    chase_trans_table = Table(title='Chase Transactions', expand=True)
    chase_trans_table.add_column('Transaction Date', 'white')
    chase_trans_table.add_column('Amount', 'white')
    chase_trans_table.add_column('Description', 'white')
    chase_trans_table.add_column('Category', 'white')
    chase_trans_table.add_column('Type', 'white')
    chase_trans_table.add_column('Memo', 'white')
    for transaction in transactions['Chase']: 
        chase_trans_table.add_row(*transaction.get_renderable_tuple())
    console.print(chase_trans_table)

    apple_trans_table = Table(title='Apple Transactions', expand=True)
    apple_trans_table.add_column('Transaction Date', 'white')
    apple_trans_table.add_column('Amount', 'white')
    apple_trans_table.add_column('Description', 'white')
    apple_trans_table.add_column('Merchant', 'white')
    apple_trans_table.add_column('Category', 'white')
    apple_trans_table.add_column('Type', 'white')
    apple_trans_table.add_column('Purchased By', 'white')
    for transaction in transactions['Apple']: 
        apple_trans_table.add_row(*transaction.get_renderable_tuple())
    console.print(apple_trans_table)

def print_totals_tables(console, transactions): 
    total = 0 
    groceries = 0 
    for _, v in transactions.items():
        for transaction in v:
            if transaction.category == 'food': 
                groceries += transaction.amount 
            total += transaction.amount

    # print formatted tables
    account_table = Table(title='Account Totals', header_style='white') 
    account_table.add_column('Account', justify='left')
    account_table.add_column('Amount (USD)', justify='right')
    account_table.add_row('Discover', f'{sum([transaction.amount for transaction in transactions['Discover']]):.{0}f}' )
    account_table.add_row('Chase', f'{sum([transaction.amount for transaction in transactions['Chase']]):.{0}f}' )
    account_table.add_row('Apple', f'{sum([transaction.amount for transaction in transactions['Apple']]):.{0}f}' )
    console.print(account_table)

    general_table = Table(title='Monthly Totals', header_style='white') 
    general_table.add_column('Category', justify='left')
    general_table.add_column('Amount (USD)', justify='right')
    general_table.add_row('Guilt Free', f'{total-groceries:.{0}f}' )
    general_table.add_row('Groceries', f'{groceries:.{0}f}' )
    general_table.add_row('Grand Total', f'{total:.{0}f}' )
    console.print(general_table)

if __name__ == '__main__': 
    main() 