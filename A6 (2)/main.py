#!/usr/bin/env python
"""
Restaurant web application.

A simple web application to let users create, manage, and order from
restaurants.

How to run:
    Ensure you have Python 3.11+ installed. Find the name of the Python binary
    (replace python3 in the following commands with it). On Linux/macOS, it may
    be `python3` or `python`. On Windows, it may be `py`.

    Optionally create a venv using `python3 -m venv .env`, then activate it.

    Install the dependencies using `python3 -m pip install -r requirements.txt`.

    Finally, run the server with `python3 main.py`.

Input and output:
    The server listens on http://127.0.0.1:8080 by default, serving HTML pages
    (viewed in a web browser) as output and taking HTTP requests (from the web
    browser) as input. See the attached PDF for specific input/output examples.

    The password for all predefined users (patrick, jeff, qays) is "password".
"""

import asyncio
import datetime
import hashlib
import json
import os
import sqlite3
import tornado
import yaml

from typing import Optional, Awaitable, List, Tuple

from validate import *

class OrderTransitionError(Exception):
    pass

class RestaurantDB:
    """
    Provides access to the restaurant database.

    Note: The way Python's sqlite3 module handles transactions is a bit screwy,
    but in general, it always keeps a transaction open, and will commit or start
    a new one when requested...
    """

    """Order status: created by the customer, still editable, not visible to restaurant"""
    ORDER_PENDING = "PENDING"

    """Order status: paid, waiting for the restaurant to accept the order"""
    ORDER_PAID = "PAID"

    """Order status: cancelled by the customer"""
    ORDER_CANCELLED = "CANCELLED"

    """Order status: accepted by the restaurant, can no longer be cancelled"""
    ORDER_ACCEPTED = "ACCEPTED"

    """Order status: delivered by the restaurant, can no longer be cancelled or edited, not visible to restaurant"""
    ORDER_DELIVERED = "DELIVERED"

    def __init__(self, filename: str):
        self.conn = sqlite3.connect(filename, detect_types=sqlite3.PARSE_COLNAMES)

        self.conn.execute("PRAGMA foreign_keys = 1")  # enforce foreign key constraints

        if self.conn.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise Exception("incorrect database version; please (re)initialize the database")

    def close(self) -> None:
        self.conn.close()

    def get_user_info(self, username: str) -> Optional[Tuple[str, str, str]]:
        """
        Returns the username, first name, and lastname of the provided user if
        it exists, or None otherwise.
        """
        return self.conn.execute("SELECT Username, FirstName, LastName FROM Accounts WHERE Username = ?", (username,)).fetchone()

    def get_user_password(self, username: str) -> Optional[str]:
        """
        Gets the SHA256 password hash for the provided user if it exists.
        """
        for (PasswordSHA256,) in self.conn.execute("SELECT PasswordSHA256 FROM Accounts WHERE Username = ?", (username,)):
            return PasswordSHA256
        return None

    def get_restaurants(self) -> List[dict]:
        """
        Get all restaurants.
        """
        restaurants = []
        for (ResturantID, Owner, Name) in self.conn.execute("SELECT RestaurantID, Owner, Name FROM Restaurants WHERE DELETED <> TRUE"):
            restaurants.append({
                "RestaurantID": int(ResturantID),
                "Owner": Owner,
                "Name": Name,
            })
        return restaurants

    def get_restaurant(self, id: int) -> Optional[dict]:
        """
        Get a restaurant by its ID, or None if it does not exist.
        """
        for (ResturantID, Owner, Name) in self.conn.execute("SELECT RestaurantID, Owner, Name FROM Restaurants WHERE Deleted <> TRUE AND RestaurantID = ?", (id,)):
            return {
                "RestaurantID": int(ResturantID),
                "Owner": Owner,
                "Name": Name,
            }
        return None

    def get_menu_items(self, id: int) -> List[dict]:
        """
        Get all menu items for a restaurant.
        """
        items = []
        for (ItemID, Name, Price) in self.conn.execute("SELECT ItemID, Name, Price FROM MenuItems WHERE Deleted <> TRUE AND RestaurantID = ?", (id,)):
            items.append({
                "ItemID": int(ItemID),
                "Name": Name,
                "Price": int(Price),
            })
        return items

    def is_user_owner(self, id: int, username: int) -> bool:
        """
        Returns true if the specified username is the owner of the specified
        restaurant.
        """
        return self.conn.execute("SELECT RestaurantID FROM Restaurants WHERE RestaurantID = ? AND Owner = ?", (id, username)).fetchone() is not None

    def is_user_employee(self, id: int, username: int) -> bool:
        """
        Returns true if the specified username is an employee of the specified
        restaurant.
        """
        return self.conn.execute("SELECT RestaurantID FROM RestaurantEmployees WHERE RestaurantID = ? AND Username = ?", (id, username)).fetchone() is not None

    def get_restaurant_active_orders(self, id: int) -> List[dict]:
        """
        Get active (i.e., not pending/delivered/cancelled) orders.
        """
        orders = []
        for (OrderID, Date, Username, Address, Total, Status) in self.conn.execute("SELECT OrderID, Date AS 'Date [timestamp]', Username, Address, Total, Status FROM Orders WHERE RestaurantID = ? AND Status IN ('PAID','ACCEPTED')", (id,)):
            assert isinstance(Date, datetime.datetime)
            orders.append({
                "OrderID": int(OrderID),
                "Date": Date,
                "Username": Username,
                "Address": Address,
                "Total": int(Total),
                "Status": Status,
            })
        return orders

    def get_restaurant_employees(self, id: int) -> List[str]:
        """
        Get all employee usernames for the specified restaurant.
        """
        usernames = []
        for (Username,) in self.conn.execute("SELECT Username FROM RestaurantEmployees WHERE RestaurantID = ?", (id,)):
            usernames.append(Username)
        return usernames

    def get_account_details(self, username: str) -> Optional[dict]:
        """
        Get the account details for the specified username if it exists.
        """
        for (Username, FirstName, LastName, Address, CardNumber, CardExpiry, CardCode) in self.conn.execute("SELECT Username, FirstName, LastName, Address, CardNumber, CardExpiry, CardCode FROM Accounts WHERE Username = ?", (username,)):
            return {
                "Username": Username,
                "FirstName": FirstName,
                "LastName": LastName,
                "Address": Address,
                "CardNumber": CardNumber,
                "CardExpiry": CardExpiry,
                "CardCode": CardCode,
            }
        return None

    def get_user_orders(self, username: str) -> List[str]:
        """
        Get user orders if the username exists.
        """
        orders = []
        for (OrderID, Date, RestaurantID, RestaurantName, Username, Address, Total, Status) in self.conn.execute("SELECT Orders.OrderID, Orders.Date AS 'Date [timestamp]', Orders.RestaurantID, Restaurants.Name AS RestaurantName, Orders.Username, Orders.Address, Orders.Total, Orders.Status FROM Orders LEFT JOIN Restaurants ON Orders.RestaurantID = Restaurants.RestaurantID WHERE Username = ?", (username,)):
            assert isinstance(Date, datetime.datetime)
            orders.append({
                "OrderID": int(OrderID),
                "Date": Date,
                "RestaurantID": RestaurantID,
                "RestaurantName": RestaurantName,
                "Username": Username,
                "Address": Address,
                "Total": int(Total),
                "Status": Status,
            })
        return orders

    def get_order(self, id: int) -> Optional[dict]:
        """
        Get order information and all valid menu items for the specified order
        if it exists.
        """
        for (OrderID, Date, RestaurantID, RestaurantName, Username, Address, Total, Status) in self.conn.execute("SELECT Orders.OrderID, Orders.Date AS 'Date [timestamp]', Orders.RestaurantID, Restaurants.Name AS RestaurantName, Orders.Username, Orders.Address, Orders.Total, Orders.Status FROM Orders LEFT JOIN Restaurants ON Restaurants.RestaurantID = Orders.RestaurantID WHERE OrderID = ?", (id,)):
            assert isinstance(Date, datetime.datetime)
            order = {
                "OrderID": OrderID,
                "Date": Date,
                "RestaurantID": RestaurantID,
                "RestaurantName": RestaurantName,
                "Username": Username,
                "Address": Address,
                "Total": int(Total),
                "Status": Status,
                "Items": [],
            }
            if Status == RestaurantDB.ORDER_PENDING:
                for (ItemID, Name, Price, Quantity) in self.conn.execute("SELECT MenuItems.ItemID, Name, Price, Quantity FROM MenuItems LEFT JOIN OrderItems ON MenuItems.ItemID = OrderItems.ItemID AND OrderItems.OrderID = ? WHERE MenuItems.RestaurantID = ? AND MenuItems.Deleted <> TRUE", (OrderID, RestaurantID)):
                    order["Items"].append({
                        "ItemID": int(ItemID),
                        "Name": Name,
                        "Price": int(Price),
                        "Quantity": int(Quantity or 0),
                    })
            else:
                for (ItemID, Name, Quantity) in self.conn.execute("SELECT OrderItems.ItemID, Name, Quantity FROM OrderItems LEFT JOIN MenuItems ON MenuItems.ItemID = OrderItems.ItemID WHERE OrderItems.OrderID = ?", (OrderID,)):
                    order["Items"].append({
                        "ItemID": int(ItemID),
                        "Name": Name,
                        "Quantity": int(Quantity),
                    })
            return order
        return None

    def get_order_customer(self, order_id: int) -> Optional[str]:
        """
        Get the order username if the order exists.
        """
        for (Username,) in self.conn.execute("SELECT Username FROM Orders WHERE OrderID = ?", (order_id,)):
            return Username
        return None

    def create_restaurant(self, name: str, owner: str) -> int:
        """
        Creates a restaurant with the specified name and owner, and adds the
        owner as an employee, returning the new restaurant id.
        """
        with self.conn:
            restaurant_id = self.conn.execute("INSERT INTO Restaurants (Name, Owner) VALUES (?, ?) RETURNING RestaurantID", (name, owner)).fetchone()[0]
            self.conn.execute("INSERT INTO RestaurantEmployees (RestaurantID, Username) VALUES (?, ?)", (restaurant_id, owner))
            self.conn.commit()
            return restaurant_id

    def create_account(self, username: str, password: str, first_name: str, last_name: str) -> None:
        """
        Creates an account with the specified username and password, returning
        True if the account is new.
        """
        sha = hashlib.sha256()
        sha.update(password.encode("utf-8"))
        sha = sha.hexdigest()
        with self.conn:
            cursor = self.conn.execute("INSERT INTO Accounts (Username, PasswordSHA256, FirstName, LastName) VALUES (?, ?, ?, ?) ON CONFLICT (Username) DO NOTHING", (username, sha, first_name, last_name))
            self.conn.commit()
            return cursor.rowcount == 1

    def transition_order(self, username: str, restaurant_id: Optional[int], order_id: int, status: str) -> None:
        """
        Transitions the order status, validating all permissions and conditions,
        raising an exception if something isn't right.
        """
        with self.conn:
            row = None
            if restaurant_id is None:
                row = self.conn.execute("SELECT RestaurantID, Username, Status from Orders WHERE OrderID = ?", (order_id,)).fetchone()
            else:
                row = self.conn.execute("SELECT RestaurantID, Username, Status from Orders WHERE RestaurantID = ? AND OrderID = ?", (restaurant_id, order_id)).fetchone()
            if not row:
                raise OrderTransitionError(f"no such order {order_id} for restaurant {restaurant_id}")
            order_restaurant_id, order_username, order_status = row
            order_restaurant_id = int(order_restaurant_id)

            if self.conn.execute("SELECT RestaurantID FROM Restaurants WHERE RestaurantID = ? AND Deleted <> TRUE", (order_restaurant_id,)).fetchone() is None:
                raise OrderTransitionError(f"restaurant does not exist or has been deleted")

            if order_status == RestaurantDB.ORDER_PENDING:
                if status == RestaurantDB.ORDER_PAID:
                    if order_username != username:
                        raise OrderTransitionError("cannot pay for someone else's order")

                    row = self.conn.execute("SELECT Address, CardNumber, CardExpiry, CardCode FROM Accounts WHERE Username = ? AND Address <> '' AND CardNumber <> '' AND CardExpiry <> '' AND CardCode <> ''", (order_username,)).fetchone()
                    if not row:
                        raise OrderTransitionError("cannot pay for order without address and billing information set for account")
                    acct_address, acct_card, acct_card_expiry, acct_card_code = row

                    total = 0
                    items = 0
                    for (ItemID, Quantity, RestaurantID, ItemName, Price, Deleted) in self.conn.execute("SELECT OrderItems.ItemID, OrderItems.Quantity, MenuItems.RestaurantID, MenuItems.Name, MenuItems.Price, MenuItems.Deleted FROM OrderItems LEFT JOIN MenuItems ON MenuItems.ItemID = OrderItems.ItemID WHERE OrderItems.OrderID = ?", (order_id,)):
                        if int(Quantity) > 0:
                            if int(RestaurantID) != order_restaurant_id:
                                raise OrderTransitionError(f"order contains item {ItemName} from another restaurant (wtf... are you messing with the requests or the database)")
                            if bool(Deleted):
                                raise OrderTransitionError(f"cannot order deleted item {ItemName}")
                            total += int(Price) * int(Quantity)
                            items += 1

                    if items == 0:
                        raise OrderTransitionError(f"order must contain at least one item")

                    self.conn.execute("UPDATE Orders SET Address = ?, Total = ? WHERE OrderID = ?", (acct_address, total, order_id))
                    # okay, fallthrough (customer: PENDING -> PAID, with valid billing information)

                elif status == RestaurantDB.ORDER_CANCELLED:
                    if order_username != username:
                        raise OrderTransitionError("cannot cancel someone else's order")
                    # okay, fallthrough (customer: PENDING -> CANCELLED)

                else:
                    raise OrderTransitionError(f"bad transition {order_status} -> {status}")
            elif order_status == RestaurantDB.ORDER_PAID:
                if status == RestaurantDB.ORDER_CANCELLED:
                    if order_username != username:
                        raise OrderTransitionError("cannot cancel someone else's order")
                    # okay, fallthrough (customer: PAID -> CANCELLED)

                elif status == RestaurantDB.ORDER_ACCEPTED:
                    if not self.is_user_employee(order_restaurant_id, username):
                        raise OrderTransitionError("cannot accept an order as a non-employee")
                    # okay, fallthrough (employee: CANCELLED -> ACCEPTED)

                else:
                    raise OrderTransitionError(f"bad transition {order_status} -> {status}")
            elif order_status == RestaurantDB.ORDER_CANCELLED:
                raise OrderTransitionError(f"bad transition {order_status} -> {status}")
            elif order_status == RestaurantDB.ORDER_ACCEPTED:
                if status == RestaurantDB.ORDER_DELIVERED:
                    if not self.is_user_employee(order_restaurant_id, username):
                        raise OrderTransitionError("cannot deliver an order as a non-employee")
                    # okay, fallthrough (employee: ACCEPTED -> DELIVERED)

                elif status == RestaurantDB.ORDER_CANCELLED:
                    raise OrderTransitionError("accepted order cannot be cancelled")

                else:
                    raise OrderTransitionError(f"bad transition {order_status} -> {status}")
            elif order_status == RestaurantDB.ORDER_DELIVERED:
                raise OrderTransitionError(f"bad transition {order_status} -> {status}")
            else:
                raise AssertionError(f"invalid order status {order_status} from database")

            self.conn.execute("UPDATE Orders SET Status = ? WHERE OrderID = ?", (status, order_id))
            self.conn.commit()

    def create_order(self, restaurant_id: int, username: str) -> int:
        """
        Creates an order for the specified user and returns the ID.
        """
        with self.conn:
            if self.conn.execute("SELECT RestaurantID FROM Restaurants WHERE RestaurantID = ? AND Deleted <> TRUE", (restaurant_id,)).fetchone() is None:
                raise OrderTransitionError(f"restaurant does not exist or has been deleted")
            order_id = self.conn.execute("INSERT INTO Orders (RestaurantID, Username, Date) VALUES (?, ?, ?) RETURNING OrderID", (restaurant_id, username, datetime.datetime.now())).fetchone()[0]
            self.conn.commit()
            return order_id

    def modify_order_item(self, order_id: int, item_id: int, delta: int) -> None:
        """
        Update the quantity of an item in an order.
        """
        with self.conn:
            row = self.conn.execute("SELECT Status FROM Orders WHERE OrderID = ?", (order_id,)).fetchone()
            if row is None:
                raise OrderTransitionError(f"order {order_id} does not exist")

            status = row[0]
            if status != "PENDING":
                raise OrderTransitionError(f"cannot modify items for non-pending order {order_id} (is {status})")

            # note: the webapp won't show options to add bad items (and we validate that the item is for the correct restaurant when paying for the order), so we don't have to do it here

            self.conn.execute("INSERT INTO OrderItems (OrderID, ItemID) VALUES (?, ?) ON CONFLICT (OrderID, ItemID) DO NOTHING", (order_id, item_id))
            self.conn.execute("UPDATE OrderItems SET Quantity = MAX(0, Quantity + ?) WHERE OrderID = ? AND ItemID = ?", (delta, order_id, item_id))
            self.conn.commit()

    def update_restaurant_name(self, id: int, name: str) -> None:
        """
        Updates the restaurant name if the restaurant exists.
        """
        with self.conn:
            self.conn.execute("UPDATE Restaurants SET Name = ? WHERE RestaurantID = ? AND Deleted <> TRUE", (name, id))
            self.conn.commit()

    def delete_restaurant(self, id: int) -> None:
        """
        Marks a restaurant as deleted if it exists.
        """
        with self.conn:
            self.conn.execute("UPDATE Restaurants SET Deleted = TRUE WHERE RestaurantID = ?", (id,))
            self.conn.commit()

    def remove_restaurant_employee(self, id: int, username: str) -> None:
        """
        Removes an employee from a restaurant if it exists.
        """
        with self.conn:
            self.conn.execute("DELETE FROM RestaurantEmployees WHERE RestaurantID = ? AND Username = ?", (id, username))
            self.conn.commit()

    def add_restaurant_employee(self, id: int, username: str) -> None:
        """
        Adds an employee to a restaurant, raising an exception if either doesn't
        exist.
        """
        with self.conn:
            if self.conn.execute("SELECT Username FROM Accounts WHERE Username = ?", (username,)).fetchone() is None:
                raise Exception("user does not exist")

            # the constraints will raise an exception if it changes between the check and here
            self.conn.execute("INSERT INTO RestaurantEmployees (RestaurantID, Username) VALUES (?, ?) ON CONFLICT (RestaurantID, Username) DO NOTHING", (id, username))
            self.conn.commit()

    def add_menu_item(self, restaurant_id: int, item_name: str, item_price: int) -> int:
        """
        Adds a menu item to a restaurant with specified item name and price.
        """
        with self.conn:
            if self.conn.execute("SELECT RestaurantID FROM Restaurants WHERE RestaurantID = ? AND Deleted <> TRUE", (restaurant_id,)).fetchone() is None:
                raise OrderTransitionError(f"restaurant does not exist or has been deleted")
            item_id = self.conn.execute("INSERT INTO MenuItems (RestaurantID, Name, Price) VALUES (?, ?, ?) RETURNING ItemID", (restaurant_id, item_name, item_price)).fetchone()[0]
            self.conn.commit()
            return item_id

    def update_menu_item(self, restaurant_id: int, item_id: int, item_name: str, item_price: int) -> None:
        """
        Adds a menu item to a restaurant with the specified name and price.
        """
        with self.conn:
            if self.conn.execute("SELECT RestaurantID FROM Restaurants WHERE RestaurantID = ? AND Deleted <> TRUE", (restaurant_id,)).fetchone() is None:
                raise OrderTransitionError(f"restaurant does not exist or has been deleted")
            # restaurantid check seems unnecessary, but is required for security
            self.conn.execute("UPDATE MenuItems SET Name = ?, Price = ? WHERE RestaurantID = ? AND ItemID = ?", (item_name, item_price, restaurant_id, item_id))
            self.conn.commit()

    def delete_menu_item(self, restaurant_id: int, item_id: int) -> None:
        """
        Deletes a menu item from a restaurant if it exists.
        """
        with self.conn:
            # restaurantid check seems unnecessary, but is required for security
            self.conn.execute("UPDATE MenuItems SET Deleted = TRUE WHERE RestaurantID = ? AND ItemID = ?", (restaurant_id, item_id))
            self.conn.commit()

    def update_account(self, username, first_name, last_name, address, card_number, card_expiry, card_code, password=None):
        """
        Updates account information (must have already been validated) including
        the first/last name, address, card number/expiry/code, and optionally
        the password.
        """
        if password is not None:
            sha = hashlib.sha256()
            sha.update(password.encode("utf-8"))
            password = sha.hexdigest()
        with self.conn:
            if password is not None:
                self.conn.execute("UPDATE Accounts SET PasswordSHA256 = ? WHERE Username = ?", (password, username))
            self.conn.execute("UPDATE Accounts SET FirstName = ?, LastName = ?, Address = ?, CardNumber = ?, CardExpiry = ?, CardCode = ? WHERE Username = ?", (first_name, last_name, address, card_number, card_expiry, card_code, username))
            self.conn.commit()

