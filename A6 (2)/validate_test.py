"""
Black-box tests for the validation functions using input partitioning.
"""


import pytest

from typing import Callable


def do_validate_test(func: Callable[[str], any], input: str, expected: any):
    """
    Runs a paramaterized test against a validate function.
    """
    actual = None
    try:
        actual = func(input)
    except:
        pass
    if expected is None:
        assert actual == None, f"'{input}' should have been invalid; got '{actual}'"
    else:
        assert actual == expected, f"'{input}' should have been parsed into '{expected}'"


@pytest.mark.parametrize("input, expected", [
    # invalid: non-empty
    ("",       None), # empty input check
    (" ",      None), # with trimmed spaces
    ("      ", None), # with trimmed spaces

    # invalid: length errors
    ("abcdefghijklmnopqrstuvwxy", None), # > 24
    ("  abcdefghijklmnopqrstuvwxy  ", None), # > 24, with trimmed spaces

    # invalid: invalid characters
    ("abc123#@", None), # non-alphanumeric
    ("öäüß", None), # non-ascii
    ("abCdef", None), # uppercaseusername
    ("abc-def", None), # dash
    ("abc def", None), # space

    # valid
    ("abcdefghijklmnopqrstuvwx", "abcdefghijklmnopqrstuvwx"), # 24
    ("ab_c", "ab_c"),
    ("ab.c", "ab.c"),
    ("  dabcdeffhijklmn", "dabcdeffhijklmn"),
    ("dabcdeffhijklmn", "dabcdeffhijklmn"),
])
def test_validate_account_username(input, expected):
    from validate import validate_account_username
    do_validate_test(validate_account_username, input, expected)


@pytest.mark.parametrize("input, expected", [
    # invalid: length
    ("jhs6", None), # < 6
    ("", None), # empty input check
    (" ", None), # with trimmed spaces

    # valid
    ("ahs73g", "ahs73g"), # 6
    ("ahs73gD", "ahs73gD"), # 7
    ("ABC12@3DEF", "ABC12@3DEF"),
])
def test_validate_account_password(input, expected):
    from validate import validate_account_password
    do_validate_test(validate_account_password, input, expected)


@pytest.mark.parametrize("input, expected", [
    # : non-empty
    ("",      None), # empty input check
    (" ",     None), # with trimmed spaces
    ("     ", None), # with trimmed spaces

    # invalid: length
    ("dD5PmKQ7SU5ornjAOv5J7VrzNtYqRgmoOfksFYvrRaFjdhsdhjsdhsjdhsTvaEVmJyGDtPtE6sNbgEXyvWFnYQPErQSnzBxG4HsFNvaoGrcF5RaJd8dD5PmKQ7SU5ornjAOv5J7VrzNtYqRgmoOfksFYvrRaFTvaEVmJyGDtPtE6sNbgEXyvWFnYQPErQSnzBxG4HsFNvaoGrcF5RaJd8jj", None), # > 100
    ("  dD5PmKQ7SU5ornjAOv5J7VrzNtYqRgmoOfksFYvrRadsdjksdjksdjksdjskdjskFTvaEVmJyGDtPtE6sNbgEXyvWFnYQPErQSnzBxG4HsFNvaoGrcF5RaJd8j dD5PmKQ7SU5ornjAOv5J7VrzNtYqRgmoOfksFYvrRaFTvaEVmJyGDtPtE6sNbgEXyvWFnYQPErQSnzBxG4HsFNvaoGrcF5RaJd8j ", None), # > 100, with trimmed spaces

    # valid
    ("dD5PmKQ7SU5ornjAOv5J7VrzNtYqRgmoOfksFYvrRaFjdhsdhjsdhsjdhsTvaEVmJyGDtPtE6sNbgEXyvWFnYQPErQSnzBxG4Hs", "dD5PmKQ7SU5ornjAOv5J7VrzNtYqRgmoOfksFYvrRaFjdhsdhjsdhsjdhsTvaEVmJyGDtPtE6sNbgEXyvWFnYQPErQSnzBxG4Hs"), # 100
    ("241Pizza", "241Pizza"),
    ("McDonalds", "McDonalds"),
    (" subway ", "subway"),
])
def test_validate_restaurant_name(input, expected):
    from validate import validate_restaurant_name
    do_validate_test(validate_restaurant_name, input, expected)


