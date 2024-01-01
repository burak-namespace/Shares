import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
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


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    username = db.execute("SELECT username,cash FROM users WHERE id = :id",id = session["user_id"])
    rows = db.execute("SELECT * FROM :username",username=username[0]["username"])

    """ API """
    fortune = 0
    for i in range(len(rows)):
        new_price = lookup(rows[i]['symbol'])
        total = new_price['price'] * float(rows[i]["shares"])
        rows[i].update({"price" : usd(new_price['price'])})
        rows[i].update({"total" : usd(total)})
        fortune += total
    fortune+= username[0]['cash']

    return render_template("index.html",rows=rows,cash=usd(username[0]['cash']),fortune=usd(fortune))



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares_name = lookup(symbol)

        # Undefined symbol
        if not shares_name:
            return apology("Sorry,undefined symbol",403)

        # Share count might be bigger than 0
        shares = float(request.form.get("shares"))
        if shares < 1:
            return apology("You must shares select big than 0",403)

        # Users tablosundan etkin olan kullanıcı seçilir.
        user = db.execute("SELECT * FROM users WHERE id = :id", id = session['user_id'])
        # Etkin kullanıcının portfolyosu seçilir. (Kendi tablosundan)
        rows = db.execute("SELECT * FROM :user ",user=user[0]['username'])

        # !!!
        #Kullanıcının bu hisseden varsa o hisse satırını seçer.
        user_shares = db.execute("SELECT * FROM :user WHERE symbol=:symbol",user=user[0]['username'],symbol=symbol)

        #Kullanıcının Cash'i , alacağı hisse fiyatını karşılıyormu ?
        if user[0]['cash'] < (shares * shares_name['price']):
            return apology("Sorry,Your cash is not enough",403)

        # Kullanıcıda bu hisseden hiç yok, ekleme yapılır.
        if len(user_shares) < 1:
            add = db.execute("INSERT INTO :user (symbol,name,shares) VALUES(:symbol,:name,:shares)",user=user[0]['username'],symbol = symbol,name=shares_name['name'],shares = shares)
            update_2 = db.execute("UPDATE users SET cash=:cash WHERE id=:id",cash = user[0]['cash'] - (shares_name['price'] * shares),id = user[0]['id'])

            #History Tablosuna alınan hisse kaydedilir.
            history = db.execute("INSERT INTO history (id,symbol,name,price,shares,date) values(:id,:symbol,:name,:price,:shares,datetime('now'))",id = session['user_id'],symbol = symbol,name = shares_name['name'],price = shares_name['price'],shares = shares)
            return redirect("/")

        #Kullanıcıda bu hisseden var.
        else:
            old_shares = int(user_shares[0]["shares"])
            update = db.execute("UPDATE :user SET shares=:new_shares WHERE symbol=:symbol",user=user[0]['username'],new_shares= old_shares + shares,symbol=symbol)
            update_2 = db.execute("UPDATE users SET cash=:cash WHERE id=:id",cash=user[0]['cash'] - (shares_name['price'] * shares),id=user[0]['id'])

            #History Tablosuna alınan hisse kaydedilir.
            history = db.execute("INSERT INTO history (id,symbol,name,price,shares,date) values(:id,:symbol,:name,:price,:shares,datetime('now'))",id=session['user_id'],symbol=symbol,name=shares_name['name'],price=shares_name['price'],shares=shares)

            return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    return jsonify("TODO")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    history = db.execute("SELECT * FROM history WHERE id=:id",id=session['user_id'])
    for i in range(len(history)):
        history[i]['price'] = usd(history[i]['price'])

    return render_template("history.html",history=history)



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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

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
    if request.method == "POST":
        symbol = lookup(request.form.get("quote"))
        if not symbol:
            return apology("Sorry , it is undefined",403)
        return render_template("quoted.html",price = symbol['price'], name = symbol['name'],symbols = symbol['symbol'])

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        if not request.form.get("username"):
            return apology("You must provide your username",403)

        elif not request.form.get("password"):
            return apology("You must provide your password",403)

        elif not request.form.get("password") == request.form.get("password-r"):
            return apology("Please check password, they are not same")

        rows = db.execute("SELECT * FROM users WHERE username= :username",username = request.form.get("username"))

        if len(rows) == 1:
            return apology("Username is not available",403)

        rows_ = db.execute("CREATE TABLE :portfolio (shares_id int PRIMARY KEY,symbol varchar(100) NOT NULL,name varchar(100) NOT NULL,shares int NOT NULL)",portfolio = request.form.get("username"))
        if not rows_:
            return apology("Sorry !",403)

        check_register = db.execute("INSERT INTO users (username,hash) VALUES(:username,:hash)",username=request.form.get("username"),hash=generate_password_hash(request.form.get("password")))
        session["user_id"]=check_register


        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":

        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("Symbol and shares cannot be empty",403)

        #Kullanıcının satacağı hisse
        symbol = request.form.get("symbol")
        #Kullanıcının satmak istediği hisse sayısı
        shares_ = int(request.form.get("shares"))

        username_cash = db.execute("SELECT * FROM users WHERE id=:id",id=session['user_id'])
        portfolio = db.execute("SELECT shares FROM :user WHERE symbol=:symbole",user=username_cash[0]['username'],symbole=symbol)

        if shares_ > portfolio[0]['shares']:
            return apology("Too many shares",403)

        #Güncel Fiyat
        api = lookup(symbol)
        if not api:
            apology(f"You have not any {shares_}",403)

        #Hissenin güncel fiyatla ve miktarıyla kullanıcının cash'ine aktarılır.
        selled = db.execute("UPDATE users SET cash=:cash WHERE id=:id ",cash=(username_cash[0]['cash']+(api['price']*shares_)),id=session['user_id'])


        #Hissenin kullanıcı portfolyosundan çıkarılması
        if portfolio[0]['shares'] - shares_ != 0:
            delet = db.execute("UPDATE :user SET shares=:sharese WHERE symbol=:symbole",user=username_cash[0]['username'],sharese=(portfolio[0]['shares']-shares_),symbole=symbol)
        else:
            delet = db.execute("DELETE FROM :user WHERE symbol=:symbole",user=username_cash[0]['username'],symbole=symbol)



        #History Tablosuna yapılan işlem kaydedilir.
        his = db.execute("INSERT INTO history (id,symbol,name,price,shares,date) VALUES(:id,:symbole,:name,:price,:sharese,datetime('now'))",id=session['user_id'],symbole=symbol,name=api['name'],price=api['price'],sharese=(-1 * shares_))

        #Anasayfaya dönülür.
        return redirect("/")

    else:
        username = db.execute("SELECT username FROM users WHERE id=:id",id=session['user_id'])
        rows = db.execute("SELECT symbol FROM :user",user=username[0]["username"])
        return render_template("sell.html",symbols=rows)



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