class BaseHandler(tornado.web.RequestHandler):
    """
    Contains common logic used for the restaurant application.
    """

    FLASH_COOKIE_NAME = "flash"
    USERNAME_COOKIE_NAME = "username"

    @property
    def db(self) -> RestaurantDB:
        db = self.settings["db"]
        if not isinstance(db, RestaurantDB):
            raise ValueError("No database set in the application settings")
        return db


    def prepare(self):
        """
        Executed before every request. Called by Tornado.
        """

        # get user info
        self.__user_info = None
        username = self.get_signed_cookie(BaseHandler.USERNAME_COOKIE_NAME)
        if username is not None:
            self.__user_info = self.db.get_user_info(username.decode("utf-8"))
            if self.__user_info is None:
                self.flash("Current user was deleted or does not exist. Logged out.", "warning")
                self.set_current_user(None)


    def get_current_user(self) -> Optional[str]:
        """
        Gets the currently logged in username. Will be a valid user at the time
        of the request.
        """
        if self.__user_info is None:
            return None
        return self.__user_info[0]


    def set_current_user(self, username: Optional[str]=None):
        """
        Sets the currently logged in user. Does not validate it.
        """
        if username is None:
            self.clear_cookie(BaseHandler.USERNAME_COOKIE_NAME)
        else:
            self.set_signed_cookie(BaseHandler.USERNAME_COOKIE_NAME, username)


    def flash(self, msg: str, kind: str="info"):
        """
        Shows a message on the next page load which calls our render function.
        The kind is used in the class name so it can be styled CSS.

        Note that this is limited by the maximum cookie length.
        """
        flash_messages = self.get_flash()
        flash_messages.append([kind, msg])  # use an array instead of an object to keep it compact
        self.set_secure_cookie(BaseHandler.FLASH_COOKIE_NAME, json.dumps(flash_messages))


    def get_flash(self, clear: bool=True) -> List[Tuple[str, str]]:
        """
        Gets pending flash messages and clears the cookie.
        """
        flash_messages = []
        try:
            obj = json.loads(self.get_signed_cookie(BaseHandler.FLASH_COOKIE_NAME))
            if isinstance(obj, list):
                for x in obj:
                    if not isinstance(x, list):
                        continue
                    if len(x) != 2:
                        continue
                    if not isinstance(x[0], str):
                        continue
                    if not isinstance(x[1], str):
                        continue
                    flash_messages.append((x[0], x[1]))
        except:
            pass
        if clear:
            self.clear_cookie(BaseHandler.FLASH_COOKIE_NAME)
        return flash_messages


    def render(self, *args, **kwargs):
        """
        Renders an application page.
        """
        super().render(*args, **kwargs,
            flash_messages=self.get_flash(),
            user_info=self.__user_info,
        )