@pytest.mark.parametrize("input, expected", [
    # invalid: non-empty
    ("",      None), # empty input check
    (" ",     None), # with trimmed spaces
    ("     ", None), # with trimmed spaces

    # invalid: not all int values
    ("123412341234123d", None), # is not all int values

    # valid
    ("378282246310005", "378282246310005"),
    ("371449635398431", "371449635398431"),
    ("378734493671000", "378734493671000"),
])
def test_validate_account_card_number(input, expected):
    from validate import validate_account_card_number
    do_validate_test(validate_account_card_number, input, expected)


@pytest.mark.parametrize("input, expected", [
    # account card code
    # invalid: non-empty
    ("",       None),

    # invalid: wrong length
    ("", None),
    ("1212", None), # > 3

    # tests isdigit
    ("L21", None), # L is not a digit

    # tests isascii
    ("٤21", None), # ٤ is not ascii

    # valid
    ("212", "212"), # 3
    ("988", "988"),

])
def test_validate_account_card_code(input, expected):
    from validate import validate_account_card_code
    do_validate_test(validate_account_card_code, input, expected)


@pytest.mark.parametrize("input, expected", [
    # invalid: wrong length
    ("", None),
    ("1212", None), # > 4
    ("121212", None), # > 5

    # date[2] is not a /
    ("12-12", None),

    # test for all ascii chars
    ("٤2156", None),

    # test for all numeric chars except the /
    ("12/1a", None), # date[5] is not a number
    ("1a/12", None), # date[1] is not a number

    # valid
    ("12/12", "12/12"), #5
    ("01/01", "01/01"),
])
def test_validate_account_card_expiry(input, expected):
    from validate import validate_account_card_expiry
    do_validate_test(validate_account_card_expiry, input, expected)


@pytest.mark.parametrize("input, expected", [
    # invalid: non-empty
    ("",      None), # empty input check
    (" ",     None), # with trimmed spaces
    ("     ", None), # with trimmed spaces

    # invalid: length errors
    ("vHH8O9NUeF8VQUDtORuOYxyMFArYtZh2gWtoo87sJpo0H0Ftepkx6GYr88OHjR7gTX47TfVa7PpD5tAqH12TsozxdOoz0ZK6gUvbwrc8MEEqwKMeU9orMEyre2Wtev87MKSUqo5PoYATpNOjrwmMM8cpJEnfDdUhSzpobFFoh4mzMzHcqwOVPV9TAzk2NNg2FgYgZWeMwrc8MEEqwKMeU9orMEyre2Wtev87MKSUqo5PoYATpNOjrwmMM8cpJEnfDdUhSzpobFFoh4mzMzHcqwOVPV9TAzk2NNg2FgYgZWeMwrc8MEEqwKMeU9orMEyre2Wtev87MKSUqo5PoYATpNOjrwmMM8cpJEnfDdUhSzpobFFoh4mzMzHcqwOVPV9TAzk2NNg2FgYgZWeMwssasarc8MEEqwKMeU9orMEyre2Wtev87MKSUqo5PoYATpNOjrwmMM8cpJEnfDdUhSzpobFFoh4mzMzHcqwOVPV9TAzk2NNg2FgYgZWeM", None), # > 500
    (  "vHH8O9NUeF8VQUDtORuOYxyMFArYtZh2gWtoo87sJpo0H0Ftepkx6GYr88OHjR7gTX47TfVa7PpD5tAqH12TsozxdOoz0ZK6gUvbwrc8MEEqwKMeU9orMEyre2Wtev87MKSUqo5PoYATpNOjrwmMM8cpJEnfDdUhSzpobFFoh4mzMzHcqwOVPV9TAzk2NNg2FgYgZWeMwrc8MEEqwKMeU9orMEyre2Wtev87MKSUqo5PoYATpNOjrwmMM8cpJEnfDdUhSzpobFFoh4mzMzHcqwOVPV9TAzk2NNg2FgYgZWeMwrc8MEEqwKMeU9orMEyre2Wtev87MKSUqo5PoYATpNOjrwmMM8cpJEnfDdUhSzpobFFoh4mzMzHcqwOVPV9TAzk2NNg2FgYgZWeMsasawrc8MEEqwKMeU9orMEyre2Wtev87MKSUqo5PoYATpNOjrwmMM8cpJEnfDdUhSzpobFFoh4mzMzHcqwOVPV9TAzk2NNg2FgYgZWeM"  , None), # > 500, with trimmed spaces

    # valid
    ("dD5PmKQ7SU5ornjAOv5J7VrzNtYqRgmoOfksFYvrRaFjdhsdhjsdhsjdhsTvaEVmJyGDtPtE6sNbgEXyvWFnYQPErQSnzBxG4Hs", "dD5PmKQ7SU5ornjAOv5J7VrzNtYqRgmoOfksFYvrRaFjdhsdhjsdhsjdhsTvaEVmJyGDtPtE6sNbgEXyvWFnYQPErQSnzBxG4Hs"), # 100
    ("1234 Street AVE", "1234 Street AVE"),
    ("  1234 Street AVE  ", "1234 Street AVE"),
])
def test_validate_account_address(input, expected):
    from validate import validate_account_address
    do_validate_test(validate_account_address, input, expected)


