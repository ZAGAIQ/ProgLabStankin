import unittest
from unittest.mock import patch, mock_open
import main
import requests

class TestPhoneFinder(unittest.TestCase):

    # ---------- find_phone_numbers ----------

    def test_find_phone_numbers_normalized(self):
        text = """ Привет! Мой личный номер +7 (999) 123-45-67, рабочий 8 800 555 35 35. 
            Можно позвонить также на +7-912-345-67-89, либо 8 (905) 111 22 33. 
            В офисе у нас есть горячая линия 8 495 765-43-21, для поддержки клиентов +7 (495) 765 43 21. 
            Если хочешь написать другу, его номер +7(921)555-55-55, а мама всегда на 8 916 777 88 99. 
            Не забудь, что старые контакты могут быть: +7 900 000 00 00, 8(903)333-22-11, +7-912-000-11-22. 
            А ещё есть тестовые номера: 8 800 000 00 00, +7 (800) 111 22 33, 8-495-123-45-67. """
        result = main.find_phone_numbers(text)
        self.assertEqual(result, ['+79991234567', '+78005553535', '+79123456789', '+79051112233', '+84957654321', '+74957654321',
                                    '+79215555555', '+79167778899', '+79000000000', '+79033332211', '+79120001122', '+78000000000',
                                    '+78001112233', '+74951234567'])

    def test_find_phone_numbers_non_normalized(self):
        text = """ Позвони по 8 (905) 111-22-33 или 8 916 777 88 99. 
            Другой контакт: 8-912-345-67-89. 
            Старые номера: 8 495 765 43 21, 8(800) 555 35 35. 
            А тестовые: 8 903 333-22-11, 8-800-000-00-00. """
        result = main.find_phone_numbers(text, normalize=False)
        self.assertEqual(result, ['8 (905) 111-22-33','8 916 777 88 99','8-912-345-67-89','8 495 765 43 21',
                                    '8(800) 555 35 35','8 903 333-22-11','8-800-000-00-00'])

    def test_find_phone_numbers_invalid(self):
        text = "номер 1234567890 невалидный"
        self.assertEqual(main.find_phone_numbers(text), [])

    def test_find_phone_numbers_with_symbols(self):
        text = "мой номер: +7(900)---000--00--00"
        result = main.find_phone_numbers(text)
        self.assertEqual(result, ['+79000000000'])

    # ---------- find_in_file ----------

    @patch("builtins.open", new_callable=mock_open, read_data="+7 999 222 33 44")
    def test_find_in_file(self, mock_file):
        result = main.find_in_file('fakefile.txt')
        self.assertEqual(result, ['+79992223344'])

    # ---------- _strip_tags_and_scripts ----------

    def test_strip_tags_and_scripts(self):
        html = """
        <html><head>
        <style>body{color:red;}</style>
        <script>alert('hi');</script>
        </head>
        <body>
        Hello <b>world</b> &amp; friends! <!-- comment -->
        </body></html>
        """
        text = main._strip_tags_and_scripts(html)
        self.assertNotIn('alert', text)
        self.assertNotIn('body', text)
        self.assertIn('Hello world & friends!', text)

    # ---------- find_in_webpage ----------

    def test_find_in_webpage(self):
        html = "<html><body>Наш номер: +7(921)555-55-55</body></html>"

        class DummyResponse:
            status_code = 200
            text = html
            def raise_for_status(self): pass

        def fake_get(url, headers=None, timeout=None):
            return DummyResponse()

        with patch('requests.get', fake_get):
            result = main.find_in_webpage("http://example.com")
        self.assertEqual(result, ['+79215555555'])

    def test_find_in_webpage_raises(self):
        def fake_get(url, headers=None, timeout=None):
            raise requests.RequestException("Connection error")
        with patch('requests.get', fake_get):
            with self.assertRaises(requests.RequestException):
                main.find_in_webpage("http://badurl.test")


if __name__ == "__main__":
    unittest.main(verbosity=2)
