import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, Response, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
# debug mode: make a change to some file but your browser not notice
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
# usd, a function (defined in helpers.py) that will make it easier to format values as US dollars (USD)
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem" # store sessions on the local filesystem
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    rows = db.execute("SELECT * FROM portfolio WHERE id = :id ", id=session["user_id"])
    # print(rows)# [{'symbol': 'FB', 'share': 7, 'id': 8},}]

    # get user's current cash
    cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])[0]["cash"]

    # empty portfolio: pass nothign to stock
    if len(rows) == 0:
        return render_template("index.html", CASH=usd(cash), total=usd(cash))

    asset = []
    cash_price = cash

    for portfolio in rows:
        print("symbol lookup: ", lookup(portfolio["symbol"]))
        current_price = lookup(portfolio["symbol"])["price"]
        total_price = current_price * portfolio["share"]
        cash_price += total_price
        asset.append({"Symbol": portfolio["symbol"], "Name": portfolio["symbol"], "Shares": portfolio["share"],
        "Price": current_price, "Total": total_price})


    return render_template("index.html", stocks=asset, CASH=usd(cash), total=usd(cash_price))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "POST":

        # ensure stock symbol & share was submitted
        if not request.form.get("symbol"):
            return apology("Missing valid symbol")
        elif not request.form.get("share"):
            return apology("Missing Share")

        # check if share is integer and greater than 0
        elif not request.form.get("share").isnumeric():
            return apology("invalid share")
        elif int(request.form.get("share")) <= 0:
            return apology("Not a positive integer")

        symbol = request.form.get("symbol").upper()
        print("symbol: ", symbol)
        quote = lookup(symbol)
        print("quote: ", quote)

        if quote == None:
            return apology("Invalid Symbol")
        # print("quote: ", quote)
        # check how much cash the user currently has in users
        cash = db.execute("SELECT cash \
                          FROM users \
                          WHERE id = :id", id=session["user_id"] )
        # print(cash) #[{'cash': 10000}]

        price = int(quote["price"])
        shares = int(request.form.get("share"))
        updated_cash = cash[0]["cash"] - shares * price
        if updated_cash < 0:
            return apology("Balance can't afford")

        # everything ok  -> 1: update user cash 2: buy stock
        db.execute("UPDATE users SET cash = :updated_cash \
                    WHERE id = :id", updated_cash=updated_cash, id=session["user_id"])

        # portfolio: keep track of the purchase
        rows = db.execute("SELECT * FROM portfolio \
                    WHERE id = :id AND symbol = :symbol", id=session["user_id"], symbol=symbol)

        # if no share then INSERT a new row in portfolio
        if len(rows) == 0:
            db.execute("INSERT INTO portfolio (id, symbol, share)\
                    VALUES (:id, :symbol, :shares)", id=session["user_id"], symbol=symbol, shares=shares)
        else:
            db.execute("UPDATE portfolio SET share = share + :shares", shares=shares)

        # update the history table
        db.execute("INSERT INTO history (id, symbol, share, price)\
                    VALUES (:id, :symbol, :share, :price)", id=session["user_id"], symbol=symbol, share=shares, price=usd(price))

        flash("Bought!") # show alert
        return redirect(url_for("index"))

    else:

        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    rows = db.execute("SELECT * FROM history \
                        WHERE id = :id", id=session["user_id"])
    # print(rows)

    return render_template("history.html", history=rows)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        # ensure stock symbol was submitted
        if not request.form.get("symbol"):
            return apology("Missing Symbol")

        # lookup: get quote from Yahoo Finance OR Alpha Vantage
        symbol = request.form.get("symbol").upper()
        print("symbol:", symbol)
        quote = lookup(symbol)
        print(quote)

        # ensure symbol is valid
        if quote == None:
            return apology("Invalid Symbol")

        return render_template("quoted.html", name=quote["name"], symbol=quote["symbol"], price=quote["price"])

    # user reached via GET
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")
        elif not request.form.get("password_confirmation"):
            return apology("must provide password confirmation")
        elif request.form.get("password") != request.form.get("password_confirmation"):
            return apology("Your passwords don't match!!!")

        # pwd_context.hash: hash password
        # add user to database
        # rows: returned id
        rows = db.execute("INSERT INTO users (username, hash) \
                            VALUES(:username, :hash)", username=request.form.get("username"),\
                            hash=pwd_context.hash(request.form.get("password")))
        if not rows:
            return apology("Username already exists")


        # remember which user has logged in
        session["user_id"] = rows

        return redirect(url_for("index"))

    else:
        return render_template("register.html")

