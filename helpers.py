import requests
import cs50
import mysql.connector
from time import gmtime, strftime
from datetime import date, timedelta
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from flask import Flask, redirect, request, render_template, session

with open("db_creds.txt", "r") as f:
    password = f.read()

mydb_conn = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    password=password,
    database="finance"
)
finance_db = mydb_conn.cursor()

with open("api_token.txt", "r") as f:
    the_api_key = f.read()
the_api_token = "?token=" + the_api_key
the_base_url = "https://cloud-sse.iexapis.com/stable/"
stock = "stock/"
ref_data = "ref-data/"

def get_quote(symbol):
    try:
        r = requests.get(the_base_url + stock + symbol + "/quote" + the_api_token)
    except requests.exceptions.ConnectionError:
        return 500

    if r.status_code != 200:
        return r.status_code

    try:
        the_result = r.json()
        return the_result
    except (KeyError, TypeError, ValueError):
        return 500

def get_company_info(symbol):
    try:
        r = requests.get(the_base_url + stock  + symbol + "/company" + the_api_token)
    except requests.exceptions.ConnectionError:
        return 500

    if r.status_code != 200:
        return r.status_code

    try:
        the_result = r.json()
        return the_result
    except (KeyError, TypeError, ValueError):
        return 500

def get_logo(symbol):
    try:
        r = requests.get(the_base_url + stock  + symbol + "/logo" + the_api_token)
    except requests.exceptions.ConnectionError:
        return 500

    if r.status_code != 200:
        return r.status_code

    try:
        the_result = r.json()
        return the_result
    except (KeyError, TypeError, ValueError):
        return 500

def get_symbols(filters):
    if ("stock_name" in filters):
        stock_name = filters["stock_name"].replace("'", "\\'")
        finance_db.execute(f"SELECT symbol, exchange, name, region, currency FROM symbols WHERE (name LIKE '%{stock_name}%' OR symbol LIKE '%{stock_name}%') AND type='cs'")
    else:
        finance_db.execute("SELECT symbol, exchange, name, region, currency FROM symbols WHERE type = 'cs'")
    return finance_db.fetchall()

def add_user(fname, lname, email, username, passwd):
    fname = fname.replace("'", "\\'")
    lname = lname.replace("'", "\\'")
    email = email.replace("'", "\\'")
    username = username.replace("'", "\\'")
    passwd = generate_password_hash(passwd, "sha256")
    passwd = passwd.replace("'", "\\'")
    print(f"INSERT INTO users (username, email, fname, lname, hash) VALUES ('{username}', '{email}', '{fname}', '{lname}', '{passwd}')")
    try:
        finance_db.execute(f"INSERT INTO users (username, email, fname, lname, hash) VALUES ('{username}', '{email}', '{fname}', '{lname}', '{passwd}')")
        mydb_conn.commit()
    except mysql.connector.errors.IntegrityError:
        return False
    return True

def check_user(username, passwd):
    username = username.replace("'", "\\'")
    finance_db.execute(f"SELECT username, email, fname, lname, hash, id FROM users WHERE username = '{username}'")
    the_result = finance_db.fetchall()
    if len(the_result) != 1 or not check_password_hash(the_result[0][4], passwd):
        return False
    else:
        return the_result

def change_passwd(user_id, old_passwd, new_passwd):
    finance_db.execute(f"SELECT hash FROM users WHERE id = '{user_id}'")
    the_old_hash = finance_db.fetchall()[0][0]
    if check_password_hash(the_old_hash, old_passwd):
        the_new_hash = generate_password_hash(new_passwd, "sha256")
        finance_db.execute(f"UPDATE users SET hash = '{the_new_hash}' WHERE id = '{user_id}'")
        mydb_conn.commit()
        return True
    else:
        return False

def get_positions(user_id):
    finance_db.execute(f"SELECT id, quantity, price, date, symbol FROM positions WHERE user_id = '{user_id}' ORDER BY symbol")
    the_positions = finance_db.fetchall()
    for i in range(len(the_positions)):
        the_positions[i] = list(the_positions[i])
        finance_db.execute(f"SELECT name FROM symbols WHERE symbol = '{the_positions[i][4]}'")
        the_positions[i].append(finance_db.fetchall()[0][0])
    return the_positions