class IndexHandler(BaseHandler):
    """
    Handles the homepage for the application.
    """

    def get(self):
        """
        Redirects to the restaurants list.
        """
        self.redirect("/restaurants", status=302)


class AccountHandler(BaseHandler):
    """
    Handles the account page.
    """

    def get(self):
        """
        Handles GET requests to the account page, showing information about the
        logged in user.
        """

        username = self.get_current_user()
        if not username:
            self.redirect("/account/login", status=302)
            return

        user = self.db.get_account_details(username)
        if not user:
            self.redirect("/account/login", status=302)
            return

        self.render("account.html", user=user)


    def post(self):
        """
        Handles POST requests to the account page, updating the information.
        """

        username = self.get_current_user()
        if username is None:
            self.flash("Not logged in.", kind="error")
            self.redirect("/account/login", False, status=303)
            return

        first_name = ""
        last_name = ""
        password = ""
        address = ""
        card_number = ""
        card_expiry = ""
        card_code = ""

        try:
            first_name = validate_first_last_name(self.get_body_argument("firstname", default=first_name))
            last_name = validate_first_last_name(self.get_body_argument("lastname", default=last_name))
        except Exception as ex:
            self.flash(f"Invalid first or last name ({ex}).", kind="error")
            self.redirect(self.request.path, status=303)
            return

        try:
            password = self.get_body_argument("password", default=password, strip=False)
            if password == "":
                password = None
            else:
                password = validate_account_password(password)
        except Exception as ex:
            self.flash(f"Invalid password ({ex}).", kind="error")
            self.redirect(self.request.path, status=303)
            return

        try:
            address = validate_account_address(self.get_body_argument("address", default=address))
        except Exception as ex:
            self.flash(f"Invalid address ({ex}).", kind="error")
            self.redirect(self.request.path, status=303)
            return

        try:
            card_number = validate_account_card_number(self.get_body_argument("cardnumber", default=card_number))
            card_expiry = validate_account_card_expiry(self.get_body_argument("cardexpiry", default=card_expiry))
            card_code = validate_account_card_code(self.get_body_argument("cardcode", default=card_code))
        except Exception as ex:
            self.flash(f"Invalid card information ({ex}).", kind="error")
            self.redirect(self.request.path, status=303)
            return

        self.db.update_account(username, first_name, last_name, address, card_number, card_expiry, card_code, password)
        self.flash("Account updated.", kind="info")
        self.redirect("/account", False, status=303)


