"""
Runs the testcases from A1 against the webapp, takes screenshots, and writes the
test results as a Markdown file.

Doesn't use pytest (just uses plain webdriver) since these tests are mostly
custom and are driven by the testcases YAML file, with a freshly-initialized
database each time.
"""

import asyncio
import os
import selenium.webdriver
import multiprocessing
import tempfile
import yaml

from selenium.webdriver.common.by import By

from typing import Optional

import main


class Chrome(selenium.webdriver.Chrome):
    """
    Wrapper around the Selenium Chrome WebDriver with some stuff for the
    restaurant tests.
    """
    def __init__(self, width: int, height: int):
        opt = selenium.webdriver.ChromeOptions()
        opt.add_argument("--headless")
        opt.add_argument("--disable-gpu")
        opt.add_argument("--no-sandbox")
        super().__init__(options=opt, keep_alive=True)
        self.set_window_size(width, height)


class App:
    """
    Runs a restaurant server with a fresh database in a separate process (to
    avoid GIL and dangling socket issues).

    Use it with the "with" statement.
    """

    def __init__(self, port: int):
        # create the temp database
        self.filename = os.path.join(tempfile.mkdtemp(), "restaurant.db")

        # load the sample data
        main.restaurant_db(self.filename)

        # initialize the process
        self.port = port
        self.process = multiprocessing.Process(target=self.__main__)
        self.ready = multiprocessing.Event()

    def __main__(self):
        async def real_main(port):
            app = main.restaurant(main.RestaurantDB(self.filename))
            app.listen(port)
            self.ready.set()
            await asyncio.Event().wait()
        asyncio.run(real_main(self.port))

    def __enter__(self):
        self.process.start()
        self.ready.wait()
        return f"http://127.0.0.1:{self.port}"

    def __exit__(self, type, value, traceback):
        self.process.kill()
        for suffix in ["", "-shm", "-wal"]:
            try:
                os.remove(self.filename + suffix)
            except:
                pass