@pytest.mark.parametrize("input, expected", [
    # invalid: wrong length
    ("",None), # empty input check
    ("KjNzOuRpHsEfWcXqUdKyGwHbAeTiFzEiCmSdJlOrWnLuAfGvZxNpIyHbVuTaLqXjKrApXoLrEhAsDfFkYeLbVrKgPpYvDdViMfXoOxJjCrYiMlTgBhPnWkLaXsFeHlIeAeLlVoFbDkUvTgKqAuLtXnSvIzQgQmGoBmDzFDDSDSDSKjNzOuRpHsEfWcXqUdKyGwHbAeTiFzEiCmSdJlOrWnLuAfGvZxNpIyHbVuTaLqXjKrApXoLrEhAsDfFkYeLbVrKgPpYvDdViMfXoOxJjCrYiMlTgBhPnWkLaXsFeHlIeAeLlVoFbDkUvTgKqAuLtXnSvIzQgQmGoBmDzFDDSDSDS", None), # > 100

    # valid
    ("dD5PmKQ7SU5ornjAOv5J7VrzNtYqRgmoOfksFYvrRaFjdhsdhjsdhsjdhsTvaEVmJyGDtPtE6sNbgEXyvWFnYQPErQSnzBxG4Hs", "dD5PmKQ7SU5ornjAOv5J7VrzNtYqRgmoOfksFYvrRaFjdhsdhjsdhsjdhsTvaEVmJyGDtPtE6sNbgEXyvWFnYQPErQSnzBxG4Hs"), # 100
    ("Pizza", "Pizza"),
])
def test_validate_menu_item(input, expected):
    from validate import validate_menu_item
    do_validate_test(validate_menu_item, input, expected)


@pytest.mark.parametrize("input, expected", [
    # invalid: wrong length
    ("", None), # empty input check
    ("wFzLpHgDxKcYqZoUvEaIbNfRjQsXkHlMmCvGuTtXhJiYnOaEoVrZpSbCpWlPvQaAqGdUcLgXkWwYjXrHxToVrQnLuPdSrJkRfMiAqZvKuPmZlLvYfNwFbAtGmUeEjNoXpVhGgIhJtAmXsZzJpCrByCdRdLrGoRpKeKmAcZeRkIuMpLtYnHjOuVzTdHh", None), # > 100

    # valid
    ("dD5PmKQ7SU5ornjAOv5J7VrzNtYqRgmoOfksFYvrRaFjdhsdhjsdhsjdhsTvaEVmJyGDtPtE6sNbgEXyvWFnYQPErQSnzBxG4Hs", "dD5PmKQ7SU5ornjAOv5J7VrzNtYqRgmoOfksFYvrRaFjdhsdhjsdhsjdhsTvaEVmJyGDtPtE6sNbgEXyvWFnYQPErQSnzBxG4Hs"), # 100
    ("John", "John"),
])
def test_validate_first_last_name(input, expected):
    from validate import validate_first_last_name
    do_validate_test(validate_first_last_name, input, expected)


@pytest.mark.parametrize("input, expected", [
    # invalid: wrong length
    ("",  None),
    ("$",  None),
    (" $ ",  None),

    # invalid: not a float
    ("a", None),
    ("1.2.3", None),
    ("1x", None),

    # invalid: tests for negative
    ("-1", None),

    # invalid: tests for more than 2 decimal places
    ("1.333", None),

    # valid
    ("1",    100),
    ("1.33", 133),
    ("1.3",  130),
    (" 1.3",  130),
    ("$ 1.3",  130),
    (" $ 1.3",  130),
    (" $ 1.30 ",  130),
    (" $ 0001.30000 ",  130),
])
def test_validate_price(input, expected):
    from validate import validate_price
    do_validate_test(validate_price, input, expected)