class AccountCreateHandler(BaseHandler):
    """
    Handles account creation requests.
    """

    def get(self):
        """
        Handles GET requests to the account creation page, showing the account
        creation form.
        """
        self.render("account_create.html")


    def post(self):
        """
        Handles POST requests to the account creation page, creating an account.
        """
        username = ""
        password = ""
        first_name = ""
        last_name = ""
        try:
            username = validate_account_username(self.get_body_argument("username", default=username))
            password = validate_account_password(self.get_body_argument("password", default=password, strip=False))
            first_name = validate_first_last_name(self.get_body_argument("first_name", default=first_name))
            last_name = validate_first_last_name(self.get_body_argument("last_name", default=last_name))
        except Exception as ex:
            self.flash(f"Invalid account information ({ex}).", kind="error")
            self.redirect(self.request.path, status=303)
            return

        if not self.db.create_account(username, password, first_name, last_name):
            self.flash(f"Username already exists.", kind="error")
            self.redirect(self.request.path, status=303)
            return

        self.set_current_user(username)
        self.flash("Account created.", kind="info")
        self.redirect("/account", status=303)


class AccountLoginHandler(BaseHandler):
    """
    Handles requests to log into the application.
    """

    def get(self):
        """
        Handles GET requests to the login page, showing the login form.
        """
        self.render("account_login.html")

    def post(self):
        """
        Processes the login form.
        """

        username = self.get_argument("username")
        password = self.get_argument("password")

        correct_password_hash = self.db.get_user_password(username)
        if correct_password_hash is None:
            self.flash("User does not exist.", kind="error")
            self.redirect(self.request.path, status=303)
            return

        hashed_password = hashlib.sha256()
        hashed_password.update(password.encode("utf-8"))
        hashed_password = hashed_password.hexdigest()

        if hashed_password != correct_password_hash:
            self.flash("Incorrect password.", kind="error")
            self.redirect(self.request.path, status=303)
            return

        self.set_current_user(username)
        self.redirect("/")


