from helpers import *
import cs50
from flask import Flask, redirect, request, render_template, session
from flask_session import Session

from datetime import datetime, timedelta

app = Flask(__name__)

app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

app.jinja_env.filters["usd"] = usd

@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route("/")
def home():
    print(session)
    if "name" not in session:
        return render_template("landing.html")
    else:
        return redirect("/account")

@app.route("/account")
@login_required
def account():
    the_current_positions_list = get_positions(session["user_id"])
    the_current_positions = []
    the_live_result = 0
    for i in the_current_positions_list:
        the_current_working_position = []
        for j in i:
            the_current_working_position.append(j)
        the_current_working_position.append(get_quote(the_current_working_position[4])["latestPrice"])
        the_current_working_position.append((the_current_working_position[6] - the_current_working_position[2]) * the_current_working_position[1])
        the_live_result += ((the_current_working_position[6] - the_current_working_position[2]) * the_current_working_position[1])
        the_current_positions.append(the_current_working_position)
    the_free_funds = get_cash_amount(session["user_id"])
    the_account_value = the_live_result + float(the_free_funds)
    return render_template("account.html", the_current_positions=the_current_positions, the_live_result=the_live_result, the_free_funds=the_free_funds, the_account_value=the_account_value)

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")
        the_result = get_quote(symbol)
        the_utc_offset = get_timezone()

        if the_result in range(400,500):
            the_result = "Please change your request and try again. Error code: " + str(the_result)
            return render_template("error.html", message=the_result)
        elif the_result in range(500, 600):
            the_result = "There was an internal server error! Please try again later. Error code: " + str(the_result)
            return render_template("error.html", message=the_result)

        the_update_time = datetime.utcfromtimestamp(round(the_result["latestUpdate"] / 1000)) + timedelta(hours=the_utc_offset)
        the_update_time = the_update_time.strftime("%Y/%m/%d %H:%M:%S")
        the_company_info = get_company_info(symbol)
        the_logo = get_logo(symbol)["url"]

        return render_template("quote_result.html", the_result=the_result, last_updated=the_update_time, the_company_info=the_company_info, the_logo=the_logo)

@app.route("/index")
@login_required
def index():
    the_list = get_symbols(request.args)
    return render_template("index.html", symbols=the_list)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = request.form.get("symbol")
        quantity = request.form.get("quantity")
        the_result = buy_stock(session["user_id"], symbol, quantity)
        if the_result == 200:
            return render_template("success.html", message=f"Successfully bought {quantity} shares of {symbol.upper()}")
        elif the_result == 499:
            return render_template("error.html", message="Insufficient Funds")
        elif the_result in range(400,500):
            the_result = f"Could not buy {quantity} shares of {symbol.upper()}. Please change your request and try again. Error code: " + str(the_result)
            return render_template("error.html", message=the_result)
        elif the_result in range(500, 600):
            the_result = f"Could not buy {quantity} shares of {symbol.upper()}. There was an internal server error! Please try again later. Error code: " + str(the_result)
            return render_template("error.html", message=the_result)
        else:
            return render_template("error.html", message=f"Could not buy {quantity} shares of {symbol.upper()}. Unknown Error")

@app.route("/sell", methods=["POST"])
@login_required
def sell():
    symbol = request.form.get("symbol")
    quantity = request.form.get("quantity")
    sell_stock(session["user_id"], symbol, quantity)
    return redirect("/account")

@app.route("/history")
@login_required
def history():
    the_history = get_history(session["user_id"])
    return render_template("history.html", the_history=the_history)

@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()

    if request.method == "GET":
        return render_template("login.html")
    else:
        username = request.form.get("username")
        passwd = request.form.get("passwd")
        the_user_info = check_user(username, passwd)
        if not the_user_info:
            return render_template("error.html", message="Incorrect username or password! Please try again")
        else:
            session["user_id"] = the_user_info[0][5]
            session["username"] = the_user_info[0][0]
            session["name"] = the_user_info[0][2] + " " + the_user_info[0][3]
            return render_template("success.html", message=f"Welcome back {the_user_info[0][2]} {the_user_info[0][3]} ({the_user_info[0][0]})")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    session.clear()

    if request.method == "GET":
        return render_template("signup.html")
    else:
        fname = request.form.get("fname")
        lname = request.form.get("lname")
        email = request.form.get("email")
        username = request.form.get("username")
        passwd = request.form.get("passwd")
        print(fname, lname, email, username, passwd)
        if add_user(fname, lname, email, username, passwd):
            return render_template("success.html", message=f"Thanks for signing up! Nice to meet you, {fname} {lname}. Enjoy your stay!")
        else:
            return render_template("error.html", message=f"Hello, {fname} {lname}. Unfortunately, we could not register you with the username \"{username}\" and/or email \"{email}\". Please try again or contact support")

@app.route("/logout")
def logout():
    session.clear()

    return render_template("success.html", message="See you next time")

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "GET":
        return render_template("settings.html")
    else:
        form = request.form.get("form")
        if form == "change_passwd":
            old_passwd = request.form.get("old_passwd")
            new_passwd = request.form.get("passwd")
            if change_passwd(session["user_id"], old_passwd, new_passwd):
                return render_template("success.html", message=f"Password Successfully Changed")
            else:
                return render_template("error.html", message=f"Cound Not Change Password... Please try again")
        elif form == "add_cash":
            the_amount = request.form.get("amount")
            add_cash(session["user_id"], the_amount)
            return render_template("success.html", message=f"Successfully added {usd(int(the_amount))} to your account")
        else:
            return render_template("error.html", message=f"Invalid Request")
    
if __name__ == "__main__":
    app.run(host='0.0.0.0')