@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    """Change user password for user already logged in."""

    if request.method == "POST":

        # invalid case
        if not request.form.get("old_password"):
            return apology("Must enter old password")
        if not request.form.get("new_password"):
            return apology("Must enter new password")
        if not request.form.get("confirmation"):
            return apology("Must confirm new password")
        if request.form.get("confirmation") != request.form.get("new_password"):
            return apology("Password must match!")

        hashes = db.execute("SELECT hash FROM users WHERE id = :id", id=session["user_id"])
        if not pwd_context.verify(request.form.get("old_password"), hashes[0]["hash"]):
            print("old hash from db:", hashes[0]["hash"])
            print("old hash from input:", pwd_context.hash(request.form.get("old_password")))
            return apology("Old password is wrong!")

        # update password
        db.execute("UPDATE users \
                    SET hash = :hash WHERE id = :id", hash=pwd_context.hash(request.form.get("new_password")), \
                    id=session["user_id"])

        flash("Change password successfully!")
        return redirect(url_for("index"))

    else:
        return render_template("password.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method == "POST":

        # ensure stock symbol & share was submitted
        if not request.form.get("symbol"):
            return apology("Missing valid symbol")
        elif lookup(request.form.get("symbol").upper()) == None:
            return apology("Invalid symbol")
        elif not request.form.get("share"):
            return apology("Missing Share")

        # check if share is integer and greater than 0
        elif not request.form.get("share").isnumeric():
            return apology("invalid share")
        elif int(request.form.get("share")) <= 0:
            return apology("Not a positive integer")

        symbol = request.form.get("symbol").upper()
        quote = lookup(symbol)
        shares = int(request.form.get("share"))

        # check if user has the share
        shares_already_list = db.execute("SELECT share \
                          FROM portfolio \
                          WHERE id = :id \
                          AND symbol = :symbol", id=session["user_id"], symbol=symbol )
        # print("share already:", shares_already)
        if len(shares_already_list) == 0:
            return apology("symbol not owned.")

        shares_already = shares_already_list[0]["share"]
        updated_share = shares_already - shares


        if updated_share < 0:
            return apology("too many shares")

        # everything ok  -> 1: update user cash from user table 2: sell stock
        cash = db.execute("SELECT cash \
                          FROM users \
                          WHERE id = :id", id=session["user_id"] )

        price = int(quote["price"])
        shares = int(request.form.get("share"))
        updated_cash = cash[0]["cash"] + shares * price

        db.execute("UPDATE users SET cash = :updated_cash \
                    WHERE id = :id", updated_cash=updated_cash, id=session["user_id"])

        # update portfolio table
        # if updated share == 0, remove row, else update
        if updated_share == 0:
            db.execute("DELETE FROM portfolio \
                        WHERE id = :id AND symbol = :symbol", id=session["user_id"], symbol=symbol)
        else:
            db.execute("UPDATE portfolio SET \
                        share = :updated_share \
                        WHERE id = :id AND symbol = :symbol", updated_share=updated_share, id=session["user_id"], symbol=symbol)

        # update history table
        db.execute("INSERT INTO history (id, symbol, share, price)\
                    VALUES (:id, :symbol, :share, :price)", id=session["user_id"], symbol=symbol, share=-(shares), price=usd(price))

        flash("Sold!")
        return redirect(url_for("index"))
    else:
        # if user reaches via GET
        # retrieve current symbol in portfolio
        rows = db.execute("SELECT symbol FROM portfolio WHERE id = :id", id=session["user_id"])

        return render_template("sell.html", stock_symbol=rows)
