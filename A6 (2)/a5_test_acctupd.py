"""
White-box statement coverage tests for the account update form POST method.
Doesn't include the validation itself (we already tested that in the black-box
tests), only that we actually use the validation result and show a relevant
error message when processing an account update.

Unfortunately, due to how Tornado works with multiple processes, it's not
possible to easily measure the coverage automatically, but it's easy to
demonstrate that it covers everything manually or by removing any of the
statements which throw (i.e., validate_*) or branch (return, if), and seeing the
test fail.
"""

import main_test
import sys
from selenium.webdriver.common.by import By
from typing import Tuple, List, Optional

def do_login(chrome, app, username: str, password: str) -> None:
    """
    Submits the login form with the provided information.
    """
    print(f"logging in as {username}:{password}")
    chrome.get(f"{app}/account/login")
    chrome.find_element(By.CSS_SELECTOR, "input[name='username']").send_keys(username)
    chrome.find_element(By.CSS_SELECTOR, "input[name='password']").send_keys(password)
    chrome.find_element(By.CSS_SELECTOR, "input[type='submit']").click()
    res = chrome.execute_script("return document.querySelector('[data-username]')?.dataset?.username ?? null")
    if username != res:
        raise Exception(f"login failed (current username: {repr(res)})")

def attempt_account_update(chrome, app, fields: List[Tuple[str, str]], fake_logout = False) -> Optional[str]:
    """
    Submits the account update form, and returns the flash message, if any.
    """
    print(f"attempting account update with fields {repr(fields)}")
    chrome.get(f"{app}/account")
    for name, value in fields:
        inp = chrome.find_element(By.CSS_SELECTOR, f"input[name='{name}']")
        inp.clear()
        inp.send_keys(value)
    if fake_logout:
        print("... clearing cookies to simulate submitting account information form without being logged in")
        chrome.delete_all_cookies()
    chrome.find_element(By.CSS_SELECTOR, f"input[type='submit']").click()
    res = chrome.execute_script("return Array.from(document.querySelectorAll('aside.flash')).map(el => el.textContent.trim()).join('\\n')")
    if res == "":
        print(f"... update successful")
    else:
        print(f"... got error message: {res}")
    return res if res != "" else None

if __name__ == "__main__":
    print("starting chrome")
    with main_test.Chrome(width=800, height=1000) as chrome:
        print("starting restaurant server")
        with main_test.App(port=8080) as app:
            try:

                do_login(chrome, app, "jeff", "password")

                assert "Account updated" in attempt_account_update(chrome, app, [
                    ("firstname", "Test"),
                    ("lastname", "Test"),
                    ("password", "password1"),
                    ("address", "123 Main St"),
                    ("cardnumber", "2222420000001113"),
                    ("cardexpiry", "08/26"),
                    ("cardcode", "123"),
                ])

                assert "Invalid first or last name" in attempt_account_update(chrome, app, [
                    ("firstname", "a"*200),
                ])

                assert "Invalid first or last name" in attempt_account_update(chrome, app, [
                    ("lastname", "a"*200),
                ])

                assert "Invalid password" in attempt_account_update(chrome, app, [
                    ("password", "short"),
                ])

                assert "Invalid address" in attempt_account_update(chrome, app, [
                    ("address", "a"*600),
                ])

                assert "Invalid card information" in attempt_account_update(chrome, app, [
                    ("cardnumber", "abc"),
                ])

                assert "Invalid card information" in attempt_account_update(chrome, app, [
                    ("cardexpiry", "99/99"),
                ])

                assert "Invalid card information" in attempt_account_update(chrome, app, [
                    ("cardcode", "asfgds"),
                ])

                assert "Not logged in" in attempt_account_update(chrome, app, [], fake_logout=True)

            except AssertionError as ex:
                print(f"!!! test failed")
                raise ex

    print(f"all tests passed")
