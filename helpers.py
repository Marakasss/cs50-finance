import requests
import datetime
import csv
import pytz
import urllib
import uuid

from cs50 import SQL
from flask import flash, redirect, render_template, request, session
from functools import wraps
# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")



def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code



def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup_company(keywords):
    """Look up company symbol and name by keywords."""

    # Вставте ваш ключ API замість 'YOUR_API_KEY'
    api_key = '575FWQMSLVWYTDJ8'

    # Контактування API
    try:
        url = f"https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={keywords}&apikey={api_key}"
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Розбір відповіді
    try:
        data = response.json()
        best_matches = data.get("bestMatches", [])
        if best_matches:
            # Вибираємо перший результат як найбільш відповідний
            return best_matches[0].get("2. name", "1. symbol")

    except (KeyError, TypeError, ValueError, IndexError):
        return None




def lookup(symbol):
    """Look up quote for symbol."""

    # Prepare API request
    symbol = symbol.upper()
    end = datetime.datetime.now(pytz.timezone("US/Eastern"))
    start = end - datetime.timedelta(days=7)

    # Yahoo Finance API
    url = (
        f"https://query1.finance.yahoo.com/v7/finance/download/{urllib.parse.quote_plus(symbol)}"
        f"?period1={int(start.timestamp())}"
        f"&period2={int(end.timestamp())}"
        f"&interval=1d&events=history&includeAdjustedClose=true"
    )

    # Query API
    try:
        response = requests.get(
            url,
            cookies={"session": str(uuid.uuid4())},
            headers={"Accept": "*/*", "User-Agent": request.headers.get("User-Agent")},
        )
        response.raise_for_status()

        # CSV header: Date,Open,High,Low,Close,Adj Close,Volume
        quotes = list(csv.DictReader(response.content.decode("utf-8").splitlines()))
        price = round(float(quotes[-1]["Adj Close"]), 2)
        name = lookup_company(symbol)
        return {"price": price, "symbol": symbol, "name": name}
    except (KeyError, IndexError, requests.RequestException, ValueError):
        return None



def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"







def stockinfo(request):
    try:
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")


        # Зберігаємо дані про акцію та рахуємо
        info = lookup(symbol)
        if not info:
            return apology("Please enter a symbol.", 400)
        name = info['name']
        price = info['price']
        symbol = info['symbol']
        shares = int(shares)
        totalprice = shares * price

        return symbol, name, shares, price, totalprice
    except(KeyError, TypeError, ValueError):
        return apology("Please enter a correct symbol.", 400)



#Функція запису та оновлення даних у таблицях користувача
def record_tab_data(symbol, name, shares, price, totalprice, balance):
    username = session["username"]
    action = request.form.get("action")

    #Якщо виконано успішну покупку
    if action == "buy":

        # Перевірка чи символ вже присутній у таблиці
        existing_stock = db.execute("SELECT * FROM :table_name WHERE Symbol = :symbol", table_name=f"{username}_card", symbol=symbol)

        if existing_stock:
        #Якщо запис існує, оновіть значення number
            updated_number = existing_stock[0]['Shares'] + shares

            db.execute("UPDATE :table_name SET Shares = :updated_number WHERE Symbol = :symbol",
                            table_name=f"{username}_card", updated_number=updated_number, symbol=symbol)
        else:
            #Записуємо дані про покупку до таблиці картка клієнта для Portfolio
            db.execute("INSERT INTO :table_name (Name, Symbol, Shares) VALUES (:name, :symbol, :shares)",
                            table_name=f"{username}_card", name=name, symbol=symbol, shares=shares)


        #history

        current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute("INSERT INTO :table_name (Action, Date, Shares, Symbol, Number, Price, Buyed, Selled, Balance) VALUES ('Buyed', :date, :name, :symbol, :shares, :price, :totalprice, ' ', :balance)",
                            table_name = f"{username}_history", date=current_date, name=name, symbol=symbol, shares=shares, price=price, totalprice=totalprice, balance=balance)

    #Якщо виконано успішний продаж
    elif action == "sell":
        # Перевірка чи символ вже присутній у таблиці
        existing_stock = db.execute("SELECT * FROM :table_name WHERE Symbol = :symbol", table_name=f"{username}_card", symbol=symbol)

        if existing_stock:
            #Якщо запис існує, оновіть значення number
            updated_number = existing_stock[0]['Shares'] - shares
            if updated_number < 0:
                return apology("There are not enough shares", 403)

            # Перевірка, чи всі акції були продані, і видалення рядка, якщо так
            if updated_number == 0:
                db.execute("DELETE FROM :table_name WHERE Symbol = :symbol", table_name=f"{username}_card", symbol=symbol)

            db.execute("UPDATE :table_name SET Shares = :updated_number WHERE Symbol = :symbol",
                                table_name=f"{username}_card", updated_number=updated_number, symbol=symbol)

        current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute("INSERT INTO :table_name (Action, Date, Shares, Symbol, Number, Price, Buyed, Selled, Balance) VALUES ('Selled', :date, :name, :symbol, :shares, :price, ' ', :totalprice, :balance)",
                                table_name = f"{username}_history", date=current_date, name=name, symbol=symbol, shares=shares, price=price, totalprice=totalprice, balance=balance)





#Функція перевірки складності паролю
def check_password_strength(password):

  # Кількість символів
  if len(password) < 5:
    flash('Password must be more than 5 symbols')
    return False

  # Різноманітність символів
  if not any(char.isupper() for char in password):
    flash('The password must contain at least one uppercase letter, one lowercase letter and a number.')
    return False
  if not any(char.islower() for char in password):
    flash('The password must contain at least one uppercase letter, one lowercase letter and a number.')
    return False
  if not any(char.isdigit() for char in password):
    flash('The password must contain at least one uppercase letter, one lowercase letter and a number')
    return False

  return True