class AccountLogoutHandler(BaseHandler):
    """
    Handles requests to log out of the application.
    """

    def get(self):
        """
        Serves the logout page, which automatically submits a form to log the user out.
        """
        self.render("account_logout.html")

    def post(self):
        """
        Clears the logged in user and redirects to the homepage.
        """
        self.set_current_user()
        self.redirect("/")


class RestaurantsHandler(BaseHandler):
    """
    Handles requests to view the list of restaurants.
    """

    def get(self):
        """
        Handles GET requests to the restaurants page, showing the list of
        restaurants.
        """
        self.render("restaurants.html", restaurants=self.db.get_restaurants())


    def post(self):
        """
        Handles POST requests to the restaurants page, creating a new restaurant.
        """
        username = self.get_current_user()
        if username is None:
            self.flash("Not logged in.", kind="error")
            self.redirect(self.request.path, status=303)
            return

        name = ""
        try:
            name = validate_restaurant_name(self.get_body_argument("name", default=name))
        except Exception as ex:
            self.flash(str(ex), kind="error")
            self.redirect(self.request.path, status=303)
            return

        self.db.create_restaurant(name, username)
        self.flash("Restaurant created.")
        self.redirect("/restaurants", False, status=303)


class RestaurantHandler(BaseHandler):
    """
    Handles requests to view or modify a single restaurant's information.
    """

    def get(self, id):
        """
        Handles GET requests to the restaurant page, showing details about the
        restaurant, allowing customers to place orders, employees to complete
        orders, and owners to edit restaurant information.
        """
        restaurant = self.db.get_restaurant(int(id))
        if restaurant is None:
            self.flash(f"Restaurant {id} does not exist.", kind="error")
            self.redirect("/restaurants")
            return

        menu_items = self.db.get_menu_items(int(id))

        username = self.get_current_user()
        is_user_employee = self.db.is_user_employee(int(id), username) if username else False
        is_user_owner = self.db.is_user_owner(int(id), username) if username else False

        orders = None
        if is_user_employee:
            orders = self.db.get_restaurant_active_orders(int(id))

        employees = None
        if is_user_owner:
            employees = self.db.get_restaurant_employees(int(id))

        self.render("restaurant.html",
            restaurant=restaurant,
            menu_items=menu_items,
            is_user_employee=is_user_employee,
            is_user_owner=is_user_owner,
            orders=orders,
            employees=employees,
        )


    def post(self, id):
        """
        Handles POST requests to the restaurant page.
        """

        username = self.get_current_user()
        if not username:
            self.flash("Not logged in.", kind="error")
            self.redirect("/account/login", 303)
            return

        id = int(id)
        action = dict(enumerate(self.get_body_argument("action", default="", strip=False).split(":")))
        if action[0] == "restaurant":
            if action[1] == "update":
                return self.post_restaurant_update(id)
            if action[1] == "delete":
                return self.post_restaurant_delete(id)
            if action[1] == "order":
                return self.post_restaurant_order(id)
        if action[0] == "employee":
            if action[1] == "new" and action[2] == "add":
                    return self.post_employee_add(id)
            else:
                if action[2] == "remove":
                    return self.post_employee_remove(id, action[1])
        if action[0] == "item":
            if action[1] == "new" and action[2] == "add":
                    return self.post_item_add(id)
            else:
                item_id = None
                try:
                    item_id = int(action[1])
                except Exception as ex:
                    self.flash("Bad action item.", kind="error")
                    self.redirect(self.request.path, status=303)
                    return
                if action[2] == "update":
                    return self.post_item_update(id, item_id)
                if action[2] == "delete":
                    return self.post_item_delete(id, item_id)
        if action[0] == "order":
            order_id = None
            try:
                order_id = int(action[1])
            except Exception as ex:
                self.flash("Bad action order.", kind="error")
                self.redirect(self.request.path, status=303)
                return
            if action[2] == "accept":
                return self.post_order_accept(id, order_id)
            if action[2] == "deliver":
                return self.post_order_deliver(id, order_id)

        self.flash("Bad action.", kind="error")
        self.redirect(self.request.path, status=303)

    def post_restaurant_update(self, restaurant_id):
        """ POST action = restaurant:update """

        if not self.db.is_user_owner(restaurant_id, self.get_current_user()):
            self.flash("Not authorized to perform this action.", kind="error")
            self.redirect(self.request.path, 303)
            return

        restaurant_name = ""
        try:
            restaurant_name = validate_restaurant_name(self.get_body_argument("restaurant:name", default=restaurant_name))
        except Exception as ex:
            self.flash(str(ex), kind="error")

        self.db.update_restaurant_name(restaurant_id, restaurant_name)
        self.redirect(self.request.path, 303)

    def post_restaurant_delete(self, restaurant_id):
        """ POST action = restaurant:delete """

        if not self.db.is_user_owner(restaurant_id, self.get_current_user()):
            self.flash("Not authorized to perform this action.", kind="error")
            self.redirect(self.request.path, 303)
            return

        self.db.delete_restaurant(restaurant_id)
        self.redirect("/restaurants", 303)

    def post_restaurant_order(self, restaurant_id):
        """ POST action = restaurant:order """
        order_id = self.db.create_order(restaurant_id, self.get_current_user())
        self.redirect(f"/orders/{order_id}", 303)

    def post_employee_add(self, restaurant_id):
        """ POST action = employee:new:add """

        if not self.db.is_user_owner(restaurant_id, self.get_current_user()):
            self.flash("Not authorized to perform this action.", kind="error")
            self.redirect(self.request.path, 303)
            return

        try:
            self.db.add_restaurant_employee(restaurant_id, self.get_body_argument("employee:new:username", default=""))
        except Exception as ex:
            self.flash(str(ex), kind="error")
        self.redirect(self.request.path, 303)

    def post_employee_remove(self, restaurant_id, username):
        """ POST action = employee:{username}:remove """

        if not self.db.is_user_owner(restaurant_id, self.get_current_user()):
            self.flash("Not authorized to perform this action.", kind="error")
            self.redirect(self.request.path, 303)
            return

        self.db.remove_restaurant_employee(restaurant_id, username)
        self.redirect(self.request.path, 303)

    def post_item_add(self, restaurant_id):
        """ POST action = item:new:add """

        if not self.db.is_user_owner(restaurant_id, self.get_current_user()):
            self.flash("Not authorized to perform this action.", kind="error")
            self.redirect(self.request.path, 303)
            return

        item_name = ""
        item_price = ""
        try:
            item_name = validate_menu_item(self.get_body_argument("item:new:name", default=item_name))
            item_price = validate_price(self.get_body_argument("item:new:price", default=item_price))
        except Exception as ex:
            self.flash(str(ex), kind="error")
            self.redirect(self.request.path, 303)
            return

        self.db.add_menu_item(restaurant_id, item_name, item_price)
        self.redirect(self.request.path, 303)

    def post_item_update(self, restaurant_id, item_id):
        """ POST action = item:{item_id}:update """

        if not self.db.is_user_owner(restaurant_id, self.get_current_user()):
            self.flash("Not authorized to perform this action.", kind="error")
            self.redirect(self.request.path, 303)
            return

        item_name = ""
        item_price = ""
        try:
            item_name = validate_menu_item(self.get_body_argument(f"item:{item_id}:name", default=item_name))
            item_price = validate_price(self.get_body_argument(f"item:{item_id}:price", default=item_price))
        except Exception as ex:
            self.flash(str(ex), kind="error")
            self.redirect(self.request.path, 303)
            return

        self.db.update_menu_item(restaurant_id, item_id, item_name, item_price)
        self.redirect(self.request.path, 303)

    def post_item_delete(self, restaurant_id, item_id):
        """ POST action = item:{item_id}:delete """

        if not self.db.is_user_owner(restaurant_id, self.get_current_user()):
            self.flash("Not authorized to perform this action.", kind="error")
            self.redirect(self.request.path, 303)
            return

        self.db.delete_menu_item(restaurant_id, item_id)
        self.redirect(self.request.path, 303)

    def post_order_accept(self, restaurant_id, order_id):
        """ POST action = order:{order_id}:accept """
        try:
            self.db.transition_order(self.get_current_user(), restaurant_id, order_id, RestaurantDB.ORDER_ACCEPTED)
            self.flash("Order accepted.", kind="info")
        except OrderTransitionError as ex:
            self.flash(str(ex), kind="error")
        self.redirect(self.request.path, 303)

    def post_order_deliver(self, restaurant_id, order_id):
        """ POST action = order:{order_id}:deliver """
        try:
            self.db.transition_order(self.get_current_user(), restaurant_id, order_id, RestaurantDB.ORDER_DELIVERED)
            self.flash("Order delivered.", kind="info")
        except OrderTransitionError as ex:
            self.flash(str(ex), kind="error")
        self.redirect(self.request.path, 303)


