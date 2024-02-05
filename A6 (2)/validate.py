"""
Contains functions to validate, normalize, and parse various fields.
"""

def validate_account_username(username: str) -> str:
    """
    Validates and normalizes a username.
    """
    username = username.strip()
    if username == "":
        raise ValueError("username must not be empty")
    if len(username) > 24:
        raise ValueError("username too long")
    for char in username:
        if not (char.isalnum() and char.isascii() and char.islower()):
            if char not in [".", "_"]:
                raise ValueError("username must only contain lowercase letters, numbers, dots, and underscores")
    return username

def validate_account_password(password: str) -> str:
    """
    Validates a password.
    """
    if len(password) < 6:
        raise ValueError("password must be at least 6 characters long")
    return password

def validate_restaurant_name(restaurant_name: str) -> str:
    """
    Validate and normalizes a restaurant name.
    """
    restaurant_name = restaurant_name.strip()
    if restaurant_name == "":
        raise ValueError("restaurant name must not be blank")
    if len(restaurant_name) > 100:
        raise ValueError("restaurant name too long")
    return restaurant_name

def validate_account_card_number(number: str) -> str:
    """
    Validates and normalize a credit card number.
    """
    number = number.strip()
    if number == "":
        raise ValueError("card number must not be blank")
    if not (number.isdigit() and number.isascii()):
        raise ValueError("card number must only contain numbers")
    # based on https://dev.to/seraph776/validate-credit-card-numbers-using-python-37j9
    digits = [int(num) for num in number]
    checkDigit = digits.pop(-1)
    digits.reverse()
    digits = [num * 2 if idx % 2 == 0 else num for idx, num in enumerate(digits)]
    digits = [num - 9 if idx % 2 == 0 and num > 9 else num for idx, num in enumerate(digits)]
    digits.append(checkDigit)
    checkSum = sum(digits)
    if checkSum % 10 != 0:
        raise ValueError("invalid credit card number")
    return number

def validate_account_card_code(code: str) -> str:
    """
    Validates and normalizes a credit card code.
    """
    code = code.strip()
    if code == "" or len(code) > 3:
        raise ValueError("invalid card code")
    if not (code.isdigit() and code.isascii()):
        raise ValueError("card code must only contain numbers")
    return code

def validate_account_card_expiry(date: str) -> str:
    """
    Validate card expiry number
    """
    date = date.strip()
    if len(date) != 5 or date[2] != '/' or not date.isascii() or not date[0:2].isnumeric() or not date[3:5].isnumeric():
        raise ValueError("invalid card expiry (must be MM/YY)")

    month = int(date[0:2])
    if not 1 <= month <= 12:
        raise ValueError("invalid card expiry month")

    return date

def validate_account_address(address: str) -> str:
    """
    Validates and normalizes an address.
    """
    address = address.strip()
    if address == "":
        raise ValueError("address must not be blank")
    if len(address) > 500:
        raise ValueError("address too long")
    return address

def validate_menu_item(item: str) -> str:
    """
    Validates and normalizes a menu item name.
    """
    item = item.strip()
    if item == "":
        raise ValueError("item name must not be empty")
    if len(item) > 100:
        raise ValueError("item name too long")
    return item

def validate_first_last_name(name: str) -> str:
    """
    Validates and normalizes a first/last name.
    """
    name = name.strip()
    if name == "":
        raise ValueError("first name must not be empty")
    if len(name) > 100:
        raise ValueError("first name too long")
    return name

def validate_price(price: str) -> int:
    """
    Validates and parses a price.
    """
    price = price.strip().lstrip("$").strip()
    if price == "":
        raise ValueError("price must not be blank")
    price = float(price) * 100
    if price < 0 or price % 1 != 0:
        raise ValueError("invalid price")
    return int(price)