def get_cash_amount(user_id):
    finance_db.execute(f"SELECT cash FROM users WHERE id = '{user_id}'")
    the_result = finance_db.fetchall()[0][0]
    return the_result

def buy_stock(user_id, symbol, quantity):
    the_available_cash = get_cash_amount(user_id)
    the_quote = get_quote(symbol)
    the_stock_price = the_quote["latestPrice"]
    if the_quote in range(400,600):
        return the_quote
    try:
        quantity = int(quantity)
    except:
        return 499
    the_total_price = the_stock_price * quantity
    if the_total_price > the_available_cash:
        return 499
    else:
        the_remaining_balance = int(the_available_cash) - the_total_price
        finance_db.execute(f"UPDATE users SET cash = '{the_remaining_balance}' WHERE id = '{user_id}'")
        mydb_conn.commit()
        finance_db.execute(f"INSERT INTO positions (quantity, price, date, symbol, user_id) values ('{quantity}', '{the_stock_price}', '{date.today()}', '{the_quote['symbol']}', '{user_id}') ON DUPLICATE KEY UPDATE price = (((price * quantity) + ({the_stock_price} * {quantity})) / (quantity + {quantity})), quantity = quantity + {quantity}, date = '{date.today()}'")
        mydb_conn.commit()
        finance_db.execute(f"INSERT INTO history (symbol, action, quantity, price, transaction_date, transaction_time, user_id) values ('{the_quote['symbol']}', 'B', '{quantity}', '{the_stock_price}', '{date.today()}', \"{strftime('%H:%M:%S', gmtime())}\", '{user_id}')")
        mydb_conn.commit()
        return 200

def sell_stock(user_id, the_symbol, the_sell_quantity):
    finance_db.execute(f"SELECT quantity, price FROM positions WHERE user_id = '{user_id}' AND symbol = '{the_symbol}'")
    the_result = finance_db.fetchall()
    the_total_quantity = the_result[0][0]
    the_total_price = the_result[0][1]
    try:
        the_sell_quantity = int(the_sell_quantity)
    except:
        return False
    if the_sell_quantity > the_total_quantity:
        return False
    the_remaining_quantity = the_total_quantity - the_sell_quantity
    the_sell_price = get_quote(the_symbol)["latestPrice"]
    if the_remaining_quantity != 0:
        the_remaining_price = ((the_total_price * the_total_quantity - (the_sell_price * the_sell_quantity)) / the_remaining_quantity)
        finance_db.execute(f"UPDATE positions SET price = '{the_remaining_price}', quantity = '{the_remaining_quantity}' WHERE symbol = '{the_symbol}'")
        mydb_conn.commit()
    else:
        the_remaining_price = 0
        finance_db.execute(f"DELETE FROM positions WHERE symbol = '{the_symbol}'")
        mydb_conn.commit()
    finance_db.execute(f"UPDATE users SET cash = cash - '{the_sell_price * the_sell_quantity}' WHERE id = '{user_id}'")
    mydb_conn.commit()
    finance_db.execute(f"INSERT INTO history (symbol, action, quantity, price, transaction_date, transaction_time, user_id) values ('{the_symbol}', 'S', '{the_sell_quantity}', '{the_sell_price}', '{date.today()}', \"{strftime('%H:%M:%S', gmtime())}\", '{user_id}')")
    mydb_conn.commit()
    return True

def get_history(user_id):
    finance_db.execute(f"SELECT symbol, action, quantity, price, transaction_date, transaction_time FROM history WHERE user_id = '{user_id}'")
    the_history = finance_db.fetchall()
    for i in range(len(the_history)):
        the_history[i] = list(the_history[i])
        if (the_history[i][1] == "B"):
            the_history[i][1] = "BUY"
        elif (the_history[i][1] == "S"):
            the_history[i][1] = "SELL"
        the_utc_offset = get_timezone()
        the_history[i][5] += timedelta(hours=the_utc_offset)
        finance_db.execute(f"SELECT name FROM symbols WHERE symbol = '{the_history[i][0]}'")
        the_history[i].insert(1, finance_db.fetchall()[0][0])
    return the_history

def add_cash(user_id, the_amount):
    finance_db.execute(f"UPDATE users SET cash = cash + '{the_amount}' WHERE id = '{user_id}'")
    mydb_conn.commit()
    return True

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def usd(value):
    return f"${value:,.2f} USD"

def get_timezone():
    return int(int(strftime("%z")) / 100)