class CustomerOrdersHandler(BaseHandler):
    """
    Handles requests to the customer own orders list.
    """

    def get(self):
        """
        Handles GET requests to the customer orders page, showing details about
        the logged in customer's order status.
        """
        username = self.get_current_user()
        if not username:
            self.redirect("/account/login", status=302)
            return

        orders = self.db.get_user_orders(username)
        self.render("orders.html", orders=orders)  # TODO: get data


class CustomerOrderHandler(BaseHandler):
    """
    Handles requests to view a single customer's order from the restaurant's
    perspective.
    """

    def get(self, id: str):
        """
        Handles GET requests to the customer order page, showing details about a
        single order, and allowing pending orders to be modified.
        """
        username = self.get_current_user()
        if not username:
            self.redirect("/account/login", status=302)
            return

        order = self.db.get_order(int(id))
        if not order:
            self.flash("Order does not exist.", kind="error")
            self.redirect("/orders")
            return

        is_employee = self.db.is_user_employee(order["RestaurantID"], username)
        is_own_order = order["Username"] == username

        if not (is_employee or is_own_order):
            self.flash("Not authorized to view order.", kind="error")
            self.redirect("/orders")
            return

        self.render("order.html",
            order=order,
            is_employee=is_employee,
            is_own_order=is_own_order
        )


    def post(self, id: str):
        """
        Handles POST requests to the customer order page.
        """

        username = self.get_current_user()
        if not username:
            self.flash("Not logged in.", kind="error")
            self.redirect("/account/login", 303)
            return

        id = int(id)
        action = dict(enumerate(self.get_body_argument("action", default="", strip=False).split(":")))
        if action[0] == "order":
            if action[1] == "pay":
                return self.post_order_pay(id)
            if action[1] == "cancel":
                return self.post_order_cancel(id)
            if action[1] == "accept":
                return self.post_order_accept(id)
            if action[1] == "deliver":
                return self.post_order_deliver(id)
        if action[0] == "item":
            item_id = None
            try:
                item_id = int(action[1])
            except Exception as ex:
                self.flash("Bad action item.", kind="error")
                self.redirect(self.request.path, status=303)
                return
            if action[2] == "add":
                return self.post_item_add(id, item_id)
            if action[2] == "subtract":
                return self.post_item_subtract(id, item_id)

        self.flash("Bad action.", kind="error")
        self.redirect(self.request.path, status=303)

    def post_order_pay(self, order_id: int):
        """ POST action = order:pay """
        try:
            self.db.transition_order(self.get_current_user(), None, order_id, RestaurantDB.ORDER_PAID)
            self.flash("Order submitted.", kind="info")
        except OrderTransitionError as ex:
            self.flash(str(ex), kind="error")
        self.redirect(self.request.path, 303)

    def post_order_cancel(self, order_id: int):
        """ POST action = order:cancel """
        try:
            self.db.transition_order(self.get_current_user(), None, order_id, RestaurantDB.ORDER_CANCELLED)
            self.flash("Order cancelled.", kind="info")
        except OrderTransitionError as ex:
            self.flash(str(ex), kind="error")
        self.redirect(self.request.path, 303)

    def post_order_accept(self, order_id: int):
        """ POST action = order:accept """
        try:
            self.db.transition_order(self.get_current_user(), None, order_id, RestaurantDB.ORDER_ACCEPTED)
            self.flash("Order accepted.", kind="info")
        except OrderTransitionError as ex:
            self.flash(str(ex), kind="error")
        self.redirect(self.request.path, 303)

    def post_order_deliver(self, order_id: int):
        """ POST action = order:deliver """
        try:
            self.db.transition_order(self.get_current_user(), None, order_id, RestaurantDB.ORDER_DELIVERED)
            self.flash("Order delivered.", kind="info")
        except OrderTransitionError as ex:
            self.flash(str(ex), kind="error")
        self.redirect(self.request.path, 303)

    def post_item_add(self, order_id: int, item_id: int):
        """ POST action = item:{item_id}:add """
        if self.db.get_order_customer(order_id) != self.get_current_user():
            self.flash("Not the order owner.", kind="error")
        else:
            self.db.modify_order_item(order_id, item_id, 1)
        self.redirect(self.request.path, 303)

    def post_item_subtract(self, order_id: int, item_id: int):
        """ POST action = item:{item_id}:subtract """
        if self.db.get_order_customer(order_id) != self.get_current_user():
            self.flash("Not the order owner.", kind="error")
        else:
            self.db.modify_order_item(order_id, item_id, -1)
        self.redirect(self.request.path, 303)

