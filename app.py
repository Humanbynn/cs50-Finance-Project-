import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # For user logged in, retrieve the shares he bought(if any) and his cash balance.Format balance with "usd" function. Sum up shares for the same symbol.
    id= session["user_id"]
    username=db.execute("SELECT username FROM users WHERE id=?",id)
    username=username[0]["username"]
    rows=db.execute("SELECT symbol,SUM(shares) AS shares FROM transactions WHERE user_id=? GROUP BY symbol", id)
    user_cash=db.execute("SELECT cash FROM users WHERE id=?",id)
    balance=user_cash[0]["cash"]
    cash=usd(balance)

    # Create a list and append the stocks owned,No of shares, current price of stock, and value of stocks owned.First check if user has any stocks.
    holdings=[]

    if not rows:
        grand_total=cash

    else:
        for row in rows:
            stock=lookup(row["symbol"])
            price=stock["price"]
            value=stock["price"] * row["shares"]
            holdings.append({
                "symbol": row["symbol"],
                "shares": row["shares"],
                "price": usd(price),
                "value": usd(value)
            })



    # Calculate the equity of user
        grand_total=0
        grand_total +=value
        grand_total +=balance
        grand_total=usd(grand_total)

    return render_template("index.html",cash=cash,holdings=holdings,grand_total=grand_total,username=username)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method=="GET":
         return render_template("buy.html")

    else:
        # check that user entered a valid no of shares
        shares=(request.form.get("shares"))
        if not shares:
            return apology("Please specify the number of shares you want to buy.",403)
        try:
            int_shares = int(shares)  # Convert to integer
        except ValueError:
            return apology("Please enter a valid integer for the number of shares.", 403)
        if int_shares<=0:
            return apology("Invalid number of shares. Please enter a positive integer.",403)

        # Verify that symbol is valid using lookup
        symbol = request.form.get("symbol").upper()
        result = lookup(symbol)
        if result is None:
            return apology("invalid symbol")


        # Calculate the cost of shares to be purchased
        price=result["price"]
        cost= int_shares * price

        # Extract user id and Retrieve user's balance from database
        user_id= session["user_id"]
        rows=db.execute("SELECT cash FROM users WHERE id=?",user_id)
        user_balance=rows[0]["cash"]

        # Check if user has enough to cover purchase
        if cost > user_balance:
            return apology("Insufficient funds. Deposit and try again.", 403)

        # Update users cash balance if purchase was successful
        db.execute("UPDATE users SET cash= cash - ? WHERE id=?", cost,user_id)

        # Insert a new row into transactions table to track purchase history
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, timestamp) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)", user_id, symbol, int_shares, price)
        return render_template("success.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # retrieve user history from database
    id=session["user_id"]
    transactions=db.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY timestamp DESC",id)
    holdings=[]
    type= None

    # Check the type of transaction


    # For every transaction,append the history
    for transaction in transactions:
        if transaction["shares"] >0:
            type="Purchase"
        else:
            type="Sale"
        holdings.append({
            "symbol":transaction["symbol"],
            "price":transaction["price"],
            "shares":abs(transaction["shares"]),
            "type":type,
            "timestamp":transaction["timestamp"]
    })

    return render_template("history.html",holdings=holdings)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

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
            return apology("incorrect username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method=="GET":
        return render_template("quote.html")

    else:
        symbol=request.form.get("symbol")
        price = lookup(symbol)
        return render_template("quoted.html", symbol=symbol,price=price)



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        Username=request.form.get("username")
        Password=request.form.get("password")

        # Return apology if no input for username or password
        if not Username or not Password:
            return apology("must provide username and password", 403)

         #check if password and confirmation matches
        if Password !=request.form.get("confirmation"):
            return apology("Password do not match",403)

        USERNAMES= db.execute("SELECT username FROM users")
        try:
        # Attempt to create the user in the database
            db.execute("INSERT INTO users(username,hash) VALUES(?,?)",Username,generate_password_hash(Password))
            return redirect("/login")

        except:
        # Check if the error is due to a unique constraint violation
            if Username in USERNAMES:
                return apology("Username already exists",403)
        return apology("Username already exists",403)


    else:
         return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # Retrieve Stock and No of shares information for user signed in
    id= session["user_id"]
    rows=db.execute("SELECT symbol,SUM(shares) AS shares FROM transactions WHERE user_id=? GROUP BY symbol", id)
    holdings=[ ]
    for row in rows:
        holdings.append({
            "symbol": row["symbol"],
            "shares": row["shares"],
        })

        if request.method=="POST":
            # Ensure that user selects a stock symbol
            symbol=request.form.get("symbol")
            if not symbol or not holdings[0]["symbol"]:
                return apology("Select valid Stock symbol", 404)

            # Ensure that "shares" is not blank and is valid
            shares=request.form.get("shares")
            try:
                int_shares = int(shares)  # Convert to integer
            except ValueError:
                return apology("Please enter a valid integer for the number of shares.", 403)
            if int_shares <=0 :
                return apology("Number ofShares must be a positive integer", 404)


            # Check if user has up to the shares they entered
            for holding in holdings:
                if int(shares)>holdings[0]["shares"]:
                    return apology("You don't have enough shares for this sale", 404)

            price=lookup(symbol)["price"]
            sales=price * int_shares
            db.execute("UPDATE users SET cash=cash + ? WHERE id=?", sales,id)
            db.execute("INSERT INTO transactions(user_id, symbol, shares, price, timestamp) VALUES(?, ?, ?, ?, CURRENT_TIMESTAMP)",id, symbol,-int_shares,price)
            return render_template("success.html")

    else:
        return render_template("sell.html", holdings=holdings)


@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    """Allows user to change password"""
    if request.method == "POST":
        Current_password=request.form.get("password")
        New_password=request.form.get("n_password")


        # Return apology if no password entered
        if not Current_password:
            return apology("Enter Current Password", 403)
        elif not New_password:
            return apology("Enter New Password", 403)

         #check if New password and confirmation matches
        if New_password !=request.form.get("confirmation"):
            return apology("Password do not match",403)

        # Check if password hash matches for user in the database
        id= session["user_id"]
        password_check=db.execute("SELECT hash FROM users WHERE id=?",id)
        password_check=password_check[0]["hash"]

        if not check_password_hash(password_check,Current_password):
            return apology("Current password is incorrect.", 403)

        db.execute("UPDATE users SET hash=? WHERE id=?",generate_password_hash(New_password),id)

        return redirect("/login")


    return render_template("password.html")
