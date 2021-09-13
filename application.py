# Website through which users can “buy” and “sell” stocks
import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show portfolio of stocks"""
    
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # ADD MONEY
        user_id = session["user_id"]
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
        more_money = int(request.form.get("more_money"))
        if more_money:
            db.execute("UPDATE users SET cash = ? WHERE id = ?", user_cash + more_money, user_id)
        
        return redirect("/")
    
    # User reached route via GET (as by clicking a link or via redirect)  
    else:
        user_id = session["user_id"]
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
        stocks = db.execute("SELECT name, price, symbol, SUM(shares) as totalShares FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
    
        total = user_cash
    
        for stock in stocks:
            total += stock["price"] * stock["totalShares"]
    
        # launch Index page
        return render_template("index.html", stocks=stocks, usd=usd, user_cash=user_cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        #Store user imput and stock attributes
        symbol = request.form.get("symbol").upper()
        user_id = session["user_id"]
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
        stocks = lookup(symbol)
        
        # Error checking
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("The Shares field only accepts integers")
        
        if shares <= 0:
            return apology("The Shares field only accepts positive integers")
        
        if not symbol:
            return apology("Empty Symbol field")
        
        elif not shares:
            return apology("Missing shares")
        
        elif not stocks:
            return apology("Invalid symbol")
        
        # Stock values
        stocks_name = stocks["name"]
        stocks_price = stocks["price"]
        total_price = stocks_price * shares
        
        if user_cash < total_price:
            return apology("The cash on hand is not enough")
            
        else:
            # Store the transaction in the DataBase
            db.execute("UPDATE users SET cash = ? WHERE id = ?", user_cash - total_price, user_id)
            db.execute("INSERT INTO transactions (user_id, name, shares, price, type, symbol) VALUES (?, ?, ?, ?, ?, ?) ", 
                       user_id, stocks_name, shares, stocks_price, "buy", symbol)
        
        # Bask to homepage
        return redirect("/")
        
    # User reached route via GET (as by clicking a link or via redirect)  
    else:
        # launch Buy page
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    
    user_id = session["user_id"]
    user_transactions = db.execute("SELECT price, symbol, shares, time FROM transactions WHERE user_id = ?", user_id)
    
    return render_template("history.html", user_transactions=user_transactions, usd=usd)


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
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        #Store user imput
        symbol = request.form.get("symbol").upper()
        
        # Error checking
        if not symbol:
            return apology("Empty Symbol field")
        
        # Getting the stock quote
        quoteV = lookup(symbol)
        if quoteV:
            return render_template("quoted.html", quoteV=quoteV, usd_function=usd)
        
        else:
            return apology("Invalid symbol")
    
    # User reached route via GET (as by clicking a link or via redirect)  
    else:
        # launch Quote page
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # Stores username, password and all usernames already registered in the database
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        
        # User name Error checking
        if not username:
            return apology("Empty USERNAME field")
        
        # Password Error checking
        elif not password:
            return apology("Empty password field.")
        
        elif not confirmation:
            return apology("Empty confirmation field.")
        
        if password != confirmation:
            return apology("Passwords do not match")
        
        # Save username and hash of password in database
        try:
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, generate_password_hash(password, method='pbkdf2:sha256', salt_length=8))
            
            # Redirect user to home page
            return redirect("/")
        except:
            return apology("USERNAME already exists")
    
    # User reached route via GET (as by clicking a link or via redirect)   
    else:
        # launch register page
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        user_id = session["user_id"]
        symbol = request.form.get("symbol").upper()
        stocks = lookup(symbol)
        
        # Error checking
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("The Shares field only accepts integers")
        
        if shares <= 0:
            return apology("The Shares field only accepts positive integers")
        
        if not symbol:
            return apology("Empty Symbol field")
        
        elif not shares:
            return apology("Missing shares")
            
        # Stock values
        stocks_name = stocks["name"]
        stocks_price = stocks["price"]
        total_price = stocks_price * shares
        
        shares_owned = db.execute("SELECT shares FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol", user_id, symbol)[0]["shares"]
        
        if shares_owned < shares:
            return apology("The number of shares selected exceeds the ones you own")
        
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
        
        #Updata your cash and Transactions
        db.execute("UPDATE users SET cash = ? WHERE id = ?", user_cash + total_price, user_id)
        db.execute("INSERT INTO transactions (user_id, name, shares, price, type, symbol) VALUES (?, ?, ?, ?, ?, ?) ", 
                       user_id, stocks_name, -shares, stocks_price, "sell", symbol)
        
        return redirect("/")
    
    # User reached route via GET (as by clicking a link or via redirect)  
    else:
        user_id = session["user_id"]
        symbols = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
        
        return render_template("sell.html", symbols=symbols)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