def restaurant(db: RestaurantDB):
    """
    Initialize and return the restaurant application.
    """
    return tornado.web.Application(
        [
            (r"/", IndexHandler),
            (r"/account", AccountHandler),
            (r"/account/create", AccountCreateHandler),
            (r"/account/login", AccountLoginHandler),
            (r"/account/logout", AccountLogoutHandler),
            (r"/restaurants", RestaurantsHandler),
            (r"/restaurants/([0-9]+)", RestaurantHandler),
            (r"/orders", CustomerOrdersHandler),
            (r"/orders/([0-9]+)", CustomerOrderHandler),
        ],

        # development
        static_hash_cache=False,  # disable caching for development
        compiled_template_cache=False,  # disable caching for development
        serve_traceback=True,  # serve error pages to browsers

        # cookies
        cookie_secret="dummy",  # insecure!!!

        # files
        template_path="./frontend/templates",

        # database
        db=db,
    )


def restaurant_db(filename: str):
    """
    Initializes the restaurant database.
    """
    conn = sqlite3.connect(filename)
    with open("database.sql", "r") as f:
        conn.executescript(f.read())
    with open('A1/INITIAL_DATA.yml', 'r') as f:
        data = yaml.load(f, Loader=yaml.Loader)
    for table in data:
        for row in data[table]:
            keys = sorted(row.keys())
            values = [f"'{str(row[key])}'" for key in keys]
            for (i, key) in enumerate(keys):
                if key in ['Total', 'Price']:
                    values[i] = str(int(row[key] * 100))
                elif isinstance(row[key], bool):
                    values[i] = 'TRUE' if row[key] else 'FALSE'
                elif isinstance(row[key], int):
                    values[i] = str(row[key])
            value_keys = [f'"{key}"' for key in keys]
            conn.execute(f"INSERT INTO {table} ({', '.join(value_keys)}) VALUES ({', '.join(values)});")
    conn.commit()
    conn.close()


async def main(port=8081, db='restaurant.db'):
    """
    Main entrypoint for the server, using the specified port.
    """
    if not os.path.exists(db):
        print("initializing database and loading sample data")
        restaurant_db(db)
    else:
        print("using existing database (delete it to re-initialize it with sample data)")

    print(f"starting server on port {port} (http://127.0.0.1:{port})")
    app = restaurant(RestaurantDB(db))
    app.listen(port)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
