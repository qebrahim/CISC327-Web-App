"""
White-box data interface coverage tests for order state transitions.

To verify that all lines were covered (which they should since we tested all
expected inputs and outputs, and the transition_order function should not
contain useless code), run "coverage run a5_test_ost.py", then "coverage report
-m". The missing lines should not intersect with the lines for the
transition_order method in main.py (except for the AssertionError near the end).
"""

import os
import sqlite3
import tempfile

from typing import List, Tuple, Set

import main

class TestDB:
    def __init__(self):
        self.fn = os.path.join(tempfile.mkdtemp(), "restaurant.db")
        with sqlite3.connect(self.fn) as c:
            with open("database.sql", "r") as f:
                c.executescript(f.read())
        self.db = main.RestaurantDB(self.fn)

    def __enter__(self):
        return self.db

    def __exit__(self, type, value, traceback):
        try:
            self.db.close()
        except:
            pass
        for suffix in ["", "-shm", "-wal"]:
            try:
                os.remove(self.fn + suffix)
            except:
                pass

def format_transitions(transitions: Set[Tuple[str, str]]) -> str:
    if not transitions:
        return "none"
    return ", ".join(f'{src}->{dst}' for src, dst in transitions)

def test_order_state_transition(
    name: str,
    # input variables
    order_id_exists: bool = False,
    restaurant_is_deleted: bool = False,
    user_owns_order: bool = False,
    user_is_employee: bool = False,
    user_has_billing_info: bool = False,
    items: List[Tuple[str, float, int]] = [],
    items_has_deleted: bool = False,
    items_has_other_restaurant: bool = False,
    order_status: Set[str] = set(),
    # output
    allowed_transitions: Set[Tuple[str, str]] = set(),
) -> bool:
    print()
    print(f"> RUN  {name}")

    transitions = set()
    for status in order_status:
        for target_status in [
            main.RestaurantDB.ORDER_PENDING,
            main.RestaurantDB.ORDER_ACCEPTED,
            main.RestaurantDB.ORDER_CANCELLED,
            main.RestaurantDB.ORDER_DELIVERED,
            main.RestaurantDB.ORDER_PAID,
        ]:
            if target_status == status:
                continue
            with TestDB() as db:
                try:
                    # create the test user
                    username = "testuser"
                    db.create_account(username, "password", "Test", "User")

                    # create a dummy user
                    other_username = "dummy"
                    db.create_account(other_username, "password", "Dummy", "User")

                    # create the test restaurant
                    restaurant_id = db.create_restaurant("Test Restaurant", other_username)

                    # create a dummy restaurant
                    other_restaurant_id = db.create_restaurant("Dummy Restaurant", other_username)

                    # create the order as the username, or the alternate one if they don't own the order
                    order_id = db.create_order(restaurant_id, username if user_owns_order else other_username)

                    # add the user as a employee if required
                    if user_is_employee:
                        db.add_restaurant_employee(restaurant_id, username)

                    # set up the users's billing info
                    if user_has_billing_info:
                        db.update_account(username, "Test", "User", "123 Test St", "5555555555554444", "09/26", "567")

                    # add the test case items to the order
                    last_order_item_id = None
                    for item_name, item_price, quantity in items:
                        item_id = db.add_menu_item(restaurant_id, item_name, int(item_price*100))
                        if quantity > 0:
                            db.modify_order_item(order_id, item_id, quantity)
                            last_order_item_id = item_id

                    # apply the special item conditions to the last item in the order
                    if items_has_deleted:
                        db.conn.execute("UPDATE MenuItems SET Deleted = TRUE WHERE ItemID = ?", (last_order_item_id,))
                    if items_has_other_restaurant:
                        db.conn.execute("UPDATE MenuItems SET RestaurantID = ? WHERE ItemID = ?", (other_restaurant_id, last_order_item_id))

                    # override the current order status to the initial one for the test case
                    db.conn.execute("UPDATE Orders SET Status = ? WHERE OrderID = ?", (status, order_id))

                    # maybe delete the restaurant
                    if restaurant_is_deleted:
                        db.delete_restaurant(restaurant_id)

                except Exception as ex:
                    raise Exception("failed to set up initial test case state") from ex

                try:
                    db.transition_order(username, restaurant_id if not order_id_exists else None, order_id if order_id_exists else 100, target_status)
                except main.OrderTransitionError as ex:
                    print(f"  [N]  {status:10s} -> {target_status:10s} :: {ex}")
                    continue
                except Exception as ex:
                    raise Exception(f"unexpected exception while testing state transition {status} -> {target_status}") from ex
            
                print(f"  [Y]  {status:10s} -> {target_status:10s}")
                transitions.add((status, target_status))
    
    if transitions != allowed_transitions:
        print(f"* FAIL expected only {format_transitions(allowed_transitions)} to be allowed, got {format_transitions(transitions)}")
        return False
    else:
        print(f"- PASS allowed transitions {format_transitions(allowed_transitions)}")
        return True