if __name__ == "__main__":
    print("... loading test cases")
    with open('A1/TESTCASES.yml', 'r') as f:
        testcases = yaml.load(f, Loader=yaml.Loader)

    report = "" # pandoc markdown
    report += f"---\n"
    report += f"title: 'main_test'\n"
    report += f"author: Group 25\n"
    report += f"geometry: paperheight=10.5in,paperwidth=14in,margin=1cm\n"
    report += f"---\n\n"

    print("... starting chrome")
    with Chrome(width=800, height=1000) as chrome:

        for uci, uc in enumerate(testcases):

            report += f"\n\n\\newpage\n\n"
            report += f"### {uci+1}. {uc['Name']}\n\n"
            report += f"**Objective**: {uc['Objective']}\n\n"
            report += f"**Arrange**: {uc['Arrange']}\n\n"
            report += f"**Act**: {uc['Act']}\n\n"
            report += f"**Assert**: {uc['Assert']}\n\n"

            for tci, tc in enumerate(uc['TestCases']):

                report += f"\n\n\\newpage\n\n"
                report += f"#### {uci+1}.{tci+1}. {uc['Name']} ({tc['Name']})\n\n"
                report += f"```yaml\n"
                report += yaml.dump(tc)
                report += f"```\n\n"

                print()
                print(f"=== EXECUTING {uci+1}.{tci+1} {uc['Name']} ({tc['Name']})")

                print("... starting restaurant server")
                with App(port=8080) as app:

                    print(f"--- InitialState")
                    if 'LoggedInUser' in tc['InitialState']:
                        print(f"... logging in as {tc['InitialState']['LoggedInUser']} with password 'password'")
                        chrome.delete_all_cookies()
                        if tc['InitialState']['LoggedInUser']:
                            chrome.get(f"{app}/account/login")
                            chrome.find_element(By.CSS_SELECTOR, "input[name='username']").send_keys(tc['InitialState']['LoggedInUser'])
                            chrome.find_element(By.CSS_SELECTOR, "input[name='password']").send_keys("password")
                            chrome.find_element(By.CSS_SELECTOR, "input[type='submit']").click()
                    if 'Page' in tc['InitialState']:
                        print(f"... navigating to {tc['InitialState']['Page']}")
                        chrome.get(f"{app}{tc['InitialState']['Page']}")
                    else:
                        raise ValueError(f"missing InitialState.Page")
                    print("... saving screenshot")
                    chrome.save_screenshot(f"A4/main.{uci+1}.{tci+1}.InitialState.png")

                    if 'InputData' in tc:
                        print("--- InputData")
                        for name, value in tc['InputData'].items():
                            if name not in ['action', 'force_action']:
                                print(f"... setting '{name}' to '{value}'")
                                inp = chrome.find_element(By.CSS_SELECTOR, f"input[name='{name}']")
                                inp.clear()
                                inp.send_keys(value)
                                chrome.execute_script("arguments[0].setAttribute('style', 'outline: red dashed 3px !important')", inp)
                        if 'action' in tc['InputData']:
                            print(f"... using action '{tc['InputData']['action']}'")
                            btn = chrome.find_element(By.CSS_SELECTOR, f"[name='action'][value='{tc['InputData']['action']}']")
                        elif 'force_action' in tc['InputData']:
                            print(f"... using FORCED (i.e., not actually there) action '{tc['InputData']['force_action']}'")
                            btn = chrome.execute_script("""
                                return (action => {
                                    let btn = document.querySelector('form').appendChild(document.createElement('button'))
                                    btn.textContent = 'FORCED ACTION: ' + action
                                    btn.setAttribute('name', action)
                                    btn.setAttribute('value', action)
                                    btn.setAttribute('style', 'outline: red dashed 3px !important')
                                    return btn
                                })(arguments[0])
                            """, tc['InputData']['force_action'])
                        else:
                            print(f"... using submit button")
                            btn = chrome.find_element(By.CSS_SELECTOR, f"input[type='submit']")
                        chrome.execute_script("arguments[0].setAttribute('style', 'outline: red dashed 3px !important')", btn)
                        print("... saving screenshot")
                        chrome.save_screenshot(f"A4/main.{uci+1}.{tci+1}.InputData.png")
                    else:
                        btn = None

                    print("--- ExpectedOutput")
                    if btn:
                        print("... clicking action")
                        btn.click()

                    print("... saving screenshot")
                    chrome.save_screenshot(f"A4/main.{uci+1}.{tci+1}.Output.png")

                    passed = True
                    if 'ExpectedOutput' in tc:
                        try:
                            for check, data in tc['ExpectedOutput'].items():
                                print(f"??? running check {check}({repr(data)})")
                                if check == 'Page':
                                    res = chrome.execute_script("return window.location.pathname")
                                    assert res == data, f"incorrect path {repr(res)}"
                                elif check == 'Message':
                                    res = chrome.execute_script("return Array.from(document.querySelectorAll('aside.flash')).map(el => el.textContent.trim()).join('\\n')")
                                    assert data in res, f"incorrect message {repr(res)}"
                                elif check == 'LoggedInUser':
                                    res = chrome.execute_script("return document.querySelector('[data-username]')?.dataset?.username ?? null")
                                    assert data == res, f"incorrect username {repr(res)}"
                                elif check == 'VisibleOrderIDs':
                                    res = chrome.execute_script("return Array.from(document.querySelectorAll('[data-orderid]')).map(el => el.dataset.orderid)")
                                    assert all([str(x) in res for x in data]), f"missing one or more orderid from page with {repr(res)}"
                                elif check == 'NotVisibleOrderIDs':
                                    res = chrome.execute_script("return Array.from(document.querySelectorAll('[data-orderid]')).map(el => el.dataset.orderid)")
                                    assert all([str(x) not in res for x in data]), f"have one or more supposedly missing orderid from page with {repr(res)}"
                                elif check == 'VisibleRestaurantIDs':
                                    res = chrome.execute_script("return Array.from(document.querySelectorAll('[data-restaurantid]')).map(el => el.dataset.restaurantid)")
                                    assert all([str(x) in res for x in data]), f"missing one or more restaurantid from page with {repr(res)}"
                                elif check == 'RestaurantName':
                                    res = chrome.execute_script("return document.querySelector('header > h1').textContent.trim()")
                                    assert data in res, f"restaurant name not in header {repr(res)}"
                                elif check == 'VisibleMenuItems':
                                    res = chrome.execute_script("""
                                        return Array.from(document.querySelectorAll("section.menu > .item > .name"))
                                            .map(el => el.tagName == "INPUT" ? el.value : el.textContent)
                                            .map(v => v.trim())
                                            .filter(v => v.length)
                                    """)
                                    assert set(res) == set(data), f"menu items do not exactly match {repr(res)}"
                                elif check == 'VisibleButtons':
                                    res = chrome.execute_script("return Array.from(document.querySelectorAll('[name=action]')).map(el => el.value)")
                                    assert all([str(x) in res for x in data]), f"missing one or more actions from page with {repr(res)}"
                                elif check == 'OrderItems':
                                    res = chrome.execute_script("""
                                        return Array.from(document.querySelectorAll("section.menu > .item"))
                                            .map(el => `${el.querySelector('.name').textContent.trim()}=${el.querySelector('.quantity').textContent.trim()}`)
                                    """)
                                    assert set(res) == set(data), f"order items do not exactly match {repr(res)}"
                                elif check == 'OrderStatus':
                                    res = chrome.execute_script("return document.querySelector('header.page--order').dataset.orderstatus")
                                    assert res == data
                                elif check == 'RestaurantListContainsName':
                                    res = chrome.execute_script("return Array.from(document.querySelectorAll('section.restaurants > a')).map(el => el.textContent.trim())")
                                    assert all([str(x) in res for x in data]), f"missing one or more restaurant names from page with {repr(res)}"
                                elif check == 'NotVisibleRestaurantNames':
                                    res = chrome.execute_script("return Array.from(document.querySelectorAll('section.restaurants > a')).map(el => el.textContent.trim())")
                                    assert all([str(x) not in res for x in data]), f"have one or more supposedly missing restaurant names from page with {repr(res)}"
                                elif check == 'VisibleEmployeeUsernames':
                                    res = chrome.execute_script("return Array.from(document.querySelectorAll('section.employees > .employee > .username')).map(el => el.textContent.trim())")
                                    assert all([str(x) in res for x in data]), f"missing one or more employee usernames from page with {repr(res)}"
                                else:
                                    raise ValueError(f"wtf: didn't implement check {check}?!?")
                        except AssertionError as ex:
                            print(f'\n!!! CHECK FAILED: {str(ex)}')
                            report += f'**CHECK FAILURE: ** `{check}({repr(data)})` - {str(ex)}\n\n'
                            passed = False

                    if passed:
                        print("*** TEST PASSED")
                        report += f'**TEST PASSED**\n\n'
                    else:
                        print("!!! TEST FAILED")
                        report += f'**TEST FAILED**\n\n'

                    report += f'| InitialState | InputData | Output |\n'
                    report += f'| --- | --- | --- |\n'
                    report += f'| ![N/A](main.{uci+1}.{tci+1}.InitialState.png) | ![N/A](main.{uci+1}.{tci+1}.InputData.png) | ![N/A](main.{uci+1}.{tci+1}.Output.png) |\n\n'

                    # note: we write the report after each case on purpose
                    os.makedirs("A4", exist_ok=True)
                    with open('A4/A4_Part1.md', 'w') as f:
                        f.write(report)
