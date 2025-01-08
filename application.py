import os



from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash


from helpers import apology, login_required, lookup, usd, stockinfo, record_tab_data, check_password_strength

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
    #Підтягуємо баланс користувача
    balance = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
    balance = balance[0]['cash']
    balance_form = usd(balance)
    stock_balance = 0
    total = 0

    username = session["username"]
    stocks = db.execute("SELECT * FROM :table_name", table_name=f"{username}_card")

    #Підтягуємо дані у таблицю

    for stock in stocks:
        info = lookup(stock['Symbol'])
        if not info:
            return apology("Try again later.", 400)

        stock['Price'] = info['price']
        stock['Total'] = stock['Price'] * stock['Shares']
        stock_balance += stock['Total']
        total = stock_balance + balance

    return render_template("index.html",stocks=stocks, balance=balance, balance_form=balance_form, stock_balance=stock_balance, total=total)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # Підтягуємо баланс користувача

    balance = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
    balance = balance[0]['cash']
    balance_form = usd(balance)
    price = 0
    totalprice = 0

    # Виводимо сторінку
    if request.method == "GET":
        return render_template("buy.html", price=price, totalprice=totalprice, balance=balance, balance_form=balance_form)
    symbol = None
    name = None
    shares = None

    # Дія
    if request.method == "POST":
        action = request.form.get("action")

        # Якщо натиснуто, TOTAL
        if action == "total":
            # Перевірка чи заповнені поля
            symbol = request.form.get("symbol")
            if not symbol:
                return apology("Please enter a symbol.", 400)
            shares = request.form.get("shares")
            if not shares.isdigit():
                return apology("You cannot purchase partial shares.")
            shares = int(shares)
            if not shares:
                return apology("Please enter the number of shares.", 400)
            if shares < 0:
                return apology("Please enter a positive number of shares.", 400)

            # Інфо, дії та розрахунки по акції (stockinfo у helpers.py)
            stock_info = stockinfo(request)
            if stock_info is None or len(stock_info) != 5:
                return apology("Could not retrieve stock information. Please try again.", 400)

            # Розпаковуємо значення з stock_info
            symbol, name, shares, price, totalprice = stock_info

            # Записуємо дані у сесію
            session.update({"symbol": symbol, "name": name, "shares": shares, "price": price})

            balance_form = usd(balance)

            return render_template("buy.html", balance_form=balance_form, balance=balance, symbol=symbol, name=name, price=price,
                                    shares=shares, totalprice=totalprice)

        # Якщо натиснуто, BUY
        elif action == "buy":
            if "symbol" in session:
                # Якщо дія BUY виконується після TOTAL і поля вже заповнені
                if session["symbol"] is not None:
                    # Перевірка чи не змінилась ціна
                    check = lookup(session["symbol"])
                    if check is None:
                        return apology("Could not retrieve stock information. Please try again.", 403)

                    if check['price'] != session["price"]:
                        return apology("Price has changed. Please try again.", 403)

                    # Перевірка чи вистачає грошей
                    totalprice = check['price'] * session["shares"]
                    if balance < totalprice:
                        return apology("Not enough money")

                    # Оновлення балансу
                    balance = balance - totalprice
                    symbol = session["symbol"]
                    name = session["name"]
                    price = session["price"]
                    shares = session["shares"]

                    # Якщо покупка успішна змінюємо cash в таблиці users
                    db.execute("UPDATE users SET cash=:balance WHERE id = :id", balance=balance, id=session["user_id"])
                    record_tab_data(symbol, name, shares, price, totalprice, balance)
                    balance_form = usd(balance)
                    session.pop("symbol", None)
                    flash('Bought')

                    return render_template("buy.html", balance_form=balance_form, balance=balance, symbol=symbol, name=name, price=price,
                                    shares=shares, totalprice=totalprice)

                return redirect("/")


            # Якщо одразу було виконано BUY не виконавши перед цим TOTAL
            elif "symbol" not in session:
                # Перевірка чи заповнені поля

                symbol = request.form.get("symbol")
                if not symbol:
                    return apology("Please enter a symbol.", 400)
                shares = request.form.get("shares")
                if not shares.isdigit():
                    return apology("You cannot purchase partial shares.")
                shares = int(shares)
                if not shares:
                    return apology("Please enter the number of shares.", 400)
                if shares < 0:
                    return apology("Please enter a positive number of shares.", 400)

                # Інфо, дії та розрахунки по акції (stockinfo у helpers.py)
                stock_info = stockinfo(request)
                if stock_info is None or len(stock_info) != 5:
                    return apology("Could not retrieve stock information. Please try again.", 400)

                # Розпаковуємо значення з stock_info
                symbol, name, shares, price, totalprice = stock_info

                if balance < totalprice:
                    return apology("Not enough money")

                balance = balance - totalprice


                # Якщо покупка успішна змінюємо cash в таблиці users
                db.execute("UPDATE users SET cash=:balance WHERE id = :id", balance=balance, id=session["user_id"])
                record_tab_data(symbol, name, shares, price, totalprice, balance)
                balance_form = usd(balance)
                totalprice = usd(totalprice)
                session.pop("symbol", None)

                flash(f"Bought {shares} of {symbol} for {price}, Updated cash: {usd(balance)}")

                return redirect("/")

    return apology("Invalid action.", 400)