if __name__ == "__main__":
    fail = 0

    fail += not test_order_state_transition(
        "pending order: invalid order id for restaurant",
        order_id_exists=False,
        items=[
            ("Water", 1.23, 1),
            ("Pop", 2.34, 0),
            ("Burger", 3.45, 1),
        ],
        order_status=set([main.RestaurantDB.ORDER_PENDING]),
        allowed_transitions=set(),
    )
    fail += not test_order_state_transition(
        "pending order: restaurant is deleted",
        order_id_exists=True,
        restaurant_is_deleted=True,
        items=[
            ("Water", 1.23, 1),
            ("Pop", 2.34, 0),
            ("Burger", 3.45, 1),
        ],
        order_status=set([main.RestaurantDB.ORDER_PENDING]),
        allowed_transitions=set(),
    )
    fail += not test_order_state_transition(
        "pending order: order was created by a different customer",
        order_id_exists=True,
        restaurant_is_deleted=False,
        user_owns_order=False,
        items=[
            ("Water", 1.23, 1),
            ("Pop", 2.34, 0),
            ("Burger", 3.45, 1),
        ],
        order_status=set([main.RestaurantDB.ORDER_PENDING]),
        allowed_transitions=set(),
    )
    fail += not test_order_state_transition(
        "pending order: customer does not have billing information",
        order_id_exists=True,
        restaurant_is_deleted=False,
        user_owns_order=True,
        user_has_billing_info=False,
        items=[
            ("Water", 1.23, 1),
            ("Pop", 2.34, 0),
            ("Burger", 3.45, 1),
        ],
        order_status=set([main.RestaurantDB.ORDER_PENDING]),
        allowed_transitions=set([
            (main.RestaurantDB.ORDER_PENDING, main.RestaurantDB.ORDER_CANCELLED),
        ]),
    )
    fail += not test_order_state_transition(
        "pending order: order contains items it shouldn't",
        order_id_exists=True,
        restaurant_is_deleted=False,
        user_owns_order=True,
        user_has_billing_info=True,
        items=[
            ("Water", 1.23, 1),
            ("Pop", 2.34, 0),
            ("Burger", 3.45, 1),
        ],
        items_has_other_restaurant=True,
        order_status=set([main.RestaurantDB.ORDER_PENDING]),
        allowed_transitions=set([
            (main.RestaurantDB.ORDER_PENDING, main.RestaurantDB.ORDER_CANCELLED),
        ]),
    )
    fail += not test_order_state_transition(
        "pending order: order contains deleted item",
        order_id_exists=True,
        restaurant_is_deleted=False,
        user_owns_order=True,
        user_has_billing_info=True,
        items=[
            ("Water", 1.23, 1),
            ("Pop", 2.34, 0),
            ("Burger", 3.45, 1),
        ],
        items_has_deleted=True,
        order_status=set([main.RestaurantDB.ORDER_PENDING]),
        allowed_transitions=set([
            (main.RestaurantDB.ORDER_PENDING, main.RestaurantDB.ORDER_CANCELLED),
        ]),
    )
    fail += not test_order_state_transition(
        "pending order: order does not contain any items",
        order_id_exists=True,
        restaurant_is_deleted=False,
        user_owns_order=True,
        user_has_billing_info=True,
        items=[],
        order_status=set([main.RestaurantDB.ORDER_PENDING]),
        allowed_transitions=set([
            (main.RestaurantDB.ORDER_PENDING, main.RestaurantDB.ORDER_CANCELLED),
        ]),
    )
    fail += not test_order_state_transition(
        "is someone else's order (not an employee)",
        order_id_exists=True,
        restaurant_is_deleted=False,
        user_owns_order=False,
        user_is_employee=False,
        user_has_billing_info=True,
        items=[
            ("Water", 1.23, 1),
            ("Pop", 2.34, 0),
            ("Burger", 3.45, 1),
        ],
        order_status=set([
            main.RestaurantDB.ORDER_PENDING,
            main.RestaurantDB.ORDER_ACCEPTED,
            main.RestaurantDB.ORDER_CANCELLED,
            main.RestaurantDB.ORDER_DELIVERED,
            main.RestaurantDB.ORDER_PAID,
        ]),
        allowed_transitions=set([
        ]),
    )
    fail += not test_order_state_transition(
        "is user's order (not an employee)",
        order_id_exists=True,
        restaurant_is_deleted=False,
        user_owns_order=True,
        user_is_employee=False,
        user_has_billing_info=True,
        items=[
            ("Water", 1.23, 1),
            ("Pop", 2.34, 0),
            ("Burger", 3.45, 1),
        ],
        order_status=set([
            main.RestaurantDB.ORDER_PENDING,
            main.RestaurantDB.ORDER_ACCEPTED,
            main.RestaurantDB.ORDER_CANCELLED,
            main.RestaurantDB.ORDER_DELIVERED,
            main.RestaurantDB.ORDER_PAID,
        ]),
        allowed_transitions=set([
            (main.RestaurantDB.ORDER_PENDING, main.RestaurantDB.ORDER_PAID),
            (main.RestaurantDB.ORDER_PENDING, main.RestaurantDB.ORDER_CANCELLED),
            (main.RestaurantDB.ORDER_PAID, main.RestaurantDB.ORDER_CANCELLED),
        ]),
    )
    fail += not test_order_state_transition(
        "is someone else's order (is an employee)",
        order_id_exists=True,
        restaurant_is_deleted=False,
        user_owns_order=False,
        user_is_employee=True,
        user_has_billing_info=True,
        items=[
            ("Water", 1.23, 1),
            ("Pop", 2.34, 0),
            ("Burger", 3.45, 1),
        ],
        order_status=set([
            main.RestaurantDB.ORDER_PENDING,
            main.RestaurantDB.ORDER_ACCEPTED,
            main.RestaurantDB.ORDER_CANCELLED,
            main.RestaurantDB.ORDER_DELIVERED,
            main.RestaurantDB.ORDER_PAID,
        ]),
        allowed_transitions=set([
            (main.RestaurantDB.ORDER_PAID, main.RestaurantDB.ORDER_ACCEPTED),
            (main.RestaurantDB.ORDER_ACCEPTED, main.RestaurantDB.ORDER_DELIVERED),
        ]),
    )
    fail += not test_order_state_transition(
        "is user's order (is an employee)",
        order_id_exists=True,
        restaurant_is_deleted=False,
        user_owns_order=True,
        user_is_employee=True,
        user_has_billing_info=True,
        items=[
            ("Water", 1.23, 1),
            ("Pop", 2.34, 0),
            ("Burger", 3.45, 1),
        ],
        order_status=set([
            main.RestaurantDB.ORDER_PENDING,
            main.RestaurantDB.ORDER_ACCEPTED,
            main.RestaurantDB.ORDER_CANCELLED,
            main.RestaurantDB.ORDER_DELIVERED,
            main.RestaurantDB.ORDER_PAID,
        ]),
        allowed_transitions=set([
            # since it's their order
            (main.RestaurantDB.ORDER_PENDING, main.RestaurantDB.ORDER_PAID),
            (main.RestaurantDB.ORDER_PENDING, main.RestaurantDB.ORDER_CANCELLED),
            (main.RestaurantDB.ORDER_PAID, main.RestaurantDB.ORDER_CANCELLED),
            # since they're also an employee, they can accept and deliver their own order :p
            (main.RestaurantDB.ORDER_PAID, main.RestaurantDB.ORDER_ACCEPTED),
            (main.RestaurantDB.ORDER_ACCEPTED, main.RestaurantDB.ORDER_DELIVERED),
        ]),
    )

    print()
    if fail:
        print(f'{fail} tests failed')
    else:
        print('all tests passed')