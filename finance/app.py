import os

from cs50 import SQL
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    #Ensure responses aren't cached
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    #Show portfolio of stocks
    user_id = session["user_id"]
    payments = db.execute("SELECT DISTINCT Symbol AS Symbol,Name AS Name FROM payments WHERE user_id = ?", user_id)
    # Need to select Shares and Total seperately
    values = []
    for i in range(len(payments)):
        ival = []
        PaymentsSym = payments[i]["Symbol"]
        stock = lookup(PaymentsSym)
        Price = stock["price"]
        Symbol = stock["symbol"]
        Name = stock["name"]
        Shares = db.execute("SELECT SUM(Shares) FROM payments WHERE user_id = ? AND Symbol = ? ", user_id, payments[i]["Symbol"])
        Shares = Shares[0]["SUM(Shares)"]
        Total = db.execute("SELECT SUM(Total) FROM payments WHERE user_id = ? AND Symbol = ? ", user_id, payments[i]["Symbol"])
        Total = Total[0]["SUM(Total)"]
        if Shares == 0:
            Total = 0
        ival.append(Symbol)
        ival.append(Name)
        ival.append(Shares)
        ival.append(Price)
        ival.append(Total)
        values.append(ival)
    cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    Cash = cash[0]["cash"]
    total = db.execute("SELECT SUM(Total) FROM payments WHERE user_id = ? AND Shares > 0", user_id)
    ntotal = db.execute("SELECT SUM(Total) FROM payments WHERE user_id = ? AND Shares < 0", user_id)
    total = (total[0]["SUM(Total)"])
    ntotal = (ntotal[0]["SUM(Total)"])
    if ntotal == None:
        ntotal = 0
    if total == None:
        total = "$10000.00"
    else:
        total = total-ntotal
        total = total + Cash
    #     total = "$"+str(round(total,2))
    # Cash = "$"+str(round(Cash,2))
    empty = False
    length = 0
    if len(values) == 0:
        empty = True
    else:
        empty = False
        length = len(values)
    return render_template("index.html", payments=payments, Cash=Cash, total=total, values=values, empty=empty, length=length)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    #Buy shares of stock
    if request.method == "POST":

        # Gets symbol and ckecks with requirements
        symbol = request.form.get("symbol")
        if symbol == "" or lookup(symbol) == None:
            return apology("Either the stock feild is empty or does not match anything.")

        # Gets shares amount
        try:
            shares = float(request.form.get("shares"))  # TO DO
        except:
            return apology("not correct format.")
        if shares < 1 or (shares).is_integer() == False:
            return apology("Shares is not positive or integer.")

        # value for Stock
        stock = lookup(symbol)
        curprice = stock["price"]
        name = stock["name"]
        total = curprice * shares

        # Lookups amount of cash of the users
        user_id = session["user_id"]
        cashdb = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        cash = cashdb[0]["cash"]
        left = cash-total

        if cash < total:
            return apology("Not enough money.")

        # Inserting values into buy/sell table
        now = datetime.now()
        date_str = now.strftime("%d/%m/%Y %H:%M:%S")
        db.execute("INSERT INTO payments(user_id,Symbol,Name,Shares,Price,Total,Date,BuySell) VALUES(?,?,?,?,?,?,?,?)",
                   user_id, symbol, name, shares, curprice, total, date_str, 'Buy')
        db.execute("UPDATE users SET cash = ? WHERE id = ?", left, user_id)
        return redirect("/")
    elif request.method == "GET":
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    #Show history of transactions
    user_id = session["user_id"]
    history = db.execute("SELECT Symbol, Shares, Price, Date FROM payments WHERE user_id = ?", user_id)
    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    #Log user in

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    #Log user out

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    #Get stock quote.
    if request.method == "GET":
        return render_template("quote.html")
    elif request.method == "POST":
        symbol = request.form.get("symbol")
        value = lookup(symbol)
        if value == None or symbol == "":
            return apology("Incorrect stock symbol.")
        name = value["name"]
        cost = usd(value["price"])
        return render_template("quoted.html", name=name, cost=cost)


@app.route("/register", methods=["GET", "POST"])
def register():
    #Register user
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if username == "":
            return apology("No username was given")
        if password == "" or confirmation == "" or password != confirmation:
            return apology("No password entered in one or both fields or password is not the same in both fields")
        passhash = generate_password_hash(password)
        try:
            db.execute("INSERT INTO users(username,hash) VALUES(?,?)", username, passhash)
        except:
            return apology("Username already exists.")
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        session["user_id"] = rows[0]["id"]
        return render_template("index.html")
    elif request.method == "GET":
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    #Sell shares of stock
    if request.method == "POST":
        user_id = session["user_id"]
        symbol = request.form.get("symbol")  # implement a select menu
        try:
            shares = float(request.form.get("shares"))  # TO DO
        except:
            return apology("not correct format.")
        if shares < 1 or (shares).is_integer() == False:
            return apology("Shares is not positive or integer.")
        if symbol == None:
            return apology("Enter a stock symbol.")
        Shares2 = db.execute("SELECT SUM(Shares) FROM payments WHERE user_id = ? AND Symbol = ? ", user_id, symbol)
        Shares2 = int(Shares2[0]["SUM(Shares)"])
        shares = int(shares)
        if shares > Shares2:
            return apology("Too many stocks.")
        stock = lookup(symbol)
        name = stock["name"]
        curprice = stock["price"]
        total = curprice * shares
        cashdb = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        cash = cashdb[0]["cash"]
        add = cash + total
        shares = int("-"+str(shares))
        now = datetime.now()
        date_str = now.strftime("%d/%m/%Y %H:%M:%S")
        db.execute("INSERT INTO payments(user_id,Symbol,Name,Shares,Price,Total,Date,BuySell) VALUES(?,?,?,?,?,?,?,?)",
                   user_id, symbol, name, shares, curprice, total, date_str, 'Sell')
        db.execute("UPDATE users SET cash = ? WHERE id = ?", add, user_id)
        return redirect("/")
    elif request.method == "GET":
        user_id = session["user_id"]
        boughts = db.execute("SELECT DISTINCT Symbol FROM payments WHERE user_id = ?", user_id)
        bought = []
        for i in range(len(boughts)):
            bought.append(boughts[i]["Symbol"])
        return render_template("sell.html", bought=bought)