@app.route("/check", methods=["GET"])
def check():
  """Return true if username available, else false, in JSON format"""
  # Зберігаємо ім'я користувача
  if request.method == "GET":
    username = request.args.get("username")

  # Перевіряємо чи поле не пусте
  if not username or len(username) < 1:
    return jsonify(False)

  # Підтягуємо імена користувачів з таблиці
  user_exists = db.execute("SELECT * FROM users WHERE username = :username", username=username)

  if not user_exists:
    return jsonify(True)  # Ім'я доступне
  return jsonify(False)  # Ім'я вже існує



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    #Отримуємо дані з таблиці history
    username = session["username"]
    stocks = db.execute(f"SELECT Action, Date, Shares, Symbol, Number, CAST(Price AS REAL) AS Price, CAST(Buyed AS REAL) AS Buyed, CAST(Selled AS REAL) AS Selled, CAST(Balance AS REAL) AS Balance FROM :table_name", table_name=f"{username}_history")

    return render_template("history.html", stocks=stocks)



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
        session["username"] = request.form.get("username")


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
    #Виводимо сторінку
    if request.method == "GET":
        return render_template("quote.html")

    if not request.form.get("symbol"):
        return apology("incorrect symbol", 400)
    symbol = request.form.get("symbol")

    #Отримуємо дані по вказаній акції
    info = lookup(request.form.get("symbol"))
    if not info:
        return apology("No info", 400)

    #Якщо користувач не вказав символ

    return render_template("quoted.html",symbol=symbol, info=info)



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # Forget any user_id
    session.clear()

    if request.method == "POST":

        # Перевірка чи заповнені поля
        if not request.form.get("username"):
            return apology("must provide username", 400)
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        elif not request.form.get("confirmation"):
            return apology("must confirm your password", 400)

        # Перевірка складності пароля
        elif not check_password_strength(request.form.get("password")):
            return apology("Password strength requirements not met.", 400)
        #Перевірка чи збігаються паролі
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("the entered passwords do not match. Try again!", 400)

        #Зберегти дані користувача у змінні
        username = request.form.get("username")
        hash = generate_password_hash(request.form.get("password"))

        #Перевірити чи ім'я користувача унікальне
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username = username)
        if len(rows) != 0:
            return apology("The username is olready exists. Try another pleace.", 400)

        #Додати нові дані до таблиці
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                   username = username, hash = hash)

        #Створити нову таблицю картка з ім'ям користувача та історія
        db.execute("CREATE TABLE IF NOT EXISTS :table_name (Action VARCHAR(50), Date DATETIME(20), Shares VARCHAR(50), Symbol VARCHAR(50), Number INTEGER, Price REAL, Buyed REAL, Selled REAL, Balance REAL)", table_name=f"{username}_history")
        db.execute("CREATE TABLE IF NOT EXISTS :table_name (Name VARCHAR(50), Symbol VARCHAR(50), Shares INTEGER, Price REAL, Total REAL)", table_name=f"{username}_card")

        return redirect("/")

    return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    #Підтягуємо баланс користувача
    balance = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
    balance = balance[0]['cash']
    balance_form = usd(balance)

    #Підтягуємо до спадного списку акції які є у власності користувача
    username = session["username"]
    stocks = db.execute("SELECT Symbol FROM :table_name", table_name=f"{username}_card")
    if request.method == "GET":
        return render_template("sell.html",stocks=stocks, balance=balance, balance_form=balance_form)

    if request.method == "POST":
        action = request.form.get("action")
    #Якщо натиснуто TOTAL
    if action == "total":
        #Перевірка чи заповнені поля
        if not request.form.get("symbol"):
            return apology("Please enter a symbol.", 400)
        if not request.form.get("shares"):
            return apology("Please enter the number of shares.", 400)

        #Інфо дії та розрахунки по акції (stockinfo у helpers.py)
        try:
            symbol, name, shares, price, totalprice = stockinfo(request)

        except(KeyError, TypeError, ValueError):
            return apology("Please enter a correct symbol.", 400)

        #Записуємо дані у сесію
        session.update({"symbol": symbol, "name": name, "shares": shares, "price": price})

        balance_form = usd(balance)

        return render_template("sell.html",balance_form=balance_form, balance=balance, symbol=symbol, name=name, price=price,
                                    shares=shares, totalprice=totalprice)
    #Якщо дія Sell
    elif action == "sell":
        if "symbol" in session:
            #Якщо дія BUY виконується після успішної дії TOTAL
            if session["symbol"] is not None:
                symbol = session["symbol"]
                name = session["name"]
                price = session["price"]
                shares = session["shares"]
                totalprice = price * shares
                balance = balance + totalprice

                #Якщо продаж успішний змінюємо cash в таблиці users
                db.execute("UPDATE users SET cash=:balance WHERE id = :id", balance=balance, id=session["user_id"])

        #Якщо одразу виконано sell
        elif "symbol" not in session:
            #Перевірка чи заповнені поля
            if not request.form.get("symbol"):
                return apology("Please enter a symbol.", 400)
            if not request.form.get("shares"):
                return apology("Please enter the number of shares.", 400)

            #Інфо дії та розрахунки по акції (stockinfo у helpers.py)
            try:
                symbol, name, shares, price, totalprice = stockinfo(request)

            except(KeyError, TypeError, ValueError):
                return apology("Please enter a correct symbol.", 400)

            balance = balance + totalprice

            #Якщо продаж успішний змінюємо cash в таблиці users
            db.execute("UPDATE users SET cash=:balance WHERE id = :id", balance=balance, id=session["user_id"])

    #Записуємо дані в історію і гаманець
    record_tab_data(symbol, name, shares, price, totalprice, balance)
    balance_form = usd(balance)

    session.pop("symbol", None)

    flash('Good deal!!!')

    return redirect("/")






def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)



# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)








